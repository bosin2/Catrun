"""Capture the installed Stage2 portal from one saved camera over editor ticks.

Call start() from Unreal Python in a normal offscreen editor. Each sample pairs
the live orbit cards with one capture from the same tick with only those cards
hidden. The Level Sequence stays paused at its opening camera and the cat stays
offscreen. No package is saved. Play-in-Editor exposure is checked separately.
"""

import ast
import datetime
import json
from pathlib import Path
import sys
import time
import traceback
import types

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/GameplayRepair'))
import author_portal_style_20261119 as portal


source = ROOT / 'Scripts/GameplayRepair/render_portal_followup.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
assert isinstance(tree.body[-1], ast.Expr) and isinstance(tree.body[-1].value, ast.Call)
helper = types.ModuleType('portal_style_motion_capture_helpers')
helper.__dict__['__file__'] = str(source)
exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), str(source), 'exec'), helper.__dict__)


def start():
    assert not portal.dirty_project() and not helper.ED.get_game_world()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = ROOT / 'Saved/PresentationFix20261119/PortalStyleMotion' / stamp
    output.mkdir(parents=True)
    report = {'completed': False, 'sample_time': 'editor-world seconds',
              'sequence_frame': 0, 'frames': [], 'before_hashes': portal.content_hashes()}
    capture_actor = level_player = holder = target = component = handle = None
    finished = False

    def persist():
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        finished = True
        if handle is not None:
            u.unregister_slate_post_tick_callback(handle)
        if level_player:
            level_player.stop()
        for actor in (capture_actor, holder):
            if actor:
                helper.ACTORS.destroy_actor(actor)
        if target:
            u.RenderingLibrary.release_render_target2d(target)
        if error:
            report['error'] = error
        report['hashes_unchanged'] = report['before_hashes'] == portal.content_hashes()
        report['completed'] = not error and report['hashes_unchanged'] and not portal.dirty_project()
        persist()
        print('CATRUN_PORTAL_STYLE_MOTION_20261119', report['completed'], str(output / 'report.json'))

    try:
        assert helper.LEVEL.load_level('/Game/Maps/Stage2')
        world = helper.ED.get_editor_world()
        sequence = portal.loaded_asset(portal.SEQUENCE)
        pawn = helper.only(a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Character)
                           if 'BP_Cat' in a.get_class().get_name())
        level_player, holder = u.LevelSequencePlayer.create_level_sequence_player(
            world, sequence, u.MovieSceneSequencePlaybackSettings(),
        )
        holder.set_binding_by_tag('CatrunArrivalPawn', [pawn], False)
        level_player.play()
        level_player.pause()
        helper.sequence_frame(level_player, 0)
        camera = level_player.get_active_camera_component()
        view = camera.get_camera_view(0.)
        bindings, arrival_parent = portal.portal_window(sequence)
        actor = helper.only(level_player.get_bound_objects(sequence.get_binding_id(arrival_parent)))
        component = helper.only(level_player.get_bound_objects(sequence.get_binding_id(bindings[portal.SPARK_COMPONENT])))
        assert component == actor.get_editor_property(portal.SPARK_COMPONENT) and component.is_visible()
        assert view.projection_mode == u.CameraProjectionMode.ORTHOGRAPHIC
        report['camera'] = {'location': helper.vector(view.location), 'rotation': view.rotation.export_text(),
                            'ortho_width': view.ortho_width}
        report['portal'] = {'location': helper.vector(actor.get_actor_location()),
                            'component': component.get_path_name(),
                            'mesh': portal.spark_mesh_state(portal.loaded_asset(portal.SPARK_MESH), component.get_material(0)),
                            'spark_parameters': portal.spark_material_state(component.get_material(0))}
        capture_actor = helper.ACTORS.spawn_actor_from_class(u.SceneCapture2D, view.location, view.rotation, transient=True)
        capture = capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
        target = u.RenderingLibrary.create_render_target2d(world, 1280, 720, u.TextureRenderTargetFormat.RTF_RGBA8,
                                                           u.LinearColor(0, 0, 0, 1), False)
        for name, value in (
            ('texture_target', target), ('capture_every_frame', False), ('capture_on_movement', False),
            ('capture_source', u.SceneCaptureSource.SCS_FINAL_COLOR_LDR),
            ('primitive_render_mode', u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST),
            ('projection_type', view.projection_mode), ('ortho_width', view.ortho_width),
            ('post_process_settings', view.post_process_settings),
            ('post_process_blend_weight', view.post_process_blend_weight),
        ):
            capture.set_editor_property(name, value)
        helper.add_render_meshes(capture, u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
        capture.capture_scene()

        def shot(name):
            actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
            helper.add_render_meshes(capture, actors)
            capture.capture_scene()
            u.RenderingLibrary.export_render_target(world, target, str(output), name)
            path = output / name
            assert path.is_file() and path.stat().st_size > 2048, path
            return str(path)

        began = time.monotonic()
        next_capture = began + 0.45

        def tick(_):
            nonlocal next_capture
            try:
                now = time.monotonic()
                if now < next_capture:
                    return
                index = len(report['frames'])
                world_time = u.GameplayStatics.get_time_seconds(world)
                visible = shot(f'Visible_{index:02d}.png')
                component.set_visibility(False, False)
                try:
                    hidden = shot(f'Hidden_{index:02d}.png')
                finally:
                    component.set_visibility(True, False)
                report['frames'].append({'world_seconds': world_time, 'wall_seconds': now - began,
                                         'visible': visible, 'hidden': hidden})
                persist()
                next_capture = now + 0.24
                if len(report['frames']) == 8:
                    assert report['frames'][-1]['world_seconds'] > report['frames'][0]['world_seconds'], (
                        'The editor stopped advancing world time. Use a normal realtime viewport.',
                    )
                    finish()
            except Exception:
                finish(traceback.format_exc())

        persist()
        handle = u.register_slate_post_tick_callback(tick)
        return str(output / 'report.json')
    except Exception:
        finish(traceback.format_exc())
        raise
