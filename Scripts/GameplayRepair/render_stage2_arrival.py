"""Render actual saved arrival sequence samples in a fresh offscreen commandlet.

No package saves or gameplay ticks. This is sampled sequence evaluation, not
manual play; the companion runtime probe checks the real Blueprint lifecycle.
"""
import ast
import datetime
import hashlib
import json
import math
import sys
import os
from pathlib import Path
import traceback
import types
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path[:0]=[str(ROOT/'Scripts/GameplayRepair'),str(ROOT/'Scripts/Menu')]
import stage2_arrival_revision as revision

BASE = '/Game/Cinematics/Stage2/Arrival/'
SEQUENCE = BASE + 'LS_Stage2_PortalArrival'
MAP = '/Game/Maps/Stage2'
# Include every cut boundary, held target and light-key endpoint. Portal and
# landing frames also exercise the animated silhouette and actual floor contact.
FRAMES = sorted({0,9,10,19,33,44,54,62,72,86,87,90,91,250,270,310,360,revision.END-1,
                 *(f for _,a,b in revision.CUTS for f in (a,b-1)),
                 *(f for _,a,b,*_ in revision.GAZE_HOLDS for f in (a,(a+b)//2,b)),
                 *(f for name in revision.FILLS for f,_ in revision.fill_keys(name))})
OUT = ROOT/'Saved/StageRevision20261123/ArrivalFrames'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
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
    stone=actor.get_editor_property('Stone')
    return {'location':helper.vector(actor.get_actor_location()),'scale':helper.vector(actor.get_actor_scale3d()),
            'duplicate_stone_hidden':stone.get_editor_property('hidden_in_game') or not stone.is_visible(),
            'blue_intensity':actor.get_editor_property('BlueLight').get_editor_property('intensity'),
            'planes':{name:{'scale':helper.vector(item.get_relative_transform().scale3d),
                            'hidden':item.get_editor_property('hidden_in_game'), 'visible':item.is_visible()}
                      for name in ('Surface','PortalDepthCore','PortalAetherHalo')
                      for item in [actor.get_editor_property(name)]}}


def light_probe(sequence, player, bindings):
    result={}
    for name in revision.FILLS:
        binding=bindings[name]
        owners=list(player.get_bound_objects(sequence.get_binding_id(binding)))
        bulbs=list(player.get_bound_objects(sequence.get_binding_id(bindings[name+'Bulb'])))
        row={'owners':[a.get_path_name() for a in owners], 'bulbs':[b.get_path_name() for b in bulbs],
             'template_actor_collision':binding.get_object_template().get_actor_enable_collision(), 'valid':False}
        result[name]=row
        if len(owners)!=1 or len(bulbs)!=1:
            continue
        actor=owners[0]
        expected=actor.get_editor_property('PointLightComponent')
        bulb=bulbs[0]
        primitives=[{'name':p.get_name(),'type':p.get_class().get_name(),'collision':str(p.get_collision_enabled()),
                     'query':p.is_query_collision_enabled(),'physics':p.is_physics_collision_enabled(),
                     'simulating':p.is_simulating_physics(),'overlap_flag':p.get_editor_property('generate_overlap_events'),
                     'no_collision':p.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION}
                    for p in actor.get_components_by_class(u.PrimitiveComponent)]
        row.update(expected=expected.get_path_name(),bound_owner=bulb.get_owner().get_path_name(),
                   actor_collision=actor.get_actor_enable_collision(),primitives=primitives,
                   correct_bulb=bulb==expected and bulb.get_owner()==actor)
        # APointLight's bulb is a USceneComponent. Only its primitive components
        # can expose collision bodies, and even its editor visualization must be inert.
        row['valid']=row['correct_bulb'] and all(p['no_collision'] and not (p['query'] or p['physics'] or p['simulating'])
                                                  for p in primitives)
    return result


def screen_point(view,xyz):
    delta=u.Vector(*xyz)-view.location
    right=u.MathLibrary.get_right_vector(view.rotation)
    up=u.MathLibrary.get_up_vector(view.rotation)
    depth=u.MathLibrary.get_forward_vector(view.rotation).dot(delta)
    half_width=(depth*math.tan(math.radians(view.fov)*.5)
                if view.projection_mode==u.CameraProjectionMode.PERSPECTIVE else view.ortho_width*.5)
    assert depth>0 and half_width>0
    return [.5+.5*right.dot(delta)/half_width,.5-.5*up.dot(delta)*view.aspect_ratio/half_width]


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
        lights={b.get_name():b for b in bindings if b.get_name() in revision.FILLS or
                b.get_name() in {n+'Bulb' for n in revision.FILLS}}
        assert len(lights)==2*len(revision.FILLS),'Missing light or component binding'
        player.play(); player.pause()
        helper.sequence_frame(player,0)
        report['light_probe']=light_probe(sequence,player,lights)
        print('STAGE2_ARRIVAL_LIGHT_PROBE',json.dumps(report['light_probe']))
        assert all(r['valid'] for r in report['light_probe'].values()),report['light_probe']
        spawned=set()
        assert sequence.get_playback_end()==revision.END
        actors={a.get_actor_label():a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor)}
        for frame in FRAMES:
            helper.sequence_frame(player,frame)
            camera=player.get_active_camera_component()
            assert camera,('No evaluated camera',frame)
            visual=helper.only(player.get_bound_objects(sequence.get_binding_id(visual_binding)))
            portals=list(player.get_bound_objects(sequence.get_binding_id(portal_binding)))
            assert len(portals)==int(frame<revision.PORTAL_END),(frame,len(portals))
            portal=portals[0] if portals else None
            spawned.update([visual.get_path_name(),camera.get_owner().get_path_name()])
            if portal: spawned.add(portal.get_path_name())
            fills={}
            for name in revision.FILLS:
                light=helper.only(player.get_bound_objects(sequence.get_binding_id(lights[name])))
                bulb=helper.only(player.get_bound_objects(sequence.get_binding_id(lights[name+'Bulb'])))
                assert bulb==light.get_editor_property('PointLightComponent') and bulb.get_owner()==light,(frame,name,bulb,light)
                intensity=bulb.get_editor_property('intensity')
                keys=revision.fill_keys(name)
                keyed=dict(keys)
                if frame in keyed:
                    assert abs(intensity-keyed[frame])<.1,(frame,name,intensity,keyed[frame])
                else:
                    left,right=next((a,b) for a,b in zip(keys,keys[1:]) if a[0]<frame<b[0])
                    lo,hi=sorted((left[1],right[1]))
                    assert lo-.1<=intensity<=hi+.1,(frame,name,intensity,left,right)
                fills[name]={'lumens':intensity,'location':helper.vector(light.get_actor_location())}
                spawned.add(light.get_path_name())
            visual_mesh=visual.get_component_by_class(u.SkeletalMeshComponent)
            bones=[visual_mesh.get_bone_name(i) for i in range(visual_mesh.get_num_bones())]
            pose=helper.pose(visual_mesh,bones)
            row={'frame':frame,'seconds':frame/30.,'real_hidden':helper.hidden(cat),'cinematic_lights':fills,
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
            assert row['visual_hidden']==(frame<revision.REVEAL) and row['visual_mesh_visible'],(frame,row)
            if portal:
                p=row['portal']
                assert math.dist(p['location'],revision.PORTAL_LOCATION)<.03 and math.dist(p['scale'],(1.25,)*3)<.005,p
                assert p['duplicate_stone_hidden'],(frame,p)
                if frame in (0,62,72,86,87,90):
                    factor=1. if frame<=62 else .8 if frame==72 else .02
                    for name,plane in p['planes'].items():
                        xy=(1.18,2.02) if name=='PortalAetherHalo' else (1.05,1.8)
                        assert all(abs(v-s*factor)<.005 for v,s in zip(plane['scale'][:2],xy)),(frame,name,plane)
                        assert plane['hidden']==(frame>=87),(frame,name,plane)
                    if frame in (0,62,72,87,90):
                        assert abs(p['blue_intensity']-(650 if frame<=62 else 520 if frame==72 else 0))<.1
            view=camera.get_camera_view(0.)
            name=next(n for n,f,t in revision.CUTS if f<=frame<t)
            assert (view.projection_mode==u.CameraProjectionMode.PERSPECTIVE)==(name in revision.PERSPECTIVE)
            key=next((k for k,a,b,*_ in revision.GAZE_HOLDS if a<=frame<=b),None)
            if key:
                xyz=revision.TARGETS[key]
                actor=actors[revision.LABELS[key]]
                assert math.dist(helper.vector(actor.get_actor_location())[:2],xyz[:2])<.03
                if key=='gate':
                    assert abs(actor.get_actor_location().z+20.)<.05 and actor.get_actor_enable_collision() and not helper.hidden(actor)
            elif frame>=revision.REVEAL and name!='Puzzle':
                xyz=row['head']
                actor=visual
            else:
                continue
            screen=screen_point(view,xyz)
            ignore=[visual,cat,camera.get_owner(),actor]
            hit=u.SystemLibrary.line_trace_single(world,view.location,u.Vector(*xyz),u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                  True,ignore,u.DrawDebugTrace.NONE,False)
            row['subject']={'label':key or 'cat head','screen':screen,
                            'occluder':hit.to_dict()['hit_actor'].get_actor_label() if hit else None}
            assert not hit,(frame,row['subject'])
            assert all(.015<coord<.985 for coord in screen),(frame,row['subject'])
            if key:
                # The eye-level wide shot places each objective on a different horizontal third.
                expected_x={'statue':.68,'plate':.27,'gate':.53}[key]
                assert abs(screen[0]-expected_x)<.07 and .40<screen[1]<.60,(frame,row['subject'])
            if name in ('Face','FaceReturn') and frame<revision.HANDOFF_FRAME:
                row['face_features']={n:screen_point(view,helper.vector(visual_mesh.get_socket_location(n)))
                                      for n in ('head','ear_tip_L','ear_tip_R')}
                assert all(.03<v<.97 for xy in row['face_features'].values() for v in xy),(frame,row['face_features'])
            if name=='RearWalk':
                row['room_gate_screen']=screen_point(view,revision.TARGETS['gate'])
                assert all(.02<v<.98 for v in row['room_gate_screen']),(frame,row['room_gate_screen'])
        soles={r['frame']:min(v[2] for v in r['paws'].values()) for r in report['frames']}
        assert soles[19]>soles[10]+15. and soles[19]>soles[33]>soles[44]
        assert all(2.<soles[f]<7. for f in (44,54,62,72)),soles
        last_cam=last_location=None
        gaze=[]
        for f in range(revision.END):
            helper.sequence_frame(player,f)
            camera=player.get_active_camera_component()
            view=camera.get_camera_view(0.)
            start=last_location if last_cam==camera.get_owner() else view.location+u.Vector(0,0,.01)
            hit=u.SystemLibrary.sphere_trace_single(world,start,view.location,2.,u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                    False,[cat],u.DrawDebugTrace.NONE,False)
            assert not hit,(f,'camera obstruction',str(hit))
            last_cam,last_location=camera.get_owner(),view.location
            first,last=revision.CUT_RANGES['Puzzle']
            if first<=f<last:
                assert 32.<view.location.z<47. and abs(view.rotation.roll)<.05
                sample=[f,*helper.vector(view.location),view.rotation.pitch,view.rotation.yaw,view.fov]
                if gaze:
                    assert math.dist(gaze[-1][1:4],sample[1:4])<5.0
                    assert all(abs(i-j)<limit for i,j,limit in zip(gaze[-1][4:],sample[4:],(2.,8.,3.5)))
                gaze.append(sample)
        report['camera_sweep_frames']=revision.END
        report['continuous_puzzle_view']=gaze
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
