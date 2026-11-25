"""Import and cold-audit the elevator delivery without loading a gameplay map."""
import csv
import json
import math
import os
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
SOURCE = Path(os.environ.get(
    'CATRUN_ELEVATOR_SOURCE',
    'C:/Users/whghk/Desktop/CastleKit/Stage2To3_Elevator/Production01_20261125',
))
ANIM_SOURCE = ROOT / 'SourceArt/Cinematics/ElevatorCat/Production01_20261125'
DEST = '/Game/Environment/ElevatorTransition'
ANIM_DEST = '/Game/Cinematics/ElevatorTransition/Animations'
CAT = '/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final'
OUT = ROOT / 'Saved/ElevatorTransition'
AUDIT = os.environ.get('CATRUN_ELEVATOR_COLD_AUDIT') == '1'
EA = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
ML = u.MaterialEditingLibrary
REPORT = {
    'cold_audit': AUDIT,
    'meshes': {},
    'textures': {},
    'materials': {},
    'animations': {},
    'errors': [],
}


def write_report():
    OUT.mkdir(parents=True, exist_ok=True)
    name = 'cold_import_audit.json' if AUDIT else 'import_report.json'
    (OUT / name).write_text(json.dumps(REPORT, indent=2), encoding='utf-8')


def apply_properties(obj, values):
    for key, value in values.items():
        obj.set_editor_property(key, value)


def asset(file, folder, name, options=None):
    path = f'{folder}/{name}'
    obj = EA.load_asset(path) if EA.does_asset_exist(path) else None
    if obj:
        return obj
    if AUDIT:
        raise RuntimeError(f'Missing saved package {path}')
    if not file.is_file():
        raise RuntimeError(f'Missing delivery file {file}')
    task = u.AssetImportTask()
    task.filename = str(file)
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.replace_existing = False
    if options:
        task.options = options
    AT.import_asset_tasks([task])
    obj = EA.load_asset(path)
    if not obj:
        raise RuntimeError(f'Failed to import {file}: {task.imported_object_paths}')
    return obj


def save(obj):
    if not EA.save_loaded_asset(obj, False):
        raise RuntimeError(f'Failed to save {obj.get_path_name()}')


def vec(value):
    return [value.x, value.y, value.z]


