"""Saved Stage3 cutaway GPU regression; import is inert, root executes main().

Run in a disposable unattended editor with -SaveToUserDir and preferably
-run=pythonscript -AllowCommandletRendering -RenderOffscreen -d3d11.
CATRUN_STAGE3_FIX_PHASE=before|after selects expectations/output (default after).
CATRUN_STAGE3_FIX_PASS=04 selects a new run suffix (default 04).
CATRUN_STAGE3_GPU_OUTPUT_DIR can override the output folder, absolute or relative
to Saved/Stage3ReadabilityPushFix20261125. Existing reports are never overwritten.
CATRUN_STAGE3_GPU_QUIT_EDITOR=1 requests QUIT_EDITOR on SUCCESS only, for a
disposable full editor. Failure raises so a Python commandlet returns nonzero.
No assets/maps are saved or reassigned. Only a transient capture and the restored
world-instance CatPosition MPC parameter are changed.
"""
import hashlib
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

SIZE = 512
CAT = (150., -110., 26.2)
CAMERA = (297.79, 37.79, 435.78)
ROTATION = (-55., -135., 0.)  # pitch, yaw, roll
MPC = '/Game/Characters/BlackCat/Materials/MPC_CatOcclusion'
CASES = (
    ('S3_Wall_0078', 'background_false_positive', 'opaque'),
    ('S3_Wall_0079', 'foreground', 'cut'),
)


def rgba(value):
    return [value.r, value.g, value.b, value.a]


def xyz(value):
    return [value.x, value.y, value.z]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projection_evidence():
    """UE 5.8 native BuildOrthoMatrix uses this reversed-Z row-vector matrix.

    Local engine source, not CameraComponent's unavailable SceneCapture fields:
    SceneCaptureComponent2D.h:93-100 exposes the custom near-plane override.
    SceneCaptureComponent.h:154-156 exposes MaxViewDistanceOverride.
    SceneCaptureRendering.cpp:1213-1224 feeds both to BuildOrthoMatrix;
    lines 546-567 and Core/Public/Math/OrthoMatrix.h:65-70 define its matrix.
    Disabling bUpdateOrthoPlanes also bypasses the view-origin/plane adjustment
    at SceneCaptureRendering.cpp:887-889. No custom projection matrix required.
    """
    near, far, half_width, half_height = -2000., 10000., 450., 450.
    z_scale, z_offset = 1. / (far-near), -near
    rows = [[1./half_width, 0., 0., 0.], [0., 1./half_height, 0., 0.],
            [0., 0., -z_scale, 0.], [0., 0., 1.-z_offset*z_scale, 1.]]
    near_depth = near * rows[2][2] + rows[3][2]
    far_depth = far * rows[2][2] + rows[3][2]
    assert abs(near_depth - 1.) < 1.e-12 and abs(far_depth) < 1.e-12
    return {'api': 'native SceneCapture custom near override + max view distance',
            'source_engine': 'UE_5.8 local Engine/Source',
            'source_references': ['Runtime/Engine/Classes/Components/SceneCaptureComponent2D.h:93-100',
                                  'Runtime/Engine/Classes/Components/SceneCaptureComponent.h:154-156',
                                  'Runtime/Renderer/Private/SceneCaptureRendering.cpp:1213-1224',
                                  'Runtime/Renderer/Private/SceneCaptureRendering.cpp:546-567',
                                  'Runtime/Core/Public/Math/OrthoMatrix.h:65-70'],
            'expected_reversed_z_matrix_rows': rows,
            'expected_near_ndc_depth': near_depth,
            'expected_far_ndc_depth': far_depth,
            'custom_projection_matrix_used': False}


def measure(pixels):
    """Count raw-linear nonblack coverage, independent of exposure/tonemapping."""
    assert len(pixels) == SIZE * SIZE, len(pixels)
    occupied = set()
    total = [0., 0., 0.]
    for index, pixel in enumerate(pixels):
        values = (pixel.r, pixel.g, pixel.b)
        assert all(math.isfinite(value) and value >= 0 for value in values), values
        if max(values) >= 1.e-6:
            occupied.add(index)
        for channel, value in enumerate(values):
            total[channel] += value
    return {
        'raw_nonblack_pixels': len(occupied),
        'raw_black_pixels': len(pixels) - len(occupied),
        'total_pixels': len(pixels),
        'raw_mean_linear': [value / len(pixels) for value in total],
    }, occupied


