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
CUT_FRAMES = (0, 17, 18, 22, 23, 32, 46, 56, 57, 62, 72, 86, 87, 88, 89, 90, 91, 145,
              199, 200, 229, 230, 239, 249, 250, 267, 284, 285, 286, 295, 305, 306, 323, 324, 344, 365, 389, 415,
              443, 444, 474, 502, 503)
OUT = ROOT / 'Saved/PresentationFix20261119/Stage2ArrivalFrames' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
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


def portal_details(actor):
    if not actor:
        return None
    return {'location':helper.vector(actor.get_actor_location()),
            'blue_intensity':actor.get_editor_property('BlueLight').get_editor_property('intensity'),
            'planes':{name:{'scale':helper.vector(item.get_relative_transform().scale3d),
                            'hidden':item.get_editor_property('hidden_in_game'), 'visible':item.is_visible()}
                      for name in ('Surface','PortalDepthCore','PortalAetherHalo')
                      for item in [actor.get_editor_property(name)]}}


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
        revised=sequence.get_playback_end()==504
        assert revised or sequence.get_playback_end()==360
        for frame in (CUT_FRAMES if revised else FRAMES):
            helper.sequence_frame(player,frame)
            camera=player.get_active_camera_component()
            assert camera,('No evaluated camera',frame)
            visual=helper.only(player.get_bound_objects(sequence.get_binding_id(visual_binding)))
            portals=list(player.get_bound_objects(sequence.get_binding_id(portal_binding)))
            assert len(portals)==int(not revised or frame<91),(frame,len(portals))
            portal=portals[0] if portals else None
            spawned.update([visual.get_path_name(),camera.get_owner().get_path_name()])
            if portal: spawned.add(portal.get_path_name())
            visual_mesh=visual.get_component_by_class(u.SkeletalMeshComponent)
            bones=[visual_mesh.get_bone_name(i) for i in range(visual_mesh.get_num_bones())]
            pose=helper.pose(visual_mesh,bones)
            row={'frame':frame,'seconds':frame/30.,'real_hidden':helper.hidden(cat),
                 'real_transform_unchanged':helper.same_transform(original,cat.get_actor_transform()),
                 'visual_transform':helper.transform(visual.get_actor_transform()),
                 'pose_hash':hashlib.sha256(json.dumps(pose).encode()).hexdigest(),
                 'paws':{b:helper.vector(visual_mesh.get_socket_location(b)) for b in ('paw_f_l','paw_f_r','paw_h_l','paw_h_r')},
                 'visual_collision':visual.get_actor_enable_collision(),'visual_hidden':helper.hidden(visual),
                 'visual_mesh_visible':visual_mesh.is_visible() and not visual_mesh.get_editor_property('hidden_in_game'),
                 'head':helper.vector(visual_mesh.get_socket_location('head')),
                 'portal':portal_details(portal),'portal_collision':portal.get_actor_enable_collision() if portal else None,
                 'capture':capture(world,capture_actor,target,camera,frame)}
            assert row['real_hidden'] and row['real_transform_unchanged'],row
            report['frames'].append(row)
            (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            if revised:
                assert row['visual_hidden']==(frame<23) and row['visual_mesh_visible'],(frame,row)
                if portal:
                    p=row['portal']
                    assert abs(p['location'][1]-3983)<.02,p
                    if frame in (0,62,72,86,87,90):
                        factor=1. if frame<=62 else .8 if frame==72 else .02
                        for name,plane in p['planes'].items():
                            xy=(1.18,2.02) if name=='PortalAetherHalo' else (1.05,1.8)
                            assert all(abs(v-s*factor)<.005 for v,s in zip(plane['scale'][:2],xy)),(frame,name,plane)
                            assert plane['hidden']==(frame>=87),(frame,name,plane)
                        if frame in (0,62,72,87,90):
                            expected=650 if frame<=62 else 520 if frame==72 else 0
                            assert abs(p['blue_intensity']-expected)<.1,(frame,p)
                in_pov=230<=frame<=305
                projection=u.CameraProjectionMode.PERSPECTIVE if in_pov else u.CameraProjectionMode.ORTHOGRAPHIC
                assert camera.projection_mode==projection,(frame,row['capture'])
                if in_pov:
                    assert all(abs(v-w)<.02 for v,w in zip(row['capture']['position'],(1374.7266,3680.1402,33.6515)))
                expected_width={200:84,306:84,443:910}.get(frame)
                if expected_width is not None:
                    assert abs(row['capture']['ortho_width']-expected_width)<.2,(frame,row['capture'])
        if revised:
            gaze=[]
            guide={230:(12.,3.,94.),239:(12.,3.,94.),250:(9.2,-16.,90.),267:(3.,-61.,78.),
                   284:(-3.1,-110.,61.),295:(-5.6,-126.7,55.),305:(-5.6,-126.7,55.)}
            for frame in range(230,306):
                helper.sequence_frame(player,frame)
                view=player.get_active_camera_component().get_camera_view(0.)
                assert view.projection_mode==u.CameraProjectionMode.PERSPECTIVE
                assert (view.location-u.Vector(1374.7266,3680.1402,33.6515)).length()<.02
                sample=[view.rotation.pitch,view.rotation.yaw,view.fov]
                if frame in guide:
                    assert all(abs(x-y)<.02 for x,y in zip(sample,guide[frame])),(frame,sample)
                if gaze:
                    for x,y,limit in zip(gaze[-1][1:],sample,(1.,4.,2.)):
                        assert -.02<=x-y<=limit,(frame,gaze[-1],sample)
                gaze.append([frame,*sample])
            report['evaluated_pov_gaze']=gaze
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
