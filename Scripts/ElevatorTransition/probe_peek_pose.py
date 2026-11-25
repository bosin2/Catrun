"""Read-only C06 head/eye and low-camera occlusion probe for a loaded Stage2.

No actors are moved, spawned, hidden, destroyed, or saved. The imported C06 pose
is evaluated without root extraction; the shipping mesh/mark transforms and
existing departure rise formula predict world positions. Scene traces ignore
the unmoved cabin; the rising platform gets a separate local bounding-box test.
Run in the coordinator's isolated editor, before or after the camera refinement.
"""
import json
import math
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/ElevatorTransition/peek_pose_probe.json'
TAG = 'CatrunElevatorTransition20261125'
MAP = '/Game/Maps/Stage2.Stage2'


def xyz(value):
    return list(value.to_tuple())


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def ray_box(start, end, lower, upper):
    """First segment/AABB entry; None means no hit. Bounds are conservative."""
    near, far = 0.0, 1.0
    for axis in range(3):
        step = end[axis] - start[axis]
        if abs(step) < 1.0e-9:
            if start[axis] < lower[axis] or start[axis] > upper[axis]:
                return None
            continue
        a = (lower[axis] - start[axis]) / step
        b = (upper[axis] - start[axis]) / step
        near, far = max(near, min(a, b)), min(far, max(a, b))
        if near > far:
            return None
    return near if 0.0 <= near <= 1.0 else None