def evaluate(baseline, active, baseline_mask, active_mask, expectation):
    base_count = baseline['raw_nonblack_pixels']
    active_count = active['raw_nonblack_pixels']
    changed_pixels = len(baseline_mask.symmetric_difference(active_mask))
    # A black/offscreen baseline cannot establish that the shader removed a wall.
    valid = base_count >= 16
    tolerance = max(4, int(base_count * .005))
    preserved = valid and changed_pixels <= tolerance
    removed = valid and active_count == 0
    return {
        'valid_visible_baseline': valid,
        'minimum_baseline_pixels': 16,
        'coverage_symmetric_difference_pixels': changed_pixels,
        'opaque_coverage_tolerance_pixels': tolerance,
        'active_to_baseline_nonblack_ratio': active_count / base_count if base_count else None,
        'opaque_coverage_preserved': preserved,
        'fully_cut': removed,
        'expected': expectation,
        'passed': preserved if expectation == 'opaque' else removed,
    }


def snapshot_component(actor, component):
    center, extent = actor.get_actor_bounds(False, False)
    cpd = list(component.get_editor_property('custom_primitive_data').get_editor_property('data'))
    materials = []
    for slot in range(component.get_num_materials()):
        material = component.get_material(slot)
        assert isinstance(material, u.MaterialInstanceConstant), (actor.get_actor_label(), slot)
        materials.append({
            'slot': slot,
            'instance': material.get_path_name(),
            'base_material': material.get_base_material().get_path_name(),
            'camera_clear_radius': u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material, 'CameraClearRadius'),
            'source_metadata': u.EditorAssetLibrary.get_metadata_tag(material, 'Stage3ReadabilitySource'),
        })
    assert materials, actor.get_actor_label()
    return {
        'actor_path': actor.get_path_name(),
        'location': xyz(actor.get_actor_location()),
        'bounds_center': xyz(center),
        'bounds_extent': xyz(extent),
        'mesh': component.static_mesh.get_path_name() if component.static_mesh else None,
        'custom_primitive_data': cpd,
        'cutaway_group_center': cpd[16:20],
        'cutaway_group_extent': cpd[20:24],
        'materials': materials,
    }


