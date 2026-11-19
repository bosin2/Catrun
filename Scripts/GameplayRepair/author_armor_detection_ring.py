"""Author the armor material with a fresh Unreal Python commandlet.

Without -catrunArmorRingAuthor, inspect the source and any saved ring only.
The author flag creates the ring, or migrates the exact first saved ring in place after backup.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
CONTENT = ROOT / 'Content'
SOURCE = '/Game/Systems/Sound/M_VisionFan'
TARGET = '/Game/Systems/Sound/M_ArmorDetectionRing'
SOURCE_FILE = Path('Systems/Sound/M_VisionFan.uasset')
TARGET_FILE = Path('Systems/Sound/M_ArmorDetectionRing.uasset')
AUTHOR_TAG = 'Catrun.ArmorDetectionRing'
LEGACY_RING_SHA256 = 'ac92d3723d1af8a7bbce43666ad150d3b98ec29473d7dfaad133bf85ef0d9307'
EMISSION_GAIN = 'RingEmissionGain'
EMISSION_DEFAULT = 12.0
PACKAGE_SUFFIXES = {'.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'}
COMMAND = u.SystemLibrary.get_command_line().lower().split()
AUTHOR = '-catrunarmorringauthor' in COMMAND
RUN = ROOT / 'Saved/PresentationFix20261119/ArmorRing' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
ASSETS = u.get_editor_subsystem(u.EditorAssetSubsystem)
EDIT = u.MaterialEditingLibrary

# name, default value, slider minimum, slider maximum, graph Y
RING_PARAMETERS = (
    ('RingWidthCm', 5.0, 0.5, 15.0, 560),
    ('RingDashCount', 24.0, 4.0, 64.0, 725),
    ('RingDashDuty', 0.65, 0.1, 0.95, 890),
)
SOURCE_PINS = {'WorldPos', 'Center', 'Range', 'CenterAngle', 'HalfAngle', 'Tex', 'Feather', 'RangeFade', 'Opacity'}
RING_CODE = '''
float2 p = WorldPos.xy - Center.xy;
float dist = length(p);
float width = clamp(RingWidthCm, 0.01, Range);
float inside = dist - (Range - width);
if (dist > Range || inside < 0.0 || dist < max(1.0, Center.z)) return 0.0;

// Use the same direction and sample as the filled vision fan.
float ang = degrees(atan2(p.y, p.x));
float delta = ang - CenterAngle;
delta = delta - 360.0 * floor((delta + 180.0) / 360.0);
float h = max(HalfAngle, 0.001);
if (abs(delta) > h) return 0.0;
float u = (delta + h) / (2.0 * h);
float d = Texture2DSampleLevel(Tex, TexSampler, float2(u, 0.5), 0).r;

// Keep the taper narrower than the ring, including where d is the unblocked Range.
float edgeWidth = min(1.0, width * 0.25);
float edge = saturate((d - dist) / clamp(Feather, 0.001, edgeWidth));
float innerEdge = smoothstep(0.0, edgeWidth, inside);

float count = max(1.0, round(RingDashCount));
float halfDuty = 0.5 * clamp(RingDashDuty, 0.01, 0.99);
float offset = abs(frac(u * count) - 0.5);
float dash = 1.0 - smoothstep(halfDuty * 0.9, halfDuty, offset);
return innerEdge * edge * dash * Opacity;
'''.strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_snapshot():
    protected = {}
    owned = {}
    for path in CONTENT.rglob('*'):
        if path.suffix.lower() in PACKAGE_SUFFIXES and path.is_file():
            relative = path.relative_to(CONTENT)
            files = owned if relative.with_suffix('') == TARGET_FILE.with_suffix('') else protected
            files[relative.as_posix()] = digest(path)
    return protected, owned


def dirty_packages():
    loading = u.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in (*loading.get_dirty_map_packages(), *loading.get_dirty_content_packages()))


def opacity_graph(material):
    node = EDIT.get_material_property_input_node(material, u.MaterialProperty.MP_OPACITY)
    assert isinstance(node, u.MaterialExpressionCustom), material.get_path_name()
    names = [str(pin.get_editor_property('input_name')) for pin in node.get_editor_property('inputs')]
    inputs = EDIT.get_inputs_for_material_expression(material, node)
    assert len(names) == len(inputs) == len(set(names)), names
    assert all(inputs), names
    return node, dict(zip(names, inputs))


def node_identity(node):
    return [node.get_name(), node.get_class().get_name()]


def inspect_emission(material, source):
    emissive = u.MaterialProperty.MP_EMISSIVE_COLOR
    source_color = EDIT.get_material_property_input_node(source, emissive)
    assert isinstance(source_color, u.MaterialExpressionVectorParameter)
    assert str(source_color.get_editor_property('parameter_name')) == 'Color'
    source_output = EDIT.get_material_property_input_node_output_name(source, emissive)
    node = EDIT.get_material_property_input_node(material, emissive)
    base_count = EDIT.get_num_material_expressions(source) + len(RING_PARAMETERS)
    if isinstance(node, u.MaterialExpressionVectorParameter):
        assert node_identity(node) == node_identity(source_color), 'Legacy ring emissive route differs'
        assert EDIT.get_material_property_input_node_output_name(material, emissive) == source_output
        assert EDIT.get_num_material_expressions(material) == base_count
        return 1, None

    assert isinstance(node, u.MaterialExpressionMultiply), 'Ring emissive must multiply the inherited Color'
    assert EDIT.get_num_material_expressions(material) == base_count + 2
    color, gain = EDIT.get_inputs_for_material_expression(material, node)
    assert node_identity(color) == node_identity(source_color), 'Ring emissive Color connection differs'
    assert str(color.get_editor_property('parameter_name')) == 'Color'
    assert isinstance(gain, u.MaterialExpressionScalarParameter)
    assert str(gain.get_editor_property('parameter_name')) == EMISSION_GAIN
    value = float(gain.get_editor_property('default_value'))
    assert value >= 0.0, value
    return 2, value


def inspect_ring(material, source, source_inputs):
    assert isinstance(material, u.Material) and material.get_path_name() == f'{TARGET}.{TARGET_FILE.stem}'
    assert str(ASSETS.get_metadata_tag(material, 'CatrunAuthor')) == AUTHOR_TAG, 'Existing material has another owner'
    node, inputs = opacity_graph(material)
    assert node.get_editor_property('code').strip() == RING_CODE, 'Saved ring shader differs from this author version'
    assert node.get_editor_property('output_type') == u.CustomMaterialOutputType.CMOT_FLOAT1
    assert set(inputs) == SOURCE_PINS | {row[0] for row in RING_PARAMETERS}, sorted(inputs)
    assert {key: node_identity(inputs[key]) for key in SOURCE_PINS} == source_inputs, 'Source pin connections differ'
    for name in ('material_domain', 'blend_mode', 'two_sided', 'disable_depth_test'):
        assert material.get_editor_property(name) == source.get_editor_property(name), name
    parameters = {}
    for name, *_ in RING_PARAMETERS:
        parameter = inputs[name]
        assert isinstance(parameter, u.MaterialExpressionScalarParameter), name
        assert str(parameter.get_editor_property('parameter_name')) == name, name
        parameters[name] = float(parameter.get_editor_property('default_value'))
    assert 0 < parameters['RingWidthCm']
    assert 1 <= parameters['RingDashCount']
    assert 0 < parameters['RingDashDuty'] < 1
    version, gain = inspect_emission(material, source)
    if version == 2:
        parameters[EMISSION_GAIN] = gain
    return version, parameters


def scalar_parameter(material, name, value, slider_min, slider_max, x, y):
    parameter = EDIT.create_material_expression(material, u.MaterialExpressionScalarParameter, x, y)
    assert parameter, name
    parameter.set_editor_property('parameter_name', name)
    parameter.set_editor_property('default_value', value)
    parameter.set_editor_property('slider_min', slider_min)
    parameter.set_editor_property('slider_max', slider_max)
    parameter.set_editor_property('group', 'Armor Ring')
    return parameter


def author_emission(material):
    material.modify()
    emissive = u.MaterialProperty.MP_EMISSIVE_COLOR
    color = EDIT.get_material_property_input_node(material, emissive)
    color_output = EDIT.get_material_property_input_node_output_name(material, emissive)
    gain = scalar_parameter(material, EMISSION_GAIN, EMISSION_DEFAULT, 0.0, 24.0, -600, -350)
    multiply = EDIT.create_material_expression(material, u.MaterialExpressionMultiply, -225, -350)
    assert multiply
    assert EDIT.connect_material_expressions(color, color_output, multiply, 'A')
    assert EDIT.connect_material_expressions(gain, '', multiply, 'B')
    assert EDIT.connect_material_property(multiply, '', emissive)


def author(material, source_inputs):
    node, inputs = opacity_graph(material)
    assert {key: node_identity(value) for key, value in inputs.items()} == source_inputs
    material.modify()
    node.modify()
    pins = list(node.get_editor_property('inputs'))
    parameters = {}
    for name, value, slider_min, slider_max, y in RING_PARAMETERS:
        parameter = scalar_parameter(material, name, value, slider_min, slider_max, -600, y)
        pin = u.CustomInput()
        pin.set_editor_property('input_name', name)
        pins.append(pin)
        parameters[name] = parameter
    # Notify the material only once the new input array is fully wired.
    node.set_editor_property('inputs', pins, notify_mode=u.PropertyAccessChangeNotifyMode.NEVER)
    for name, parameter in parameters.items():
        assert EDIT.connect_material_expressions(parameter, '', node, name), name
    node.set_editor_property('code', RING_CODE)
    node.set_editor_property('description', 'Armor detection ring opacity')
    ASSETS.set_metadata_tag(material, 'CatrunAuthor', AUTHOR_TAG)


def save_ring(material, report):
    report['compile_errors'] = list(EDIT.recompile_material(material))
    assert not report['compile_errors'], report['compile_errors']
    assert not set(dirty_packages()) - {TARGET}, 'Unexpected dirty packages before save'
    assert digest(CONTENT / SOURCE_FILE) == report['source_sha256'], 'Source changed before save'
    assert ASSETS.save_loaded_asset(material, only_if_is_dirty=False), TARGET


def main(report):
    assert '-run=pythonscript' in COMMAND, 'Use a fresh Unreal Python commandlet'
    assert (ROOT / 'Catrun.uproject').is_file(), ROOT
    assert u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is None
    report['dirty_before'] = dirty_packages()
    assert not report['dirty_before'], report['dirty_before']
    protected, owned = package_snapshot()
    report['protected_file_count'] = len(protected)
    report['source_sha256'] = protected[SOURCE_FILE.as_posix()]
    report['target_before'] = owned
    try:
        source = ASSETS.load_asset(SOURCE)
        assert isinstance(source, u.Material), SOURCE
        node, inputs = opacity_graph(source)
        assert set(inputs) == SOURCE_PINS, sorted(inputs)
        assert 'return edge * fade * Opacity;' in node.get_editor_property('code'), 'Source fan opacity changed'
        source_inputs = {key: node_identity(value) for key, value in inputs.items()}

        exists = ASSETS.does_asset_exist(TARGET)
        assert exists == (TARGET_FILE.as_posix() in owned), 'Registry and disk disagree on the target'
        if exists:
            material = ASSETS.load_asset(TARGET)
            version, parameters = inspect_ring(material, source, source_inputs)
            report.update(graph_version=version, parameters=parameters, action='validated_existing')
            if AUTHOR:
                if version == 1:
                    assert owned[TARGET_FILE.as_posix()] == LEGACY_RING_SHA256, 'Legacy ring hash differs from reviewed asset'
                assert not dirty_packages(), 'Loading the existing ring dirtied a package'
                report['backups'] = {}
                for name, sha in owned.items():
                    backup = RUN / 'Before' / name
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(CONTENT / name, backup)
                    assert digest(backup) == sha, name
                    report['backups'][name] = {'path': str(backup), 'sha256': sha}
                if version == 1:
                    author_emission(material)
                    version, adjusted = inspect_ring(material, source, source_inputs)
                    assert version == 2 and adjusted == {**parameters, EMISSION_GAIN: EMISSION_DEFAULT}
                    report.update(graph_version=version, parameters=adjusted, action='migrated_emission')
                    save_ring(material, report)
        elif AUTHOR:
            assert not owned, 'Found an orphaned target package sidecar'
            assert not dirty_packages(), 'Loading the source dirtied a package'
            material = ASSETS.duplicate_asset(SOURCE, TARGET)
            assert isinstance(material, u.Material), TARGET
            author(material, source_inputs)
            author_emission(material)
            version, parameters = inspect_ring(material, source, source_inputs)
            assert version == 2 and parameters[EMISSION_GAIN] == EMISSION_DEFAULT
            report.update(graph_version=version, parameters=parameters, action='created')
            save_ring(material, report)
        else:
            report['action'] = 'target_absent'
    finally:
        after_protected, after_owned = package_snapshot()
        report['protected_changes'] = sorted(name for name in protected.keys() | after_protected.keys()
                                             if protected.get(name) != after_protected.get(name))
        report['target_after'] = after_owned
        report['dirty_after'] = dirty_packages()

    assert not report['protected_changes'], report['protected_changes']
    assert not report['dirty_after'], report['dirty_after']
    if report['action'] in ('created', 'migrated_emission'):
        assert TARGET_FILE.as_posix() in report['target_after'], 'No saved ring package on disk'
        assert report['target_after'] != owned, 'Ring authoring did not change the target on disk'
    else:
        assert report['target_after'] == owned, 'Read-only target changed on disk'


report = {'mode': 'author' if AUTHOR else 'audit', 'source': SOURCE, 'target': TARGET, 'completed': False}
try:
    main(report)
    report['completed'] = True
except Exception:
    report['error'] = traceback.format_exc()
    raise
finally:
    RUN.mkdir(parents=True, exist_ok=True)
    report_file = RUN / 'report.json'
    report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    u.log(f'Armor detection ring report: {report_file}')
