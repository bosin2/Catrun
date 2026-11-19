"""Render evaluated departure shots in a cold commandlet with the actual map, cat and lights."""
import datetime
import json
import math
import statistics
from pathlib import Path
import sys
import traceback

import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/GameplayRepair'))
import stage1_departure_shots as s

h=s.h
r=s.definitions('render_portal_followup.py','main')
FRAMES={0,14,15,34,54,120,230,320,349,350,361,364,397,405,406,435,463,464,470,
        481,483,490,491,495,503,508,512,516,518,520,522,524,525,526,530,538}
FRAMES={f+s.EXTRA if f>=349 else f for f in FRAMES}


def screen_point(view,xyz):
    p,y=math.radians(view.rotation.pitch),math.radians(view.rotation.yaw)
    fwd=(math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p))
    right=(-math.sin(y),math.cos(y),0.)
    up=(-math.sin(p)*math.cos(y),-math.sin(p)*math.sin(y),math.cos(p))
    v=[a-b for a,b in zip(xyz,h.tuple3(view.location))]
    dot=lambda axis: sum(x*b for x,b in zip(v,axis))
    extent=dot(fwd)*math.tan(math.radians(view.fov)*.5)
    assert extent>0, ('Subject behind camera',xyz)
    return (.5+.5*dot(right)/extent, .5-.5*dot(up)*16/(9*extent))