def main():
    phase = os.environ.get('CATRUN_STAGE3_FIX_PHASE', 'after').lower()
    assert phase in ('before', 'after'), phase
    root = Path(u.Paths.project_dir()).resolve()
    run = root / 'Saved/Stage3ReadabilityPushFix20261125'
    pass_id = os.environ.get('CATRUN_STAGE3_FIX_PASS', '04')
    assert all(char.isalnum() or char in '_-' for char in pass_id), pass_id
    folder = os.environ.get('CATRUN_STAGE3_GPU_OUTPUT_DIR', 'GPU_' + phase + pass_id)
    out = Path(folder)
    out = (out if out.is_absolute() else run / out).resolve()
    assert out.is_relative_to(run.resolve()), 'GPU output must stay under ' + str(run)
    assert not (out / 'report.json').exists(), 'Preserve existing evidence; select a new GPU output folder: ' + str(out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'success': False,
        'phase': phase,
        'pass': pass_id,
        'output_directory': str(out),
        'rows': [],
        'scope': 'Representative regression for two GPU-observable walls at the entrance: background Wall0078 restored, foreground Wall0079 still cut. Not a four-wall GPU acceptance test.',
        'excluded_gpu_cases': [
            {'actor': label, 'reason': 'GPU_after03 alpha=0 baseline had zero nonblack pixels in this fixed view; not GPU-validated. Remains outside this GPU test, for separate CPU checks.',
             'prior_opaque_baseline_nonblack_pixels': 0}
            for label in ('S3_Wall_0001', 'S3_Wall_0002')],
        'resolution': [SIZE, SIZE],
        'cat_position': list(CAT),
        'camera_position': list(CAMERA),
        'camera_rotation_pitch_yaw_roll': list(ROTATION),
        'orthographic_width': 900.,
        'ortho_near_far': [-2000., 10000.],
        'projection': projection_evidence(),
        'compilation_barriers': [],
        'method': 'Actual saved Stage3 mesh + material instance + custom primitive data; one actor exclusively shown per deferred SCS_BASE_COLOR RGBA16F capture; raw linear RGB nonblack coverage at CatPosition.a=0 versus 1.',
        'limitations': 'A fixed entrance view and two GPU-observable saved walls only. GPU_after03 recorded zero alpha=0 baseline pixels for Wall0001 and Wall0002; one-sided rendering/culling or view visibility makes those cases invalid, so they are excluded without claiming GPU validation. Their CPU checks are separate. Whole-component cutaway is binary even for partial silhouette intersection. Opaque means preserved BaseColor coverage, not final Lit beauty or all camera positions. No shadows, gameplay, enemy visibility, interaction, or statue-push behavior is validated. A baseline with fewer than 16 nonblack pixels remains invalid. Before phase diagnoses the known Wall0078 false-positive, not a fixed-state acceptance pass.',
        'packages_saved': False,
    }
    actor_subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    world = collection = original_cat = capture_actor = target = None
    original_actor_paths = None
    initial_snapshots = {}
    protected_files = {}
    command_line = u.SystemLibrary.get_command_line()
    disposable = u.SystemLibrary.is_unattended() and '-savetouserdir' in command_line.lower()
    try:
        assert disposable, 'Requires a disposable unattended -SaveToUserDir process'
        editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        assert not editor.get_game_world(), 'Run against the saved editor world, not PIE'
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
        world = editor.get_editor_world()
        original_actors = list(actor_subsystem.get_all_level_actors())
        original_actor_paths = {actor.get_path_name() for actor in original_actors}
        by_label = {}
        for actor in original_actors:
            by_label.setdefault(actor.get_actor_label(), []).append(actor)
        saved_files = [root / 'Content/Maps/Stage3.umap']
        saved_files += list((root / 'Content/Environment/Stage3/GothicRevision_20261125/CameraReadability').rglob('*.uasset'))
        protected_files = {str(path): digest(path) for path in saved_files}
        report['saved_map_sha256'] = protected_files[str(root / 'Content/Maps/Stage3.umap')]
        cases = []
        for label, role, after_expectation in CASES:
            assert len(by_label.get(label, [])) == 1, ('Missing/duplicate actor', label)
            actor = by_label[label][0]
            component = actor.get_component_by_class(u.StaticMeshComponent)
            assert component, label
            initial_snapshots[label] = snapshot_component(actor, component)
            cases.append((label, role, after_expectation, actor, component))
        collection = u.load_asset(MPC)
        assert collection, MPC
        original_cat = u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition')
        capture_actor = actor_subsystem.spawn_actor_from_class(
            u.SceneCapture2D, u.Vector(*CAMERA),
            u.Rotator(pitch=ROTATION[0], yaw=ROTATION[1], roll=ROTATION[2]), transient=True)
        assert capture_actor
        capture = capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
        settings = {
            'capture_every_frame': False,
            'capture_on_movement': False,
            'projection_type': u.CameraProjectionMode.ORTHOGRAPHIC,
            'ortho_width': 900.,
            'auto_calculate_ortho_planes': False,
            'update_ortho_planes': False,
            # UE 5.8 SceneCaptureRendering.cpp:1213-1224 supports these for
            # orthographic projection. CameraComponent's ortho_*_clip_plane
            # properties do not exist on SceneCaptureComponent2D.
            'override_custom_near_clipping_plane': True,
            'custom_near_clipping_plane': -2000.,
            'max_view_distance_override': 10000.,
            'use_custom_projection_matrix': False,
            'capture_source': u.SceneCaptureSource.SCS_BASE_COLOR,
            'primitive_render_mode': u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST,
        }
        for name, value in settings.items():
            capture.set_editor_property(name, value)
            assert capture.get_editor_property(name) == value, name
        report['projection']['native_property_readback'] = {
            name: capture.get_editor_property(name) for name in (
                'ortho_width', 'auto_calculate_ortho_planes', 'update_ortho_planes',
                'override_custom_near_clipping_plane', 'custom_near_clipping_plane',
                'max_view_distance_override', 'use_custom_projection_matrix')}
        target = u.RenderingLibrary.create_render_target2d(
            world, SIZE, SIZE, u.TextureRenderTargetFormat.RTF_RGBA16F,
            u.LinearColor(0, 0, 0, 0), False)
        capture.set_editor_property('texture_target', target)
        # The project helper is commandlet-only (CatrunAuthoringLibrary.cpp:13).
        # Use the editor-supported synchronous command in either execution mode:
        # AssetCompilingManager.cpp:46-54 supplies FinishAllCompilation; the
        # console name is registered by AsyncCompilationHelpers.cpp:386-389.
        barrier_started = time.monotonic()
        u.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
        report['compilation_barriers'].append({
            'reason': 'saved Stage3 and capture target ready, before GPU readback',
            'method': 'synchronous editor console command',
            'command': 'Editor.AsyncAssetCompilationFinishAll',
            'wall_seconds': time.monotonic() - barrier_started,
            'returned': True,
            'commandlet_only_project_helper_used': False,
        })
        for label, role, after_expectation, actor, component in cases:
            capture.clear_show_only_components()
            capture.show_only_component(component)
            row = {'actor': label, 'role': role, 'saved_component': initial_snapshots[label]}
            masks = {}
            for alpha, name in ((0., 'opaque_baseline'), (1., 'cutaway_enabled')):
                u.MaterialLibrary.set_vector_parameter_value(world, collection, 'CatPosition', u.LinearColor(*CAT, alpha))
                readback = u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition')
                assert max(abs(a-b) for a,b in zip(rgba(readback), list(CAT) + [alpha])) < 1.e-4
                # A synchronous raw readback flushes the capture; repeat once to
                # avoid treating first-use shader/scene initialization as a cut.
                for _ in range(2):
                    capture.capture_scene()
                    pixels = u.RenderingLibrary.read_render_target_raw_pixel_area(world, target, 0, 0, SIZE, SIZE, False)
                row[name], masks[name] = measure(pixels)
                u.RenderingLibrary.export_render_target(world, target, str(out), label + '_' + name + '.hdr')
            expectation = 'cut' if phase == 'before' and label == 'S3_Wall_0078' else after_expectation
            row.update(evaluate(row['opaque_baseline'], row['cutaway_enabled'], masks['opaque_baseline'], masks['cutaway_enabled'], expectation))
            report['rows'].append(row)
            (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print('STAGE3_OCCLUSION_GPU', phase, label, row['opaque_baseline']['raw_nonblack_pixels'], row['cutaway_enabled']['raw_nonblack_pixels'], row['passed'])
        report['success'] = len(report['rows']) == len(CASES) and all(row['passed'] for row in report['rows'])
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        cleanup_errors = []
        if original_cat is not None:
            try:
                u.MaterialLibrary.set_vector_parameter_value(world, collection, 'CatPosition', original_cat)
                restored = u.MaterialLibrary.get_vector_parameter_value(world, collection, 'CatPosition')
                report['world_mpc_restored'] = max(abs(a-b) for a,b in zip(rgba(original_cat), rgba(restored))) < 1.e-6
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        if capture_actor:
            try:
                actor_subsystem.destroy_actor(capture_actor)
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        try:
            if original_actor_paths is not None:
                remaining = list(actor_subsystem.get_all_level_actors())
                report['original_actor_set_preserved'] = original_actor_paths == {actor.get_path_name() for actor in remaining}
                remaining_by_label = {actor.get_actor_label(): actor for actor in remaining}
                report['saved_components_preserved'] = all(
                    snapshot_component(remaining_by_label[label], remaining_by_label[label].get_component_by_class(u.StaticMeshComponent)) == snapshot
                    for label, snapshot in initial_snapshots.items())
            report['protected_disk_files_unchanged'] = bool(protected_files) and all(Path(path).exists() and digest(Path(path)) == sha for path, sha in protected_files.items())
        except Exception:
            cleanup_errors.append(traceback.format_exc())
        if cleanup_errors:
            report['cleanup_errors'] = cleanup_errors
        report['success'] = report['success'] and not cleanup_errors and all(report.get(name, False) for name in (
            'world_mpc_restored', 'original_actor_set_preserved', 'saved_components_preserved', 'protected_disk_files_unchanged'))
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    assert report['success'], 'Stage3 GPU occlusion failed; see ' + str(out / 'report.json')
    if os.environ.get('CATRUN_STAGE3_GPU_QUIT_EDITOR') == '1':
        assert disposable
        u.SystemLibrary.execute_console_command(world, 'QUIT_EDITOR')
    return report


if __name__ == '__main__':
    main()
