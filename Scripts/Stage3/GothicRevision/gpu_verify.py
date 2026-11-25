"""Read-only GPU BaseColor QA; root schedules this in a disposable commandlet.

Use -run=pythonscript -AllowCommandletRendering -RenderOffscreen -d3d11.
No package/map saves. Import is inert; call main(), or execute as the script.
Only transient test actors and a restored world MPC instance are touched.
"""
import json
import math
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
RUN = ROOT / 'Saved/Stage3GothicRevision20261125'
OUT = RUN / 'GPU'
DEST = '/Game/Environment/Stage3/GothicRevision_20261125/'
ARMOR = DEST + 'Characters/MI_Gothic_ArmorSteel_72_71_74'
SIZE = 256
TOLERANCE = 2.5


def srgb(value):
    return 255. * (12.92 * value if value <= .0031308 else 1.055 * value ** (1 / 2.4) - .055)


def package(path):
    return path.split('.')[0]


def color(value):
    return [value.r, value.g, value.b, value.a]


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def select_cases(report):
    """All five new mechanism roles, new armor, one wrapper per calibrated role."""
    imported = read(RUN / 'import_report.json')
    assert imported['success']
    assert set(imported['materials']) == {'brass', 'dark_stone', 'iron', 'limestone', 'steel'}
    cases = []
    for role, item in sorted(imported['materials'].items()):
        cases.append({'kind': 'mechanism', 'role': role, 'material': item['instance'],
                      'target_srgb': item['target_srgb8']})
    cases.append({'kind': 'armor', 'role': 'ArmorSteel', 'material': ARMOR,
                  'target_srgb': [72, 71, 74]})
    old = read(ROOT / 'Saved/Stage3MaterialCorrection20261125/Materials/application_report.json')
    assert old['success']
    old_instances = {package(key): value for key, value in old['instances'].items()}
    cutaway = read(RUN / 'occlusion_report.json')
    assert cutaway['success']
    sampled_roles = set()
    report['wrapper_checks'] = []
    report['uncalibrated_wrappers_not_color_targeted'] = []
    ml = u.MaterialEditingLibrary
    ea = u.EditorAssetLibrary
    for parent_path, entry in sorted(cutaway['parents'].items()):
        mi = u.load_asset(entry['instance'])
        assert isinstance(mi, u.MaterialInstanceConstant), entry['instance']
        source_path = ea.get_metadata_tag(mi, 'Stage3ReadabilitySource')
        assert source_path, ('Missing wrapper source metadata', entry['instance'])
        source = u.load_asset(source_path)
        assert source
        base = source.get_base_material() if isinstance(source, u.MaterialInstanceConstant) else source
        parent = mi.get_base_material()
        assert package(parent.get_path_name()) == package(parent_path)
        for name in ('BASE_COLOR', 'NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS', 'METALLIC', 'EMISSIVE_COLOR'):
            prop = getattr(u.MaterialProperty, 'MP_' + name)
            a = ml.get_material_property_input_node(base, prop)
            b = ml.get_material_property_input_node(parent, prop)
            assert (a.get_name() if a else None) == (b.get_name() if b else None), (parent_path, name)
            assert ml.get_material_property_input_node_output_name(base, prop) == ml.get_material_property_input_node_output_name(parent, prop)
        checked = {'material': mi.get_path_name(), 'source': source_path,
                   'non_opacity_roots_and_output_channels_preserved': True}
        if package(source_path) not in old_instances:
            report['uncalibrated_wrappers_not_color_targeted'].append(mi.get_path_name())
            report['wrapper_checks'].append(checked)
            continue
        item = old_instances[package(source_path)]
        tint = color(ml.get_material_instance_vector_parameter_value(mi, 'ColorTint'))
        original_tint = color(ml.get_material_instance_vector_parameter_value(source, 'ColorTint'))
        brightness = ml.get_material_instance_scalar_parameter_value(mi, 'Brightness')
        original_brightness = ml.get_material_instance_scalar_parameter_value(source, 'Brightness')
        assert max(abs(a - b) for a, b in zip(tint, original_tint)) < 1.e-6
        assert abs(brightness - original_brightness) < 1.e-6
        checked.update(ColorTint=tint, Brightness=brightness, parameters_preserved=True)
        report['wrapper_checks'].append(checked)
        role = item['calibration'].rsplit('__', 1)[-1]
        if role not in sampled_roles:
            cases.append({'kind': 'cutaway', 'role': role, 'material': mi.get_path_name(),
                          'source': source_path, 'target_srgb': item['target_srgb']})
            sampled_roles.add(role)
    assert {'Wall', 'Pillar', 'GateDecorStone'} <= sampled_roles, sampled_roles
    report['expected_case_count'] = len(cases)
    report['sampled_wrapper_roles'] = sorted(sampled_roles)
    for case in cases:
        assert case['material'].startswith(DEST), case
    return cases