def check(out,report):
    assert not r.dirty_packages() and not h.ED.get_game_world()
    assert h.LEVEL.load_level(h.MAPS[0])
    world=h.ED.get_editor_world()
    actors=list(u.GameplayStatics.get_all_actors_of_class(world,u.Actor))
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    director=h.only(r.tagged(actors,'CatrunAuthoredStage1Exit'))
    door=director.get_editor_property('DepartureRearDoor')
    portal=director.get_editor_property('PortalPresentation')
    assert door and portal and not r.hidden(door)
    mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
    seq=h.load_asset(h.SEQUENCE)
    s.verify_sequence(seq)
    proxy=h.only(b for b in seq.get_bindings() if b.get_name()==s.PROXY)
    door_id=h.only(b for b in seq.get_bindings() if s.DOOR_TAG in map(str,b.get_binding_tags()))
    initial=cat.get_actor_transform()
    initial_mode=mesh.get_animation_mode()
    orig_hidden=r.hidden(cat)
    settings=u.MovieSceneSequencePlaybackSettings()
    settings.set_editor_property('finish_completion_state_override',u.MovieSceneCompletionModeOverride.FORCE_RESTORE_STATE)
    player=sequence_actor=capture=target=None
    try:
        assert cat.set_actor_location_and_rotation(u.Vector(101,-80,25.2),u.Rotator(yaw=-90),False,True)
        staged=cat.get_actor_transform()
        player,sequence_actor=u.LevelSequencePlayer.create_level_sequence_player(world,seq,settings)
        for tag,actor in (('CatrunCat',cat),('CatrunPortal',portal),(s.DOOR_TAG,door)):
            sequence_actor.set_binding_by_tag(tag,[actor],False)
        capture=r.ACTORS.spawn_actor_from_class(u.SceneCapture2D,u.Vector(),u.Rotator(),transient=True)
        component=capture.get_component_by_class(u.SceneCaptureComponent2D)
        target=r.RENDER.create_render_target2d(world,1280,720,u.TextureRenderTargetFormat.RTF_RGBA8,u.LinearColor(0,0,0,1),False)
        component.set_editor_property('texture_target',target)
        component.set_editor_property('capture_every_frame',False)
        component.set_editor_property('capture_on_movement',False)
        component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        component.set_editor_property('primitive_render_mode',u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        assert u.CatrunAuthoringLibrary.finish_asset_compilation()
        player.play()
        player.pause()
        r.sequence_frame(player,0)
        assert list(player.get_bound_objects(seq.get_binding_id(door_id)))==[door]
        names=[str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]
        report['mesh']={'asset':mesh.get_skeletal_mesh_asset().get_path_name(),'bone_names':names}
        by_name={b.casefold():b for b in names}
        features=[b for b in names if b.casefold() in (*s.PAWS,'pelvis','head') or b.casefold().startswith(('ear','tail'))]
        assert all(b in by_name for b in ('head',*s.PAWS)),report['mesh']
        diff=out/'Occlusion'
        for folder in ('Visible','Hidden'):
            (diff/folder).mkdir(parents=True,exist_ok=False)
        for f in range(s.END):
            r.sequence_frame(player,f)
            camera=player.get_active_camera_component()
            assert camera and r.hidden(door) and r.hidden(cat)==(f>=s.HIDE),(f,'visibility or camera')
            visual=h.only(player.get_bound_objects(seq.get_binding_id(proxy)))
            if f in (0,54,525) or f in FRAMES:
                assert str(visual.static_mesh_component.get_collision_profile_name())=='NoCollision'
            bones={b:h.tuple3(mesh.get_socket_location(b)) for b in features}
            center,extent,_=u.SystemLibrary.get_component_bounds(mesh)
            row={'frame':f,'cat':h.tuple3(cat.get_actor_location()),'camera':camera.get_owner().get_name(),
                 'mesh_rear_y':center.y+extent.y,'bones':bones,'proxy_yaw':visual.get_actor_rotation().yaw,
                 'cat_visible':not r.hidden(cat)}
            if f<s.JUMP+1:
                view=camera.get_camera_view(0.)
                row['screen']={b:screen_point(view,xyz) for b,xyz in bones.items()
                               if b.casefold() in (*s.PAWS,'head','ear_tip_l','ear_tip_r')}
                if s.CUTS[1][0]<=f<s.CUTS[1][1]:
                    stone=h.only(c for c in portal.get_components_by_class(u.StaticMeshComponent) if c.get_name()=='Stone')
                    c,e,_=u.SystemLibrary.get_component_bounds(stone)
                    row['arch_top']=screen_point(view,(c.x,c.y,c.z+e.z))
            report['samples'].append(row)
            if f in FRAMES:
                all_actors=u.GameplayStatics.get_all_actors_of_class(world,u.Actor)
                row['image']=r.capture(world,capture,target,camera,out,f,all_actors)
                (out/'report.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
                if f-s.EXTRA in (503,518,522,525,526):
                    prior=r.hidden(cat)
                    cat.set_actor_hidden_in_game(False)
                    try:
                        r.capture(world,capture,target,camera,diff/'Visible',f,all_actors)
                        cat.set_actor_hidden_in_game(True)
                        r.capture(world,capture,target,camera,diff/'Hidden',f,all_actors)
                    finally:
                        cat.set_actor_hidden_in_game(prior)
        assert len({row['camera'] for row in report['samples']})==3
        assert report['samples'][s.HIDE]['mesh_rear_y'] < s.PORTAL_Y, 'A portion of the skinned mesh bounds remains in front of the portal'
        assert report['samples'][s.HIDE]['cat'][1] < s.PORTAL_Y-60
        assert math.dist(report['samples'][s.WALK+24]['cat'],[101.,-450.,25.2])<.1
        speeds=[math.dist(a['cat'],b['cat'])*30 for a,b in zip(report['samples'][:s.WALK],report['samples'][1:s.WALK+1])]
        speed=abs(s.WALK_Y+80)*30/s.WALK
        report['walk_speed_cm_s']={'expected':speed,'minimum':min(speeds),'maximum':max(speeds)}
        assert max(abs(v-speed) for v in speeds)<.1, ('Actual initial transform or gait speed drift',report['walk_speed_cm_s'])
        paws=[b for b in features if b.casefold() in s.PAWS]
        for first,last in ((0,32),(32,s.WALK-1)):
            travel=[math.dist(a['bones'][b][:2],c['bones'][b][:2]) for a,c in zip(
                report['samples'][first:last],report['samples'][first+1:last+1]) for b in paws
                if max(a['bones'][b][2],c['bones'][b][2])<=4.3 and abs(a['bones'][b][2]-c['bones'][b][2])<=.15]
            assert len(travel)>10,(first,last,'few stance samples')
            med=statistics.median(travel)
            report.setdefault('planted_paw_motion',[]).append(dict(first=first,last=last,n=len(travel),median_cm_per_frame=med))
            assert med<.18,('Visible planted-paw drift',first,last,med)
        for row in report['samples']:
            f=row['frame']
            if s.WALK<=f<s.JUMP:
                for b,xy in row['screen'].items():
                    if b in paws and f<s.CUTS[1][0]:
                        continue # The face shot frames ears/eyes; the two-shot and side shot include the feet.
                    assert all(.018<q<.982 for q in xy),('Subject cropped',f,b,xy)
            if 'arch_top' in row:
                assert .018<row['arch_top'][1]<.45,('Arch top cropped or too low',f,row['arch_top'])
        player.stop()
        assert not r.hidden(door) and r.same_transform(staged,cat.get_actor_transform())
        assert not r.hidden(cat) and mesh.get_animation_mode()==initial_mode
        report['stop_restores_door_pawn_and_animation']=True
    finally:
        if player:
            player.stop()
        for actor in (capture,sequence_actor):
            if actor:
                r.ACTORS.destroy_actor(actor)
        if target:
            r.RENDER.release_render_target2d(target)
        cat.set_actor_transform(initial,False,True)
        cat.set_actor_hidden_in_game(orig_hidden)


def main():
    out=ROOT/'Saved/PresentationFix20261119/DepartureFrames'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    report={'samples':[],'completed':False,'capture':'Evaluated scene capture; runtime UMG/fade requires PIE.'}
    before=r.asset_hashes()
    try:
        check(out,report)
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        report['packages_unchanged']=r.asset_hashes()==before
        (out/'report.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
        print('CATRUN_DEPARTURE_FRAMES',str(out),report['completed'])
        assert report['packages_unchanged']


if __name__=='__main__':
    main()