def import_material(name):
    path = f'{DEST}/Materials/{name}'
    existing = EA.does_asset_exist(path)
    if AUDIT and not existing:
        raise RuntimeError(f'Missing saved package {path}')
    material = (EA.load_asset(path) if existing else
                AT.create_asset(name, f'{DEST}/Materials', u.Material, u.MaterialFactoryNew()))
    if name == 'M_E23_LanternEmission':
        if not existing:
            node = ML.create_material_expression(material, u.MaterialExpressionConstant3Vector, -300, 0)
            node.set_editor_property('constant', u.LinearColor(2.0, 0.68, 0.09, 1.0))
            ML.connect_material_property(node, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
            base = ML.create_material_expression(material, u.MaterialExpressionConstant3Vector, -300, 150)
            base.set_editor_property('constant', u.LinearColor(0.75, 0.32, 0.065, 1.0))
            ML.connect_material_property(base, '', u.MaterialProperty.MP_BASE_COLOR)
        textures = {}
    else:
        prefix = {
            'M_Stage2_Floors_Shared': 'Reuse_T_Stage2_Floors',
            'M_Stage2_Walls_Shared': 'Reuse_T_Stage2_Walls',
        }.get(name, 'T_' + name.removeprefix('M_'))
        textures = {}
        texture_channels = [
            ('BaseColor', u.MaterialSamplerType.SAMPLERTYPE_COLOR,
             [('RGB', u.MaterialProperty.MP_BASE_COLOR)]),
            ('Normal_DX', u.MaterialSamplerType.SAMPLERTYPE_NORMAL,
             [('RGB', u.MaterialProperty.MP_NORMAL)]),
            ('ORM', u.MaterialSamplerType.SAMPLERTYPE_MASKS,
             [('R', u.MaterialProperty.MP_AMBIENT_OCCLUSION),
              ('G', u.MaterialProperty.MP_ROUGHNESS),
              ('B', u.MaterialProperty.MP_METALLIC)]),
        ]
        for index, (suffix, sampler, channels) in enumerate(texture_channels):
            tex_name = f'{prefix}_{suffix}'
            tex = asset(SOURCE / 'Textures' / f'{tex_name}.png', f'{DEST}/Textures', tex_name)
            properties = {'srgb': suffix == 'BaseColor'}
            if suffix == 'Normal_DX':
                properties.update(compression_settings=u.TextureCompressionSettings.TC_NORMALMAP,
                                  flip_green_channel=False)
            elif suffix == 'ORM':
                properties['compression_settings'] = u.TextureCompressionSettings.TC_MASKS
            if AUDIT:
                for key, value in properties.items():
                    if tex.get_editor_property(key) != value:
                        raise RuntimeError(f'{tex_name} has unexpected {key}')
            elif not existing or any(tex.get_editor_property(key) != value for key, value in properties.items()):
                apply_properties(tex, properties)
                save(tex)
            textures[suffix] = tex.get_path_name()
            REPORT['textures'][tex_name] = textures[suffix]
            if not existing:
                node = ML.create_material_expression(
                    material, u.MaterialExpressionTextureSample, -550, index * 250)
                node.set_editor_property('texture', tex)
                node.set_editor_property('sampler_type', sampler)
                for channel, prop in channels:
                    if not ML.connect_material_property(node, channel, prop):
                        raise RuntimeError(f'Failed to connect {tex_name} {channel}')
    if not AUDIT and not existing:
        ML.recompile_material(material)
        save(material)
    REPORT['materials'][name] = {'path': material.get_path_name(), 'textures': textures}
    return material


def mesh_options():
    options = u.FbxImportUI()
    apply_properties(options, {
        'automated_import_should_detect_type': False,
        'mesh_type_to_import': u.FBXImportType.FBXIT_STATIC_MESH,
        'import_as_skeletal': False,
        'import_materials': False,
        'import_textures': False,
    })
    apply_properties(options.static_mesh_import_data, {
        'combine_meshes': True,
        'auto_generate_collision': False,
        'one_convex_hull_per_ucx': True,
        'convert_scene': True,
        'convert_scene_unit': True,
        'force_front_x_axis': False,
        'generate_lightmap_u_vs': False,
        'import_uniform_scale': 1.0,
        'normal_import_method': u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
    })
    return options


def import_mesh(row, materials):
    name = row['name']
    saved_before = EA.does_asset_exist(f'{DEST}/Meshes/{name}')
    mesh = asset(SOURCE / 'Assets' / name / f'{name}.fbx', f'{DEST}/Meshes', name, mesh_options())
    bindings = {}
    for index, slot in enumerate(mesh.get_editor_property('static_materials')):
        slot_name = str(slot.get_editor_property('material_slot_name')).split('.')[0]
        if slot_name not in row['materials']:
            raise RuntimeError(f'{name}: unmapped material slot {slot_name}')
        material = materials[slot_name]
        if not AUDIT and not saved_before:
            mesh.set_material(index, material)
        if slot.get_editor_property('material_interface') != material and (AUDIT or saved_before):
            raise RuntimeError(f'{name}: saved material binding differs for {slot_name}')
        bindings[slot_name] = material.get_path_name()
    if set(bindings) != set(row['materials']):
        raise RuntimeError(f'{name}: material list differs from manifest')
    body = mesh.get_editor_property('body_setup')
    geo = body.get_editor_property('agg_geom')
    shape_counts = {
        key: len(geo.get_editor_property(key))
        for key in ['box_elems', 'convex_elems', 'sphere_elems', 'sphyl_elems']
    }
    expected_collision = len(row['collision_names'])
    actual_collision = sum(shape_counts.values())
    if not AUDIT and not saved_before:
        apply_properties(mesh, {'light_map_coordinate_index': 1, 'light_map_resolution': 64})
        if actual_collision:
            body.set_editor_property('collision_trace_flag', u.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
        else:
            body.set_editor_property('collision_trace_flag', u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        save(mesh)
    measured = mesh.get_bounding_box()
    actual = [vec(measured.min), vec(measured.max)]
    px, py, pz = row['pivot']
    lo, hi = row['bounds_m']
    expected = [
        [(lo[0] - px) * 100, (py - hi[1]) * 100, (lo[2] - pz) * 100],
        [(hi[0] - px) * 100, (py - lo[1]) * 100, (hi[2] - pz) * 100],
    ]
    error = max(abs(a - b) for values in zip(actual, expected) for a, b in zip(*values))
    REPORT['meshes'][name] = {
        'path': mesh.get_path_name(),
        'mode': row.get('mode'),
        'pivot_cm': [px * 100, -py * 100, pz * 100],
        'bounds_cm': actual,
        'expected_bounds_cm': expected,
        'max_bounds_error_cm': error,
        'material_map': bindings,
        'shape_counts': shape_counts,
        'expected_ucx': expected_collision,
        'collision_trace_flag': str(body.get_editor_property('collision_trace_flag')),
    }
    if error > 0.05:
        REPORT['errors'].append(f'{name}: bounds error {error:g} cm')
    if actual_collision != expected_collision:
        REPORT['errors'].append(f'{name}: {actual_collision} collision shapes, expected {expected_collision}')


def extract_root_track(animation, frames, fps):
    return [u.AnimationLibrary.extract_root_track_transform(animation, frame / fps) for frame in range(frames)]


def import_animation(clip, fps, skeleton, source_roots, idle_pose, pose_options):
    options = u.FbxImportUI()
    apply_properties(options, {
        'automated_import_should_detect_type': False,
        'import_mesh': False,
        'import_animations': True,
        'import_materials': False,
        'import_textures': False,
        'mesh_type_to_import': u.FBXImportType.FBXIT_ANIMATION,
        'skeleton': skeleton,
    })
    apply_properties(options.anim_sequence_import_data, {
        'import_uniform_scale': 100.0,
        'convert_scene': True,
        'convert_scene_unit': True,
        'force_front_x_axis': False,
        'use_default_sample_rate': False,
        'custom_sample_rate': fps,
    })
    name = clip['action']
    file = ANIM_SOURCE / clip.get('fbx', f'FBX/{name}.fbx')
    animation = asset(file, ANIM_DEST, name, options)
    if not isinstance(animation, u.AnimSequence):
        raise RuntimeError(f'{name}: unexpected package type')
    if not AUDIT:
        apply_properties(animation, {'enable_root_motion': False, 'force_root_lock': False})
    if animation.get_editor_property('skeleton') != skeleton:
        raise RuntimeError(f'{name}: skeleton mismatch')
    if animation.get_editor_property('enable_root_motion') or animation.get_editor_property('force_root_lock'):
        raise RuntimeError(f'{name}: root trajectory must stay in the pose')
    length = animation.get_play_length()
    frames = clip['frames'][1] - clip['frames'][0] + 1
    seconds = (frames - 1) / fps
    if abs(length - seconds) > 0.001:
        REPORT['errors'].append(f'{name}: duration {length:g}s, expected {seconds:g}s')
    tracks = [str(track) for track in u.AnimationLibrary.get_animation_track_names(animation)]
    if 'root' not in tracks:
        raise RuntimeError(f'{name}: no root bone track')
    expected_points = source_roots.get(name)
    if not expected_points or len(expected_points) != frames:
        raise RuntimeError(f'{name}: per-frame root source count differs from import count')
    root = extract_root_track(animation, frames, fps)
    idle_root = u.AnimPoseExtensions.get_bone_pose(idle_pose, 'root', u.AnimPoseSpaces.LOCAL)
    expected_root_scale = vec(idle_root.scale3d)
    if not AUDIT:
        # Animation-only FBX may arrive with Blender meter translations and a unit-scale
        # root. The existing Unreal skeleton's root carries the meter-to-centimeter
        # scale, so only its root track must be normalized to match the original clips.
        points = [vec(transform.translation) for transform in root]
        current_scale = vec(root[0].scale3d)
        unscaled_track = max(math.dist(a, [100 * v for v in b])
                             for a, b in zip(expected_points, points)) <= 0.25
        use_authored_peek_track = clip.get('id') == 'C06' and not unscaled_track
        unit_root_scale = math.dist(current_scale, [1.0, 1.0, 1.0]) <= 0.01
        if unit_root_scale and (unscaled_track or use_authored_peek_track):
            # PeekDown's animation-only import resamples the moving root differently.
            # Restore its authored 30 Hz translation samples from the delivery CSV.
            translations = ([u.Vector(*point) for point in expected_points] if use_authored_peek_track
                            else [transform.translation * 100 for transform in root])
            controller = animation.get_editor_property('controller')
            controller.open_bracket('Match elevator root track to the BlackCat skeleton')
            try:
                if not controller.set_bone_track_keys(
                    'root', translations,
                    [transform.rotation for transform in root],
                    [u.Vector(*expected_root_scale) for transform in root],
                ):
                    raise RuntimeError(f'{name}: failed to normalize root track')
            finally:
                controller.close_bracket()
            root = extract_root_track(animation, frames, fps)
        save(animation)
    points = [vec(transform.translation) for transform in root]
    scales = [vec(transform.scale3d) for transform in root]
    root_error = max(math.dist(a, b) for a, b in zip(expected_points, points))
    if root_error > 0.25:
        REPORT['errors'].append(
            f'{name}: root track error {root_error:g} cm, end {points[-1]}, expected {expected_points[-1]}')
    evaluated = u.AnimPoseExtensions.get_anim_pose_at_time(animation, 0.0, pose_options)
    if not u.AnimPoseExtensions.is_valid(evaluated):
        raise RuntimeError(f'{name}: invalid evaluated pose')
    joint_lengths = {}
    for bone in ['pelvis', 'neck', 'head', 'paw_F_L', 'paw_H_R', 'tail_01']:
        local = u.AnimPoseExtensions.get_bone_pose(evaluated, bone, u.AnimPoseSpaces.LOCAL)
        idle = u.AnimPoseExtensions.get_bone_pose(idle_pose, bone, u.AnimPoseSpaces.LOCAL)
        joint_lengths[bone] = [local.translation.length(), idle.translation.length()]
    contact = {}
    if clip.get('id') in ('C02', 'C03'):
        frame = 23 if clip['id'] == 'C02' else 0
        compressed_options = u.AnimPoseEvaluationOptions()
        apply_properties(compressed_options, {
            'evaluation_type': u.AnimDataEvalType.COMPRESSED,
            'extract_root_motion': False,
            'incorporate_root_motion_into_pose': False,
            'should_retarget': False,
            'optional_skeletal_mesh': pose_options.optional_skeletal_mesh,
        })
        for options in (pose_options, compressed_options):
            contact_pose = u.AnimPoseExtensions.get_anim_pose_at_frame(animation, frame, options)
            if not u.AnimPoseExtensions.is_valid(contact_pose):
                raise RuntimeError(f'{name}: invalid evaluated contact pose')
            contact[str(options.evaluation_type)] = {
                bone: vec(u.AnimPoseExtensions.get_bone_pose(
                    contact_pose, bone, u.AnimPoseSpaces.WORLD).translation * 2)
                for bone in ('paw_f_l', 'paw_f_r')
            }
    sampled_keys = u.AnimationLibrary.get_num_keys(animation)
    if sampled_keys != frames:
        REPORT['errors'].append(f'{name}: {sampled_keys} keys, expected {frames}')

    scale_error = max(math.dist(scale, expected_root_scale) for scale in scales)
    if scale_error > 0.01:
        REPORT['errors'].append(f'{name}: unexpected root scale deviation {scale_error:g}')
    REPORT['animations'][clip.get('id', 'MASTER')] = {
        'path': animation.get_path_name(),
        'seconds': length,
        'sampled_keys': sampled_keys,
        'expected_keys': frames,
        'bone_tracks': tracks,
        'skeleton': skeleton.get_path_name(),
        'root_motion_enabled': False,
        'root_start_cm': points[0],
        'root_end_cm': points[-1],
        'root_min_cm': [min(axis) for axis in zip(*points)],
        'root_max_cm': [max(axis) for axis in zip(*points)],
        'root_scale': scales[0],
        'root_scale_max_deviation': scale_error,
        'max_root_track_error_cm': root_error,
        'sample_local_and_idle_joint_lengths_cm': joint_lengths,
        'grip_paw_positions_cm_at_mesh_scale_2': contact,
    }


def run_case(fn, *args):
    try:
        fn(*args)
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    write_report()


def main():
    # Legacy FBX imports use explicit FbxImportUI and honor delivered UCX hulls.
    if not AUDIT:
        world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
        u.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    delivery = json.loads((SOURCE / 'asset_manifest.json').read_text(encoding='utf-8'))
    animation = json.loads((ANIM_SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    cat_mesh = EA.load_asset(CAT)
    skeleton = cat_mesh.get_editor_property('skeleton')
    pose_options = u.AnimPoseEvaluationOptions()
    apply_properties(pose_options, {
        'evaluation_type': u.AnimDataEvalType.SOURCE,
        'extract_root_motion': False,
        'incorporate_root_motion_into_pose': False,
        'should_retarget': False,
        'optional_skeletal_mesh': cat_mesh,
    })
    idle = EA.load_asset('/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Idle')
    idle_pose = u.AnimPoseExtensions.get_anim_pose_at_time(idle, 0.0, pose_options)
    source_roots = {}
    with (ANIM_SOURCE / 'root_contact_tracks.csv').open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            x, y, z = (float(row[f'root_native_{axis}_m']) for axis in 'xyz')
            source_roots.setdefault(row['action'], []).append([100 * x, -100 * y, 100 * z])
    for clip in animation['clips'] + [animation['master']]:
        run_case(import_animation, clip, animation['fps'], skeleton, source_roots, idle_pose, pose_options)
    material_names = sorted({material for row in delivery['assets'] for material in row['materials']})
    materials = {name: import_material(name) for name in material_names}
    for row in delivery['assets']:
        run_case(import_mesh, row, materials)
    REPORT['success'] = not REPORT['errors']
    write_report()
    if REPORT['errors']:
        raise RuntimeError(f"{len(REPORT['errors'])} elevator import or audit errors")
    print('ELEVATOR_IMPORT_OK', len(REPORT['meshes']), len(REPORT['animations']))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
        write_report()
        raise
