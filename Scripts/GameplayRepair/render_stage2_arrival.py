"""Render actual saved arrival sequence samples in a fresh offscreen commandlet.

No package saves or gameplay ticks. This is sampled sequence evaluation, not
manual play; the companion runtime probe checks the real Blueprint lifecycle.
"""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import traceback
import types
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
BASE = '/Game/Cinematics/Stage2/Arrival/'
SEQUENCE = BASE + 'LS_Stage2_PortalArrival'
MAP = '/Game/Maps/Stage2'
FRAMES = (0, 12, 24, 38, 60, 70, 74, 88, 91, 150, 178, 182, 209, 211, 270, 299, 330, 359)
OUT = ROOT / 'Saved/Stage2Arrival20261116/Frames' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
OUT.mkdir(parents=True, exist_ok=False)

# Reuse only definitions from the established capture helper, never its main.
source = ROOT / 'Scripts/GameplayRepair/render_portal_followup.py'
tree = ast.parse(source.read_text(encoding='utf8'))
assert isinstance(tree.body[-1], ast.Expr) and isinstance(tree.body[-1].value, ast.Call)
helper = types.ModuleType('arrival_capture_helpers')
helper.__dict__['__file__'] = str(source)
exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), str(source), 'exec'), helper.__dict__)


def hashes():
    files = [ROOT/'Content/Maps/Stage2.umap', ROOT/'Content/Maps/SoundTest_Stage2.umap']
    for folder in ('Cinematics/Stage1/Portal', 'Cinematics/Stage2/Arrival', 'Characters/BlackCat/Final'):
        files.extend((ROOT/'Content'/folder).rglob('*.uasset'))
    return {str(p.relative_to(ROOT)): helper.digest(p) for p in files}


def capture(world, actor, target, camera, frame):
    view = camera.get_camera_view(0.)
    actor.set_actor_location_and_rotation(view.location, view.rotation, False, True)
    component = actor.get_component_by_class(u.SceneCaptureComponent2D)
    component.set_editor_property('projection_type', view.projection_mode)
    component.set_editor_property('fov_angle', view.fov)
    component.set_editor_property('ortho_width', view.ortho_width)
    component.set_editor_property('post_process_settings', view.post_process_settings)
    component.set_editor_property('post_process_blend_weight', view.post_process_blend_weight)
    count = helper.add_render_meshes(component, list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor)))
    component.capture_scene()
    name = f'Frame_{frame:03d}.png'
    u.RenderingLibrary.export_render_target(world, target, str(OUT), name)
    path = OUT/name
    assert path.exists() and path.stat().st_size > 2048
    return {'image': str(path), 'components': count, 'position': helper.vector(view.location),
            'rotation': view.rotation.export_text(), 'projection': str(view.projection_mode),
            'ortho_width': view.ortho_width, 'fov': view.fov}


def main():
    report = {'completed': False, 'pid': os.getpid(), 'frames': [], 'before': hashes(),
              'scope': 'Exact editor-world sequence scrubs with actual map lighting; no PIE, UMG or continuous material time.'}
    player = sequence_actor = capture_actor = target = None
    try:
        assert not helper.ED.get_game_world() and not helper.dirty_packages()
        assert helper.LEVEL.load_level(MAP)
        world = helper.ED.get_editor_world()
        cat = helper.only(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Character)
                          if 'BP_Cat' in a.get_class().get_name())
        mesh = cat.get_component_by_class(u.SkeletalMeshComponent)
        original = cat.get_actor_transform()
        original_hidden = helper.hidden(cat)
        original_mode, original_anim = mesh.get_animation_mode(), mesh.get_anim_instance()
        sequence = u.load_asset(SEQUENCE)
        assert sequence
        settings = u.MovieSceneSequencePlaybackSettings()
        settings.set_editor_property('finish_completion_state_override', u.MovieSceneCompletionModeOverride.NONE)
        player, sequence_actor = u.LevelSequencePlayer.create_level_sequence_player(world, sequence, settings)
        sequence_actor.set_binding_by_tag('CatrunArrivalPawn',[cat],False)
        capture_actor = helper.ACTORS.spawn_actor_from_class(u.SceneCapture2D,u.Vector(),u.Rotator(),transient=True)
        target = u.RenderingLibrary.create_render_target2d(world,1280,720,u.TextureRenderTargetFormat.RTF_RGBA8,
                                                           u.LinearColor(0,0,0,1),False)
        component=capture_actor.get_component_by_class(u.SceneCaptureComponent2D)
        component.set_editor_property('texture_target',target)
        component.set_editor_property('capture_every_frame',False)
        component.set_editor_property('capture_on_movement',False)
        component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        component.set_editor_property('primitive_render_mode',u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        assert u.CatrunAuthoringLibrary.finish_asset_compilation()
        bindings=sequence.get_bindings()
        visual_binding=helper.only(b for b in bindings if b.get_name()=='CosmeticCat')
        portal_binding=helper.only(b for b in bindings if b.get_name()=='ArrivalPortal')
        player.play(); player.pause()
        spawned=set()
        for frame in FRAMES:
            helper.sequence_frame(player,frame)
            camera=player.get_active_camera_component()
            assert camera,('No evaluated camera',frame)
            visual=helper.only(player.get_bound_objects(sequence.get_binding_id(visual_binding)))
            portal=helper.only(player.get_bound_objects(sequence.get_binding_id(portal_binding)))
            spawned.update((visual.get_path_name(),portal.get_path_name(),camera.get_owner().get_path_name()))
            visual_mesh=visual.get_component_by_class(u.SkeletalMeshComponent)
            bones=[visual_mesh.get_bone_name(i) for i in range(visual_mesh.get_num_bones())]
            pose=helper.pose(visual_mesh,bones)
            row={'frame':frame,'seconds':frame/30.,'real_hidden':helper.hidden(cat),
                 'real_transform_unchanged':helper.same_transform(original,cat.get_actor_transform()),
                 'visual_transform':helper.transform(visual.get_actor_transform()),
                 'pose_hash':hashlib.sha256(json.dumps(pose).encode()).hexdigest(),
                 'paws':{b:helper.vector(visual_mesh.get_socket_location(b)) for b in ('paw_f_l','paw_f_r','paw_h_l','paw_h_r')},
                 'visual_collision':visual.get_actor_enable_collision(),'portal_collision':portal.get_actor_enable_collision(),
                 'capture':capture(world,capture_actor,target,camera,frame)}
            assert row['real_hidden'] and row['real_transform_unchanged'],row
            report['frames'].append(row)
            (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        player.stop()
        report['restored']=(helper.same_transform(original,cat.get_actor_transform()) and helper.hidden(cat)==original_hidden
                            and mesh.get_animation_mode()==original_mode and mesh.get_anim_instance()==original_anim)
        current={a.get_path_name() for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor)}
        report['spawnables_removed']=not spawned.intersection(current)
        assert report['restored'] and report['spawnables_removed']
        assert len({r['pose_hash'] for r in report['frames']})>4
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        if player: player.stop()
        for actor in (capture_actor,sequence_actor):
            if actor: helper.ACTORS.destroy_actor(actor)
        if target: u.RenderingLibrary.release_render_target2d(target)
        report['after']=hashes()
        report['inputs_unchanged']=report['before']==report['after']
        report['completed']=report['completed'] and report['inputs_unchanged']
        (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print('STAGE2_ARRIVAL_RENDER',report['completed'],str(OUT/'report.json'))
        assert report['inputs_unchanged']

main()