def measure(pixels):
    assert len(pixels) == SIZE * SIZE, len(pixels)
    sums = [0., 0., 0.]
    squares = [0., 0., 0.]
    black = 0
    for pixel in pixels:
        values = [pixel.r, pixel.g, pixel.b]
        black += max(values) < 1.e-6
        for index, value in enumerate(values):
            assert math.isfinite(value) and value >= 0, values
            sums[index] += value
            squares[index] += value * value
    means = [value / len(pixels) for value in sums]
    return {'gpu_mean_linear': means,
            'gpu_representative_srgb': [srgb(value) for value in means],
            'gpu_std_linear': [math.sqrt(max(0., square / len(pixels) - mean * mean))
                               for square, mean in zip(squares, means)],
            'black_pixels': black, 'pixel_count': len(pixels)}


def main():
    report = {'success': False, 'rows': [], 'resolution': SIZE,
              'tolerance_srgb_bytes': TOLERANCE,
              'method': 'Deferred SceneCapture SCS_BASE_COLOR, equal-area UV0 plane, RGBA16F raw linear readback; linear mean then IEC sRGB encode',
              'variance_is_diagnostic_only': True,
              'limitations': '256px sampling includes texture compression, mip filtering and GBuffer quantization. Zero sampled BaseColor variance is not by itself a failure; source iron was already flat in earlier GPU baselines. This does not test final Lit readability, occlusion boundaries or full graph connectivity.',
              'packages_saved': False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'BaseColor').mkdir(exist_ok=True)
    actors = []
    original_actors = None
    original_cat = None
    world = None
    collection = None
    ea = u.get_editor_subsystem(u.EditorActorSubsystem)
    try:
        assert u.SystemLibrary.is_unattended(), 'Disposable unattended process required'
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
        world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
        original_actors = {actor.get_path_name() for actor in ea.get_all_level_actors()}
        cases = select_cases(report)
        collection = u.load_asset('/Game/Characters/BlackCat/Materials/MPC_CatOcclusion')
        assert collection
        # World instance only, restored in finally. Do not edit the collection asset.
        original_cat = u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition')
        u.MaterialLibrary.set_vector_parameter_value(world, collection, 'CatPosition', u.LinearColor(0, 0, 0, 0))
        assert abs(u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition').a) < 1.e-6
        plane = ea.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, 0, 10000), transient=True)
        actors.append(plane)
        plane.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane.Plane'))
        plane.static_mesh_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        camera = ea.spawn_actor_from_class(u.SceneCapture2D, u.Vector(0, 0, 10100), u.Rotator(pitch=-90), transient=True)
        actors.append(camera)
        capture = camera.get_component_by_class(u.SceneCaptureComponent2D)
        capture.set_editor_property('capture_every_frame', False)
        capture.set_editor_property('capture_on_movement', False)
        capture.set_editor_property('projection_type', u.CameraProjectionMode.ORTHOGRAPHIC)
        capture.set_editor_property('ortho_width', 100.)
        capture.set_editor_property('capture_source', u.SceneCaptureSource.SCS_BASE_COLOR)
        capture.set_editor_property('primitive_render_mode', u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        capture.clear_show_only_components()
        capture.show_only_component(plane.static_mesh_component)
        target = u.RenderingLibrary.create_render_target2d(world, SIZE, SIZE, u.TextureRenderTargetFormat.RTF_RGBA16F, u.LinearColor(0, 0, 0, 0), False)
        capture.set_editor_property('texture_target', target)
        for case in cases:
            material = u.load_asset(case['material'])
            assert isinstance(material, u.MaterialInstanceConstant), case['material']
            plane.static_mesh_component.set_material(0, material)
            assert u.CatrunAuthoringLibrary.finish_asset_compilation()
            capture.capture_scene()
            pixels = u.RenderingLibrary.read_render_target_raw_pixel_area(world, target, 0, 0, SIZE, SIZE, False)
            row = dict(case, **measure(pixels))
            row['max_srgb_error'] = max(abs(a - b) for a, b in zip(row['gpu_representative_srgb'], row['target_srgb']))
            row['passed'] = row['max_srgb_error'] <= TOLERANCE and row['black_pixels'] == 0
            report['rows'].append(row)
            u.RenderingLibrary.export_render_target(world, target, str(OUT / 'BaseColor'), case['kind'] + '_' + case['role'] + '.hdr')
            (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print('GOTHIC_BASECOLOR_GPU', case['kind'], case['role'], row['gpu_representative_srgb'], row['max_srgb_error'])
        report['success'] = len(report['rows']) == report['expected_case_count'] and all(row['passed'] for row in report['rows'])
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        try:
            if original_cat is not None:
                u.MaterialLibrary.set_vector_parameter_value(world, collection, 'CatPosition', original_cat)
                restored = u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition')
                report['world_mpc_restored'] = max(abs(a - b) for a, b in zip(color(original_cat), color(restored))) < 1.e-6
            for actor in reversed(actors):
                if actor:
                    ea.destroy_actor(actor)
            if original_actors is not None:
                report['original_actor_set_preserved'] = original_actors == {actor.get_path_name() for actor in ea.get_all_level_actors()}
            report['success'] = report['success'] and report.get('world_mpc_restored', False) and report.get('original_actor_set_preserved', False)
        except Exception:
            report['cleanup_error'] = traceback.format_exc()
            report['success'] = False
            raise
        finally:
            (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return report


if __name__ == '__main__':
    main()
