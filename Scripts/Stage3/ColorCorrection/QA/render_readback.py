"""GPU BaseColor verification in a disposable UE commandlet, never the live editor.

Root must schedule with -run=pythonscript -AllowCommandletRendering -RenderOffscreen
-d3d11. Does not save packages. Only transient test actors are created/destroyed.
All authoritative scene actors and existing assets remain untouched.
"""
import json
import importlib.util
import math
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3MaterialCorrection20261125/QA'
MANIFEST = ROOT / 'Saved/Stage3MaterialCorrection20261125/Materials/calibration.json'
DEST = '/Game/Environment/Stage3/ColorCorrection_20261125'
REPORT = {'method': 'Deferred SceneCapture SCS_BASE_COLOR -> RGBA16F -> raw linear pixel readback; equal-area UV0 plane',
          'tolerance_srgb_bytes': 2.5, 'resolution': 256, 'rows': [], 'success': False,
          'limitations': '256px UV-plane samples imported GPU texture/mips, not every source mip0 texel; GBuffer/compression quantization included.'}
OUT.mkdir(parents=True, exist_ok=True)


def srgb(v):
    return 255 * (12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055)


def main():
    assert u.SystemLibrary.is_unattended(), 'Disposable unattended process required'
    assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
    spec = importlib.util.spec_from_file_location('stage3_qa', ROOT / 'Scripts/Stage3/ColorCorrection/verify.py')
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    qa.loaded_materials()
    manifest = json.loads(MANIFEST.read_text(encoding='utf8'))
    ea = u.get_editor_subsystem(u.EditorActorSubsystem)
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    original_actors = {a.get_path_name() for a in ea.get_all_level_actors()}
    test_actors = []
    try:
        plane = ea.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, 0, 10000), transient=True)
        test_actors.append(plane)
        plane.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane.Plane'))
        plane.static_mesh_component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        camera = ea.spawn_actor_from_class(u.SceneCapture2D, u.Vector(0, 0, 10100), u.Rotator(pitch=-90), transient=True)
        test_actors.append(camera)
        capture = camera.get_component_by_class(u.SceneCaptureComponent2D)
        capture.set_editor_property('capture_every_frame', False)
        capture.set_editor_property('capture_on_movement', False)
        capture.set_editor_property('projection_type', u.CameraProjectionMode.ORTHOGRAPHIC)
        capture.set_editor_property('ortho_width', 100.0)
        capture.set_editor_property('capture_source', u.SceneCaptureSource.SCS_BASE_COLOR)
        capture.set_editor_property('primitive_render_mode', u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        capture.clear_show_only_components()
        capture.show_only_component(plane.static_mesh_component)
        target = u.RenderingLibrary.create_render_target2d(world, 256, 256, u.TextureRenderTargetFormat.RTF_RGBA16F, u.LinearColor(0,0,0,0), False)
        # RGBA16F's resource GetDisplayGamma() is already 1.0. The internal
        # bForceLinearGamma flag is not exposed as a Python editor property.
        capture.set_editor_property('texture_target', target)
        # Stage3 materials are referenced from production assignment report;
        # discover actual saved MI assets so naming cannot silently diverge.
        application = json.loads((MANIFEST.parent / 'application_report.json').read_text(encoding='utf8'))
        assert application['success']
        for material_path, instance_row in application['instances'].items():
            name = instance_row['calibration']
            row = manifest['calibrations'][name]
            assert material_path.startswith(DEST + '/')
            material = u.load_asset(material_path)
            assert isinstance(material, u.MaterialInstanceConstant), material_path
            plane.static_mesh_component.set_material(0, material)
            assert u.CatrunAuthoringLibrary.finish_asset_compilation()
            capture.capture_scene()
            # PixelArea uses an exclusive maximum, unlike single-pixel APIs.
            pixels = u.RenderingLibrary.read_render_target_raw_pixel_area(world, target, 0, 0, 256, 256, False)
            assert len(pixels) == 256 * 256, len(pixels)
            sums = [0.0, 0.0, 0.0]
            squares = [0.0, 0.0, 0.0]
            black = 0
            for p in pixels:
                channels = [p.r, p.g, p.b]
                black += max(channels) < 1e-6
                for c, value in enumerate(channels):
                    assert math.isfinite(value)
                    sums[c] += value
                    squares[c] += value * value
            mean = [s / len(pixels) for s in sums]
            std = [math.sqrt(max(0.0, ss / len(pixels) - m * m)) for ss, m in zip(squares, mean)]
            rgb = [srgb(m) for m in mean]
            error = max(abs(a-b) for a,b in zip(rgb, row['target_srgb']))
            result = {'calibration': name, 'material': material.get_path_name(), 'role': row['role'],
                      'target_srgb': row['target_srgb'], 'gpu_mean_linear': mean,
                      'gpu_representative_srgb': rgb, 'gpu_std_linear': std,
                      'max_srgb_error': error, 'black_pixels': black,
                      'passed': error <= REPORT['tolerance_srgb_bytes'] and black == 0 and max(std) > 0}
            REPORT['rows'].append(result)
            u.RenderingLibrary.export_render_target(world, target, str(OUT / 'BaseColor'), material.get_name() + '.hdr')
            (OUT / 'basecolor_gpu.json').write_text(json.dumps(REPORT, indent=2), encoding='utf8')
            print('STAGE3_BASECOLOR_GPU', name, rgb, error)
        REPORT['success'] = bool(REPORT['rows']) and all(r['passed'] for r in REPORT['rows'])
    finally:
        for actor in reversed(test_actors):
            ea.destroy_actor(actor)
        REPORT['original_actor_set_preserved'] = original_actors == {a.get_path_name() for a in ea.get_all_level_actors()}
        REPORT['success'] = REPORT['success'] and REPORT['original_actor_set_preserved']


try:
    (OUT / 'BaseColor').mkdir(exist_ok=True)
    main()
except Exception:
    REPORT['error'] = traceback.format_exc()
    raise
finally:
    (OUT / 'basecolor_gpu.json').write_text(json.dumps(REPORT, indent=2), encoding='utf8')
