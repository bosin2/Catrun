"""Render sampled Stage1 sequence evaluations in an offscreen editor commandlet.

Use -run=pythonscript -AllowCommandletRendering -RenderOffscreen -onethread
-NoAsyncLoadingThread and the four isolated geometry CVars. Run in a fresh
process. This creates transient capture/player actors and never saves packages.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
BASE = '/Game/Cinematics/Stage1/Portal/'
MAP = '/Game/Maps/Stage1'
SEQUENCE = BASE + 'LS_Stage1_PortalExit'
PRESENTATION = BASE + 'BP_Stage1PortalPresentation'
PORTAL_LOCATION = (101., -293.9189189189189, -.8)
FRAMES = (0, 60, 120, 200, 238, 248, 275, 283, 284, 290)
ISOLATED_CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
                  'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')
CLIPS = '/Game/Characters/BlackCat/Final/Animations/'
ASSETS = (SEQUENCE, PRESENTATION, BASE + 'BP_Stage1PortalExit', BASE + 'WBP_ExitTransition',
          BASE + 'M_Stage1PortalBlue', BASE + 'Followup20261112/M_PortalDepthCore',
          BASE + 'Followup20261112/M_PortalAetherHalo', CLIPS + 'AN_BlackCat_Walk',
          CLIPS + 'Cinematics/AN_BlackCat_PortalInspect', CLIPS + 'Cinematics/AN_BlackCat_PortalJumpIn')
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
RENDER = u.RenderingLibrary


def digest(file):
    with file.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def asset_hashes():
    return {package: digest(ROOT / 'Content' / (package.removeprefix('/Game/') + ext))
            for ext, packages in (('.umap', (MAP, '/Game/Maps/SoundTest_Stage1')), ('.uasset', ASSETS))
            for package in packages}


def dirty_packages():
    saving = u.EditorLoadingAndSavingUtils
    return sorted(package.get_name() for package in
                  (*saving.get_dirty_map_packages(), *saving.get_dirty_content_packages()))


def only(objects):
    objects = list(objects)
    assert len(objects) == 1, objects
    return objects[0]


def tagged(actors, tag):
    return [actor for actor in actors if tag in map(str, actor.tags)]


def vector(value):
    return (value.x, value.y, value.z)


def transform(value):
    rotation = value.rotation
    return {'location': vector(value.translation), 'scale': vector(value.scale3d),
            'rotation': (rotation.x, rotation.y, rotation.z, rotation.w)}


def same_transform(first, second):
    a, b = transform(first), transform(second)
    return (math.dist(a['location'], b['location']) < .01 and math.dist(a['scale'], b['scale']) < .001
            and min(math.dist(a['rotation'], tuple(sign * x for x in b['rotation']))
                    for sign in (-1., 1.)) < .001)


def hidden(actor):
    return actor.get_editor_property('hidden')


def pose(mesh, bone_names):
    return {str(name): transform(mesh.get_socket_transform(name, u.RelativeTransformSpace.RTS_COMPONENT))
            for name in bone_names}


def changed_bones(first, second):
    return sum(any(math.dist(value, second[name][key]) > .001 for key, value in bone.items())
               for name, bone in first.items())


def sequence_frame(player, frame):
    params = u.MovieSceneSequencePlaybackParams()
    params.set_editor_property('frame', u.FrameTime(u.FrameNumber(frame), 0.))
    params.set_editor_property('position_type', u.MovieScenePositionType.FRAME)
    params.set_editor_property('update_method', u.UpdatePositionMethod.SCRUB)
    params.set_editor_property('has_jumped', True)
    player.set_playback_position(params)
    current = player.get_current_time()
    assert current.time.frame_number.value == frame and abs(current.time.sub_frame) < .001, str(current)


def portal_state(portal):
    meshes = {}
    for component in portal.get_components_by_class(u.StaticMeshComponent):
        material = component.get_material(0)
        meshes[component.get_name()] = {
            'path': component.get_path_name(), 'location': vector(component.get_world_location()),
            'material': material.get_path_name() if material else None, 'visible': component.is_visible(),
        }
    return {'path': portal.get_path_name(), 'transform': transform(portal.get_actor_transform()), 'meshes': meshes}


def add_render_meshes(component, actors):
    # The Game scene capture keeps actual stage lighting and shadows. Explicit
    # mesh selection excludes editor-only icons, collision and trigger proxies.
    component.clear_show_only_components()
    count = 0
    for actor in actors:
        if hidden(actor):
            continue
        for primitive in actor.get_components_by_class(u.PrimitiveComponent):
            if (isinstance(primitive, (u.StaticMeshComponent, u.SkeletalMeshComponent))
                    and primitive.is_visible() and not primitive.get_editor_property('hidden_in_game')):
                component.show_only_component(primitive)
                count += 1
    return count


def capture(world, capture_actor, target, camera, frames_dir, frame, scene_actors):
    view = camera.get_camera_view(0.)
    assert view.projection_mode == u.CameraProjectionMode.PERSPECTIVE
    assert not view.constrain_aspect_ratio or math.isclose(view.aspect_ratio, 16 / 9, abs_tol=.001)
    assert capture_actor.set_actor_location_and_rotation(view.location, view.rotation, False, True)
    component = capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
    component.set_editor_property('fov_angle', view.fov)
    component.set_editor_property('post_process_settings', view.post_process_settings)
    component.set_editor_property('post_process_blend_weight', view.post_process_blend_weight)
    count = add_render_meshes(component, scene_actors)
    component.capture_scene()
    name = f'Frame_{frame:03d}.png'
    RENDER.export_render_target(world, target, str(frames_dir), name)
    image = frames_dir / name
    assert image.is_file() and image.stat().st_size > 2048, (frame, 'empty capture')
    return {'path': str(image), 'sha256': digest(image), 'mesh_components': count,
            'camera_location': vector(view.location), 'camera_rotation': (view.rotation.pitch, view.rotation.yaw, view.rotation.roll),
            'fov': view.fov, 'camera_aspect_ratio': view.aspect_ratio}


def render(report, frames_dir, persist):
    assert not ED.get_game_world() and not dirty_packages(), dirty_packages()
    assert all(u.SystemLibrary.get_console_variable_int_value(name) == 0 for name in ISOLATED_CVARS)
    assert LEVEL.load_level(MAP), MAP
    world = ED.get_editor_world()
    assert world.get_path_name().split('.')[0] == MAP and not ED.get_game_world()
    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
    director = only(tagged(actors, 'CatrunAuthoredStage1Exit'))
    cat = only(actor for actor in actors if isinstance(actor, u.Character) and actor.get_name() == 'BP_Cat_C_0')
    mesh = cat.get_component_by_class(u.SkeletalMeshComponent)
    assert mesh and mesh.get_num_bones() > 1
    bones = [mesh.get_bone_name(i) for i in range(mesh.get_num_bones())]
    sequence = u.EditorAssetLibrary.load_asset(SEQUENCE)
    presentation = u.EditorAssetLibrary.load_blueprint_class(PRESENTATION)
    assert sequence and presentation and director.get_editor_property('CinematicActor').get_sequence() == sequence
    rate = sequence.get_display_rate()
    assert (rate.numerator, rate.denominator) == (30, 1) and sequence.get_playback_end() == 308
    bindings = sequence.get_bindings()
    cat_binding = only(b for b in bindings if 'CatrunCat' in map(str, b.get_binding_tags()))
    portal_binding = only(b for b in bindings if 'CatrunPortal' in map(str, b.get_binding_tags()))
    light_binding = only(b for b in bindings if b.get_name() == 'BlueLight'
                         and b.get_parent().get_id().export_text() == portal_binding.get_id().export_text())
    camera_track = only(track for track in sequence.get_tracks() if isinstance(track, u.MovieSceneCameraCutTrack))
    cuts = camera_track.get_sections()
    animations = only(cat_binding.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)).get_sections()
    report.update(world=world.get_path_name(), director=director.get_path_name(), sequence=sequence.get_path_name(),
                  cat=cat.get_path_name(), cat_mesh=mesh.get_skeletal_mesh_asset().get_path_name(), fps=30)

    saved_transform = cat.get_actor_transform()
    initial_hidden = hidden(cat)
    initial_mode = mesh.get_animation_mode()
    initial_anim = mesh.get_anim_instance()
    original_pose = pose(mesh, bones)
    report['saved_cat_transform'] = transform(saved_transform)
    assert not initial_hidden
    sequence_actor = capture_actor = transient_portal = target = player = None
    try:
        portal = director.get_editor_property('PortalPresentation')
        if portal:
            assert only(tagged(actors, 'CatrunAuthoredStage1Portal')) == portal
        else:
            assert not tagged(actors, 'CatrunAuthoredStage1Portal')
            portal = transient_portal = ACTORS.spawn_actor_from_class(
                presentation, u.Vector(*PORTAL_LOCATION), u.Rotator(yaw=180.), transient=True)
            actors.append(portal)
        assert portal.get_class() == presentation and math.dist(vector(portal.get_actor_location()), PORTAL_LOCATION) < .01
        report['portal'] = portal_state(portal)
        report['portal']['transient_fixture'] = transient_portal is not None
        portal_materials = {row['material'] for row in report['portal']['meshes'].values() if row['visible']}
        for package in (BASE + 'M_Stage1PortalBlue', BASE + 'Followup20261112/M_PortalDepthCore',
                        BASE + 'Followup20261112/M_PortalAetherHalo'):
            assert package + '.' + package.rsplit('/', 1)[1] in portal_materials, report['portal']

        # This validated corridor point is the pre-animated pawn arrival. The
        # original level spawn is outside the sequence's initial camera frame.
        arrival = director.get_editor_property('Trigger').get_world_location()
        assert math.dist(vector(arrival), (101., -80., 25.2)) < .01
        assert cat.set_actor_location_and_rotation(arrival, u.Rotator(yaw=-90.), False, True)
        staged_transform = cat.get_actor_transform()
        report['preview_arrival'] = transform(staged_transform)

        capture_actor = ACTORS.spawn_actor_from_class(u.SceneCapture2D, u.Vector(), u.Rotator(), transient=True)
        capture_component = capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
        target = RENDER.create_render_target2d(world, 1280, 720, u.TextureRenderTargetFormat.RTF_RGBA8,
                                                u.LinearColor(0., 0., 0., 1.), False)
        capture_component.set_editor_property('texture_target', target)
        capture_component.set_editor_property('capture_every_frame', False)
        capture_component.set_editor_property('capture_on_movement', False)
        capture_component.set_editor_property('capture_source', u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        capture_component.set_editor_property('primitive_render_mode', u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        assert u.CatrunAuthoringLibrary.finish_asset_compilation()

        settings = u.MovieSceneSequencePlaybackSettings()
        settings.set_editor_property('finish_completion_state_override', u.MovieSceneCompletionModeOverride.FORCE_RESTORE_STATE)
        player, sequence_actor = u.LevelSequencePlayer.create_level_sequence_player(world, sequence, settings)
        assert player and sequence_actor and player.get_sequence() == sequence
        sequence_actor.set_binding_by_tag('CatrunCat', [cat], False)
        sequence_actor.set_binding_by_tag('CatrunPortal', [portal], False)
        # Enter the player once to enable global pre-animated state capture.
        # The commandlet never ticks gameplay and each image uses an exact scrub.
        player.play()
        assert player.is_playing(), 'Editor-world player failed to start'
        player.pause()

        previous_pose = original_pose
        active_cameras = set()
        for frame in FRAMES:
            sequence_frame(player, frame)
            camera = player.get_active_camera_component()
            assert camera, (frame, 'no evaluated camera cut')
            cut = only(cut for cut in cuts if cut.get_start_frame() <= frame < cut.get_end_frame())
            camera_actor = only(player.get_bound_objects(cut.get_camera_binding_id()))
            assert camera.get_owner() == camera_actor, (frame, 'active camera and evaluated cut differ')
            active_cameras.add(camera_actor.get_path_name())
            assert list(player.get_bound_objects(sequence.get_binding_id(cat_binding))) == [cat]
            assert list(player.get_bound_objects(sequence.get_binding_id(portal_binding))) == [portal]
            light = only(player.get_bound_objects(sequence.get_binding_id(light_binding)))
            assert light.get_owner() == portal
            current_pose = pose(mesh, bones)
            location = vector(cat.get_actor_location())
            visible = not hidden(cat)
            clip = only(section for section in animations if section.get_start_frame() <= frame < section.get_end_frame())
            row = {'frame': frame, 'seconds': frame / 30., 'camera': camera_actor.get_path_name(),
                   'camera_binding_id': cut.get_camera_binding_id().export_text(), 'cat_visible': visible,
                   'cat_location': location, 'cat_animation_mode': str(mesh.get_animation_mode()),
                   'authored_clip_at_frame': clip.get_editor_property('params').get_editor_property('animation').get_path_name(),
                   'cat_pose_sha256': hashlib.sha256(json.dumps(current_pose).encode()).hexdigest(),
                   'changed_bones_from_previous': changed_bones(previous_pose, current_pose),
                   'changed_bones_from_saved_pose': changed_bones(original_pose, current_pose),
                   'portal_light': {'path': light.get_path_name(), 'intensity': light.get_editor_property('intensity'),
                                    'location': vector(light.get_world_location())}}
            report['frames'].append(row)
            persist()
            assert visible == (frame < 284), (frame, 'evaluated cat visibility mismatch', visible)
            row['capture'] = capture(world, capture_actor, target, camera, frames_dir, frame, actors)
            persist()
            previous_pose = current_pose

        assert len(active_cameras) == 3, active_cameras
        assert len({row['capture']['sha256'] for row in report['frames']}) >= 7, 'Frames did not change'
        assert math.dist(report['frames'][0]['cat_location'], report['frames'][6]['cat_location']) > 150.
        assert len({row['portal_light']['intensity'] for row in report['frames']}) > 1, 'Portal light did not animate'
        report['skeletal_pose_evaluated'] = all(
            any(row['changed_bones_from_previous'] > 0 for row in report['frames'] if low <= row['frame'] < high)
            for low, high in ((0, 96), (96, 216), (238, 284)))
        player.stop()
        report['player_stop_restored_preview_state'] = (
            same_transform(staged_transform, cat.get_actor_transform()) and hidden(cat) == initial_hidden
            and mesh.get_animation_mode() == initial_mode and mesh.get_anim_instance() == initial_anim)
        assert report['player_stop_restored_preview_state'], 'Player did not restore its pre-animated pawn state'
        assert not any(a.get_path_name() in active_cameras for a in u.GameplayStatics.get_all_actors_of_class(
            world, u.CameraActor)), 'Spawnable cameras survived Stop'
        assert report['skeletal_pose_evaluated'], 'Editor-world pose changes could not be verified'
    finally:
        if player:
            player.stop()
        for actor in (capture_actor, sequence_actor, transient_portal):
            if actor:
                assert ACTORS.destroy_actor(actor), actor.get_path_name()
        if target:
            RENDER.release_render_target2d(target)
        cat.set_actor_transform(saved_transform, False, True)
        cat.set_actor_hidden_in_game(initial_hidden)
        report['saved_cat_state_restored'] = (same_transform(saved_transform, cat.get_actor_transform())
                                              and hidden(cat) == initial_hidden and mesh.get_animation_mode() == initial_mode)
        assert report['saved_cat_state_restored'] and not ED.get_game_world()


def main():
    frames_dir = ROOT / 'Saved/GameplayRepair20261112/PortalFollowup/Frames' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    frames_dir.mkdir(parents=True, exist_ok=False)
    report_file = frames_dir / 'report.json'
    report = {'pid': os.getpid(), 'completed': False, 'frames': [], 'pie': False,
              'capture_method': 'ULevelSequencePlayer exact editor-world scrubs and SceneCapture2D final color',
              'render_limits': ['The Game/PIE PlayerCameraManager fade and UMG are outside SceneCapture2D.',
                                'The editor world does not advance gameplay/material time between samples.'],
              'script_sha256': digest(Path(__file__))}

    def persist():
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    try:
        report['before_hashes'] = asset_hashes()
        persist()
        render(report, frames_dir, persist)
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        report['dirty_packages_in_memory'] = dirty_packages()
        if 'before_hashes' in report:
            report['after_hashes'] = asset_hashes()
            report['inputs_unchanged'] = report['before_hashes'] == report['after_hashes']
        else:
            report['inputs_unchanged'] = None
        report['completed'] = report['completed'] and report['inputs_unchanged']
        persist()
        print('CATRUN_PORTAL_RENDER', report['completed'], str(report_file))
        assert report['inputs_unchanged'] is not False, 'A saved input changed during capture'


main()