def main():
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    assert not editor.get_game_world(), 'Probe saved task-editor Stage2 outside PIE'
    world = editor.get_editor_world()
    assert world and world.get_path_name() == MAP, 'Load Stage2 explicitly; this probe never loads maps'
    actors = list(subsystem.get_all_level_actors())
    lookup = {a.get_actor_label(): a for a in actors}
    director = lookup['E23_Director']
    assert TAG in map(str, director.tags) and not director.get_editor_property('arrival_side')
    pivot = director.get_editor_property('cabin_pivot').get_actor_location()
    mark = director.get_editor_property('cat_mark')
    assert abs(mark.get_actor_rotation().yaw - 90.0) < 0.1, 'Stage2 mark orientation changed'
    cls = u.load_class(None, '/Game/Characters/BlackCat/Blueprints/BP_Cat.BP_Cat_C')
    cat_default = u.get_default_object(cls)
    # Character's native mesh reference works on its unregistered CDO as well.
    mesh_component = cat_default.get_editor_property('mesh')
    mesh = mesh_component.get_skeletal_mesh_asset()
    relative = mesh_component.get_relative_transform()
    mesh_origin = u.MathLibrary.transform_location(mark.get_actor_transform(), relative.translation)
    assert abs(mesh_component.get_editor_property('relative_rotation').yaw + 90.0) < 0.1
    scale = relative.scale3d
    clips = list(director.get_editor_property('departure_clips'))
    clip = clips[5]
    assert clip.get_editor_property('skeleton') == mesh.get_editor_property('skeleton')
    options = u.AnimPoseEvaluationOptions()
    for key, value in {
        'evaluation_type': u.AnimDataEvalType.SOURCE,
        'extract_root_motion': False,
        'incorporate_root_motion_into_pose': False,
        'should_retarget': False,
        'optional_skeletal_mesh': mesh,
    }.items():
        options.set_editor_property(key, value)
    bone_names = {str(n).lower(): str(n) for n in u.AnimationLibrary.get_animation_track_names(clip)}
    requested = ['root', 'pelvis', 'head', 'lid_upper_l_00', 'lid_upper_r_00', 'paw_f_l', 'paw_f_r']
    assert all(n in bone_names for n in requested), bone_names
    source_length = clip.get_editor_property('sequence_length')
    startup_length = clips[4].get_editor_property('sequence_length')
    rise_time = startup_length + source_length + clips[6].get_editor_property('sequence_length') - 8.0 / 30.0
    rise_distance = director.get_editor_property('departure_rise_distance')
    camera = director.get_editor_property('peek_camera')
    lenses = {
        'authored': xyz(camera.get_actor_location()),
        'old_below_floor': xyz(pivot + u.Vector(20.0, 240.0, -32.0)),
        'proposed_above_floor': xyz(pivot + u.Vector(14.0, 280.0, 14.0)),
    }
    moving = list(director.get_editor_property('cabin_actors'))
    ignored = list(set(moving + list(u.GameplayStatics.get_all_actors_of_class(world, u.Pawn))))
    audit = json.loads((ROOT / 'Saved/ElevatorTransition/cold_import_audit.json').read_text())
    bounds = audit['meshes']['SM_E23_Platform']['bounds_cm']
    samples = []
    for frame in sorted(set(range(94, 175, 2)) | {103, 133, 153, 174}):
        time = (frame - 1) / 30.0
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(clip, time, options)
        assert u.AnimPoseExtensions.is_valid(pose)
        moving_time = time + startup_length - 8.0 / 30.0
        rise = rise_distance * smooth(moving_time / rise_time)
        sway = 2.2 * math.sin(moving_time * 15.0) * math.exp(-2.6 * moving_time)
        sway += 0.75 * math.sin(moving_time * 2.0) * smooth(moving_time / 0.85)
        local, positions = {}, {}
        for name in requested:
            transform = u.AnimPoseExtensions.get_bone_pose(pose, bone_names[name], u.AnimPoseSpaces.WORLD)
            p = transform.translation
            local[name] = xyz(u.Vector(p.x * scale.x, p.y * scale.y, p.z * scale.z))
            offset = mesh_origin + u.Vector(*local[name]) - pivot
            positions[name] = xyz(pivot + u.MathLibrary.rotate_angle_axis(offset, sway, u.Vector(1, 0, 0)) + u.Vector(0, 0, rise))
        eyes = [(a + b) * 0.5 for a, b in zip(positions['lid_upper_l_00'], positions['lid_upper_r_00'])]
        # Transform the ray back to the rising/swaying platform's local space.
        # Its mesh bounds are conservative; actual triangle traces in PIE remain
        # the final geometric visibility evidence.
        cabin_position = pivot + u.Vector(0, 0, rise)
        local_eyes = xyz(u.MathLibrary.rotate_angle_axis(u.Vector(*eyes) - cabin_position,
            -sway, u.Vector(1, 0, 0)))
        results = {}
        for label, lens in lenses.items():
            hit = u.SystemLibrary.line_trace_single(world, u.Vector(*lens), u.Vector(*eyes),
                u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, u.DrawDebugTrace.NONE, False)
            data = hit.to_dict() if hit else {}
            blocker = data.get('hit_actor')
            local_lens = xyz(u.MathLibrary.rotate_angle_axis(u.Vector(*lens) - cabin_position,
                -sway, u.Vector(1, 0, 0)))
            along = (bounds[1][1] - local_lens[1]) / (local_eyes[1] - local_lens[1])
            edge_clearance = local_lens[2] + along * (local_eyes[2] - local_lens[2]) - bounds[1][2]
            results[label] = {
                'fixed_scene_blocker': blocker.get_actor_label() if blocker else None,
                'rising_platform_bounds_hit_fraction': ray_box(local_lens, local_eyes, *bounds),
                'front_edge_eye_ray_clearance_cm': edge_clearance,
                'look_rotation': xyz(u.MathLibrary.find_look_at_rotation(u.Vector(*lens), u.Vector(*eyes))),
                'face_distance_cm': math.dist(lens, eyes),
            }
        samples.append({'frame': frame, 'source_seconds': time, 'rise_cm': rise, 'sway_degrees': sway,
            'local_at_mesh_scale': local, 'world': positions, 'eyes_midpoint_world': eyes, 'lenses': results})
    report = {
        'read_only': True, 'map': world.get_path_name(), 'clip': clip.get_path_name(),
        'skeleton': mesh.get_editor_property('skeleton').get_path_name(),
        'root_motion_enabled': clip.get_editor_property('enable_root_motion'),
        'mesh_origin': xyz(mesh_origin), 'mesh_scale': xyz(scale), 'lenses': lenses,
        'platform_local_bounds': bounds, 'source_seconds': source_length,
        'current_shot_seconds': [3.4, 5.77],
        'samples': samples,
        'limits': ['Imported source pose plus authored rise, not live runtime evaluation.',
            'Scene trace ignores the unmoved cabin; rising platform local bounds are a separate approximation.',
            'Static collision traces cannot prove lighting or eye readability; inspect full-size PIE shots.'],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(OUT), 'read_only': True, 'sample_count': len(samples),
        'old_camera_blockers': sorted({s['lenses']['old_below_floor']['fixed_scene_blocker'] or '' for s in samples}),
        'proposed_camera_blockers': sorted({s['lenses']['proposed_above_floor']['fixed_scene_blocker'] or '' for s in samples}),
        'proposed_min_front_edge_clearance_cm': min(s['lenses']['proposed_above_floor']['front_edge_eye_ray_clearance_cm'] for s in samples),
    }, ensure_ascii=False))


main()
