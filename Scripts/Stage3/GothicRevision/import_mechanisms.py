"""Frozen, additive Mechanisms03 import. Only the root writer may call main().

Offline: python import_mechanisms.py --freeze [--out ABSOLUTE_DIRECTORY]
UE: import import_mechanisms as im; report = im.main(freeze_path=...)
No level, actor, existing source asset, or project setting is edited.
"""
import argparse
import hashlib
import itertools
import json
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path('C:/Users/whghk/Desktop/CastleKit/Stage3/Mechanisms03_20261125')
PROJECT = Path(__file__).resolve().parents[3]
OUT = PROJECT / 'Saved/Stage3GothicRevision20261125/MechanismImport'
DEST = '/Game/Environment/Stage3/GothicRevision_20261125'
OWNER = 'GothicRevisionMechanisms03_v1'
TARGETS = {'steel': [72, 71, 74], 'iron': [52, 50, 54],
           'brass': [150, 134, 107], 'limestone': [119, 115, 109],
           'dark_stone': [89, 86, 82]}
SUFFIXES = ('BaseColor', 'Normal_DX', 'ORM')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temporary.replace(path)


def safe_source(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError('Source path escapes delivery: ' + str(relative))
    return path


def linear(byte):
    x = byte / 255.0
    return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4


def mean_linear_png(path):
    # Offline preparation only. Unreal does not require Pillow or numpy.
    from PIL import Image
    with Image.open(path) as image:
        rgb = image.convert('RGB')
        hist = rgb.histogram()
        count = rgb.width * rgb.height
        return [sum(hist[c * 256 + i] * linear(i) for i in range(256)) / count
                for c in range(3)]


def verify_frozen(frozen):
    root = Path(frozen['source'])
    mismatches = []
    for relative, expected in frozen['files'].items():
        path = safe_source(root, relative)
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            mismatches.append({'file': relative, 'expected': expected, 'actual': actual})
    for relative in frozen.get('absent_evidence', []):
        if safe_source(root, relative).exists():
            mismatches.append({'file': relative, 'expected': 'absent', 'actual': 'now present'})
    if mismatches:
        raise RuntimeError('Frozen delivery changed; create a new freeze: ' + json.dumps(mismatches))
    return True


def freeze(source=SOURCE, out=OUT):
    """Read-only source snapshot; never calls UE. Incomplete QA is recorded honestly.

    Existing freeze files are immutable and named by their full-input digest.
    A stale manifest or a file changing during the scan refuses the snapshot.
    """
    source, out = Path(source).resolve(), Path(out).resolve()
    result = {'schema': 1, 'source': str(source), 'destination': DEST,
              'created_utc': datetime.now(timezone.utc).isoformat(), 'files': {},
              'absent_evidence': [], 'assets': [], 'materials': {}, 'qa_warnings': [],
              'success': False}

    def track(relative):
        relative = str(relative).replace('\\', '/')
        path = safe_source(source, relative)
        result['files'][relative] = sha(path)
        return path

    try:
        manifest = read(track('asset_manifest.json'))
        result['manifest_status'] = {k: manifest.get(k) for k in
            ('version', 'asset_count', 'assembly_count', 'capture_count_current',
             'pending_capture_paths', 'user_art_approval', 'delivery_type')}
        for relative in ('README.md', 'BRIEF.md', manifest.get('independent_qa_report', 'QA/FINAL_QA.md')):
            if safe_source(source, relative).exists():
                track(relative)
            else:
                result['absent_evidence'].append(relative)
                result['qa_warnings'].append('Missing delivery evidence: ' + relative)
        result['final_qa_present'] = not any('FINAL_QA' in p for p in result['absent_evidence'])
        result['qa_warnings'].append('Technical QA and source captures do not establish user art approval or Unreal runtime verification.')
        assets = [a for a in manifest['items'] if a['kind'] == 'asset']
        if len(assets) != 24 or manifest['asset_count'] != 24:
            raise RuntimeError('Expected exactly 24 mechanism meshes')
        if len({a['name'] for a in assets}) != 24:
            raise RuntimeError('Duplicate asset names')
        keys = set()
        for item in assets:
            if not re.fullmatch(r'SM_[A-Za-z0-9_]+', item['name']):
                raise RuntimeError('Unsafe asset name: ' + item['name'])
            for field, hash_field in (('blend', 'sha256'), ('fbx', 'fbx_sha256')):
                track(item[field])
                if result['files'][item[field]] != item.get(hash_field):
                    raise RuntimeError('Stale manifest hash: ' + item[field])
            metadata = read(track(item['metadata']))
            slots = metadata.get('materials')
            if not slots or not item.get('bounds_m'):
                raise RuntimeError('Missing material/bounds contract: ' + item['name'])
            for slot in slots:
                key = slot.removeprefix('M_S3_')
                if key not in TARGETS:
                    raise RuntimeError('Unmapped source material: ' + slot)
                keys.add(key)
            if not item.get('capture_current'):
                result['qa_warnings'].append('Capture not current: ' + item['name'])
            # Only completed numeric evidence relevant to this mesh is included.
            evidence = []
            numeric_paths = list((source / 'QA/numeric').glob('*' + item['name'] + '*'))
            numeric_paths += list((source / item['metadata']).parent.glob('*QA*.json'))
            for p in sorted(set(numeric_paths)):
                if p.is_file():
                    track(p.relative_to(source))
                    evidence.append(p.relative_to(source).as_posix())
            exporter = ({'axis_forward': '-Y', 'axis_up': 'Z', 'apply_scale_options': 'FBX_SCALE_UNITS',
                         'evidence': 'DockScripts/dock_mesh.py'} if item['category'] == 'Dock' else
                        {'axis_forward': '-Z', 'axis_up': 'Y', 'apply_scale_options': 'FBX_SCALE_NONE',
                         'evidence': 'WeightScripts/export.py or shoe.py'} if item['category'] == 'Weight' else
                        {'axis_forward': '-Z', 'axis_up': 'Y', 'apply_scale_options': 'FBX_SCALE_NONE',
                         'evidence': 'ConnectionScripts/build_gate_lock.py'} if item['name'].startswith('SM_S3_GateLock_') else
                        {'evidence': 'Read authoritative imported bounds and axis_mapping_candidates; exporter not assumed'})
            result['assets'].append(dict(item, metadata_data=metadata, source_export=exporter,
                expected_slots=slots, expected_collision_count=len(metadata.get('collision_objects', metadata.get('collision', []))),
                numeric_evidence=evidence))
        for key in sorted(keys):
            textures = {suffix: 'Shared/Textures/' + key + '/' + suffix + '.png' for suffix in SUFFIXES}
            for relative in textures.values():
                track(relative)
            mean = mean_linear_png(source / textures['BaseColor'])
            if min(mean) <= 1e-8:
                raise RuntimeError('Cannot normalize zero-mean BaseColor: ' + key)
            result['materials'][key] = {'textures': textures, 'source_mean_linear': mean,
                'normalization': [1 / value for value in mean], 'target_srgb8': TARGETS[key],
                'color_tint': [linear(value) for value in TARGETS[key]], 'brightness': 1.0}
        # Rehash after scanning and calibration: reject mixed revisions.
        verify_frozen(result)
        payload = {'files': result['files'], 'absent_evidence': result['absent_evidence'], 'targets': TARGETS, 'owner': OWNER}
        result['input_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        result['success'] = True
        path = out / ('freeze_' + result['input_sha256'] + '.json')
        if not path.exists():
            write(path, result)
        write(out / 'latest_freeze.json', {'freeze_path': str(path), 'input_sha256': result['input_sha256']})
        return {'freeze_path': str(path), 'input_sha256': result['input_sha256'],
                'assets': len(assets), 'qa_warnings': result['qa_warnings']}
    except Exception:
        result['error'] = traceback.format_exc()
        write(out / 'freeze_attempt_report.json', result)
        raise


def bounds_mapping(source_m, actual_cm, tolerance=.2):
    """Measure possible XY handedness/axis mappings, keeping Z up.

    Symmetric meshes cannot prove their axes from AABB; all valid candidates
    are reported. Root must use asymmetric pieces/assembly references to place.
    """
    candidates = []
    for swap in (False, True):
        axes = (1, 0, 2) if swap else (0, 1, 2)
        for sx, sy in itertools.product((-1, 1), repeat=2):
            signs = (sx, sy, 1)
            transformed = [[0.] * 3 for _ in range(2)]
            for axis, (src_axis, sign) in enumerate(zip(axes, signs)):
                values = [source_m[0][src_axis] * sign * 100, source_m[1][src_axis] * sign * 100]
                transformed[0][axis], transformed[1][axis] = min(values), max(values)
            error = max(abs(transformed[row][axis] - actual_cm[row][axis])
                        for row in range(2) for axis in range(3))
            if error <= tolerance:
                candidates.append({'ue_axes_from_blender': [('-' if sign < 0 else '+') + 'XYZ'[a]
                                    for a, sign in zip(axes, signs)], 'max_error_cm': error})
    return candidates


def main(freeze_path=None, out=OUT, require_final_qa=False):
    """Root-only UE writer. Additive hash-revision subfolder; no map mutation.

    Same frozen batch may safely resume; unknown/unowned existing objects abort.
    New source content gets a new subfolder, preserving every prior revision.
    """
    out = Path(out)
    if freeze_path is None:
        freeze_path = read(out / 'latest_freeze.json')['freeze_path']
    frozen = read(freeze_path)
    if not frozen.get('success'):
        raise RuntimeError('Invalid or incomplete freeze')
    verify_frozen(frozen)  # Before importing Unreal or mutating assets.
    if require_final_qa and not frozen['final_qa_present']:
        raise RuntimeError('FINAL_QA.md is not available in this frozen batch')
    import unreal as u
    ea, ml, at = u.EditorAssetLibrary, u.MaterialEditingLibrary, u.AssetToolsHelpers.get_asset_tools()
    digest = frozen['input_sha256']
    destination = DEST + '/Mechanisms_' + digest[:16]
    report_path = out / ('import_report_' + digest + '.json')
    report = {'success': False, 'freeze_path': str(freeze_path), 'input_sha256': digest,
              'destination': destination, 'qa_warnings': frozen['qa_warnings'],
              'textures': {}, 'materials': {}, 'meshes': {}, 'errors': [], 'map_modified': False}

    def save(obj):
        if not ea.save_loaded_asset(obj):
            raise RuntimeError('Asset save failed: ' + obj.get_path_name())

    def tag(obj):
        ea.set_metadata_tag(obj, 'GothicRevisionOwner', OWNER)
        ea.set_metadata_tag(obj, 'GothicRevisionInputSHA256', digest)

    def existing(path, cls):
        if not ea.does_asset_exist(path):
            return None
        obj = ea.load_asset(path)
        if not isinstance(obj, cls) or ea.get_metadata_tag(obj, 'GothicRevisionOwner') != OWNER or ea.get_metadata_tag(obj, 'GothicRevisionInputSHA256') != digest:
            raise RuntimeError('Refusing unowned or mismatched destination: ' + path)
        return obj

    def imported(relative, folder, name, cls, options=None):
        path = folder + '/' + name
        obj = existing(path, cls)
        if obj:
            return obj
        file = safe_source(Path(frozen['source']), relative)
        if sha(file) != frozen['files'][relative]:
            raise RuntimeError('Source changed immediately before import: ' + relative)
        task = u.AssetImportTask()
        task.filename, task.destination_path, task.destination_name = str(file), folder, name
        task.automated, task.save, task.replace_existing = True, False, False
        if options is not None:
            task.options = options
            task.factory = u.FbxFactory()
        at.import_asset_tasks([task])
        obj = ea.load_asset(path)
        if not isinstance(obj, cls):
            raise RuntimeError('Import failed: ' + str((relative, list(task.imported_object_paths))))
        tag(obj)
        save(obj)
        return obj

    try:
        instances = {}
        for key, cal in frozen['materials'].items():
            textures = {}
            for suffix, relative in cal['textures'].items():
                texture = imported(relative, destination + '/Textures', 'T_GM_' + key + '_' + suffix, u.Texture2D)
                texture.set_editor_property('srgb', suffix == 'BaseColor')
                compression = (u.TextureCompressionSettings.TC_NORMALMAP if suffix == 'Normal_DX' else
                               u.TextureCompressionSettings.TC_DEFAULT if suffix == 'BaseColor' else u.TextureCompressionSettings.TC_MASKS)
                texture.set_editor_property('compression_settings', compression)
                if suffix == 'Normal_DX':
                    texture.set_editor_property('flip_green_channel', False)
                save(texture)
                textures[suffix] = texture
                report['textures'][key + '_' + suffix] = {'path': texture.get_path_name(), 'source': relative,
                    'srgb': texture.get_editor_property('srgb'), 'compression': str(texture.get_editor_property('compression_settings')),
                    'sha256': frozen['files'][relative]}
            name = 'M_GM_' + key
            parent = existing(destination + '/Parents/' + name, u.Material)
            if not parent:
                parent = at.create_asset(name, destination + '/Parents', u.Material, u.MaterialFactoryNew())
                if not parent:
                    raise RuntimeError('Cannot create parent: ' + name)
                tag(parent)
                samples = {}
                for index, suffix in enumerate(SUFFIXES):
                    node = ml.create_material_expression(parent, u.MaterialExpressionTextureSample, -900, index * 220)
                    node.texture = textures[suffix]
                    node.sampler_type = (u.MaterialSamplerType.SAMPLERTYPE_COLOR if suffix == 'BaseColor' else
                                         u.MaterialSamplerType.SAMPLERTYPE_NORMAL if suffix == 'Normal_DX' else u.MaterialSamplerType.SAMPLERTYPE_MASKS)
                    samples[suffix] = node
                if not ml.connect_material_property(samples['Normal_DX'], 'RGB', u.MaterialProperty.MP_NORMAL):
                    raise RuntimeError('Normal connection failed')
                for channel, prop in [('R', u.MaterialProperty.MP_AMBIENT_OCCLUSION), ('G', u.MaterialProperty.MP_ROUGHNESS), ('B', u.MaterialProperty.MP_METALLIC)]:
                    if not ml.connect_material_property(samples['ORM'], channel, prop):
                        raise RuntimeError('ORM connection failed')
                norm = ml.create_material_expression(parent, u.MaterialExpressionConstant3Vector, -900, -220)
                norm.set_editor_property('constant', u.LinearColor(*cal['normalization'], 1))
                tint = ml.create_material_expression(parent, u.MaterialExpressionVectorParameter, -600, -220)
                tint.set_editor_property('parameter_name', 'ColorTint')
                tint.set_editor_property('default_value', u.LinearColor(*cal['color_tint'], 1))
                tint.set_editor_property('group', 'Stage3 Color Correction')
                brightness = ml.create_material_expression(parent, u.MaterialExpressionScalarParameter, -300, -220)
                brightness.set_editor_property('parameter_name', 'Brightness')
                brightness.set_editor_property('default_value', 1.)
                brightness.set_editor_property('group', 'Stage3 Color Correction')
                previous, output = samples['BaseColor'], 'RGB'
                for index, (other, other_output) in enumerate(((norm, ''), (tint, 'RGB'), (brightness, ''))):
                    multiply = ml.create_material_expression(parent, u.MaterialExpressionMultiply, -600 + index * 300, 0)
                    if not ml.connect_material_expressions(previous, output, multiply, 'A') or not ml.connect_material_expressions(other, other_output, multiply, 'B'):
                        raise RuntimeError('BaseColor calibration connection failed')
                    previous, output = multiply, ''
                if not ml.connect_material_property(previous, '', u.MaterialProperty.MP_BASE_COLOR):
                    raise RuntimeError('BaseColor output connection failed')
                ml.recompile_material(parent)
                save(parent)
            name = 'MI_GM_' + key
            instance = existing(destination + '/Instances/' + name, u.MaterialInstanceConstant)
            if not instance:
                instance = at.create_asset(name, destination + '/Instances', u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
                if not instance:
                    raise RuntimeError('Cannot create instance: ' + name)
                tag(instance)
            ml.set_material_instance_parent(instance, parent)
            ml.set_material_instance_vector_parameter_value(instance, 'ColorTint', u.LinearColor(*cal['color_tint'], 1))
            ml.set_material_instance_scalar_parameter_value(instance, 'Brightness', cal['brightness'])
            actual = ml.get_material_instance_vector_parameter_value(instance, 'ColorTint')
            if max(abs(a - b) for a, b in zip((actual.r, actual.g, actual.b), cal['color_tint'])) > 1e-6:
                raise RuntimeError('ColorTint readback failed: ' + key)
            if abs(ml.get_material_instance_scalar_parameter_value(instance, 'Brightness') - cal['brightness']) > 1e-6:
                raise RuntimeError('Brightness readback failed: ' + key)
            ml.update_material_instance(instance)
            save(instance)
            instances['M_S3_' + key] = instance
            report['materials'][key] = dict(cal, parent=parent.get_path_name(), instance=instance.get_path_name(),
                formula='BaseColor_linear / mean(BaseColor_linear) * ColorTint_linear * Brightness')
        for asset in frozen['assets']:
            options = u.FbxImportUI()
            for key, value in {'automated_import_should_detect_type': False, 'mesh_type_to_import': u.FBXImportType.FBXIT_STATIC_MESH,
                    'import_as_skeletal': False, 'import_materials': False, 'import_textures': False, 'import_animations': False}.items():
                options.set_editor_property(key, value)
            data = options.static_mesh_import_data
            for key, value in {'combine_meshes': True, 'auto_generate_collision': False, 'one_convex_hull_per_ucx': True,
                    'convert_scene': True, 'convert_scene_unit': True, 'force_front_x_axis': False,
                    'generate_lightmap_u_vs': False, 'import_uniform_scale': 1.0,
                    'normal_import_method': u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS}.items():
                data.set_editor_property(key, value)
            mesh = imported(asset['fbx'], destination + '/Meshes', asset['name'], u.StaticMesh, options)
            slots = []
            for index, slot in enumerate(mesh.get_editor_property('static_materials')):
                slot_name = str(slot.material_slot_name).split('.')[0]
                if slot_name not in asset['expected_slots'] or slot_name not in instances:
                    raise RuntimeError('Unknown material slot: ' + str((asset['name'], index, slot_name)))
                mesh.set_material(index, instances[slot_name])
                slots.append({'index': index, 'source_slot': slot_name, 'assigned': mesh.get_material(index).get_path_name()})
            if sorted(s['source_slot'] for s in slots) != sorted(asset['expected_slots']):
                raise RuntimeError('Material slots differ from metadata: ' + asset['name'])
            mesh.set_editor_property('light_map_coordinate_index', 1)
            mesh.set_editor_property('light_map_resolution', 64)
            box = mesh.get_bounding_box()
            bounds = [[box.min.x, box.min.y, box.min.z], [box.max.x, box.max.y, box.max.z]]
            mappings = bounds_mapping(asset['bounds_m'], bounds)
            body = mesh.get_editor_property('body_setup')
            if not body:
                raise RuntimeError('No body setup: ' + asset['name'])
            geometry = body.get_editor_property('agg_geom')
            counts = {key: len(geometry.get_editor_property(key)) for key in ('convex_elems', 'box_elems', 'sphere_elems', 'sphyl_elems')}
            row = {'path': mesh.get_path_name(), 'source': asset['fbx'], 'fbx_sha256': frozen['files'][asset['fbx']],
                'bounds': bounds, 'bounds_cm': bounds, 'dimensions_cm': [hi - lo for lo, hi in zip(*bounds)],
                'source_bounds_m': asset['bounds_m'], 'axis_mapping_candidates': mappings,
                'source_orientation': asset['source_export'],
                'axis_ambiguous_from_bounds': len(mappings) != 1, 'material_slots': slots,
                'materials': [s['assigned'] for s in slots],
                'collision_counts': counts, 'expected_collision_count': asset['expected_collision_count'],
                'collision_trace_flag': str(body.get_editor_property('collision_trace_flag')),
                'numeric_evidence': asset['numeric_evidence'],
                'collision_policy': 'Preserve authored UCX only; no generated or complex-as-simple fallback. Root decides actor collision.'}
            report['meshes'][asset['name']] = row
            write(report_path, report)
            if not mappings:
                raise RuntimeError('Imported bounds/units mismatch: ' + asset['name'])
            if sum(counts.values()) != asset['expected_collision_count']:
                raise RuntimeError('Authored collision import mismatch: ' + asset['name'])
            save(mesh)
        verify_frozen(frozen)
        report['success'] = True
        report['mesh_count'] = len(report['meshes'])
        write(out / 'latest_import_report.json', {'report_path': str(report_path), 'destination': destination, 'input_sha256': digest})
        return report
    except Exception:
        report['errors'].append(traceback.format_exc())
        raise
    finally:
        write(report_path, report)
        write(PROJECT / 'Saved/Stage3GothicRevision20261125/import_report.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', help='Offline read-only source freeze; never import into UE')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    if not args.freeze:
        parser.error('Use --freeze offline; call main() explicitly from the coordinated UE root writer')
    print(json.dumps(freeze(args.source, args.out), ensure_ascii=False, indent=2))
