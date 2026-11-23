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
FRAMES={0,16,38,39,56,57,96,138,176,188,194,195,215,230,231,245,254,255,266,278,285,291,293,294,311}
OCCLUSION=(266,280,291,293,294)
FACE_LIGHT=(57,96,138,176)


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


def capture_occlusion_passes(out,world,capture,target,camera,frame,actors,cat,mesh):
    component=capture.get_component_by_class(u.SceneCaptureComponent2D)
    original_source=component.get_editor_property('capture_source')
    original_shadow=mesh.get_editor_property('cast_shadow')
    original_hidden=r.hidden(cat)
    try:
        passes=[('Depth',u.SceneCaptureSource.SCS_DEVICE_DEPTH)]
        if frame in (291,293):
            passes.append(('NoCatShadow',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR))
        for name,source in passes:
            component.set_editor_property('capture_source',source)
            if name=='NoCatShadow':
                mesh.set_cast_shadow(False)
            for hidden in (False,True):
                cat.set_actor_hidden_in_game(hidden)
                folder=out/name/('Hidden' if hidden else 'Visible')
                folder.mkdir(parents=True,exist_ok=True)
                r.capture(world,capture,target,camera,folder,frame,actors)
    finally:
        cat.set_actor_hidden_in_game(original_hidden)
        mesh.set_cast_shadow(original_shadow)
        component.set_editor_property('capture_source',original_source)
    assert r.hidden(cat)==original_hidden and mesh.get_editor_property('cast_shadow')==original_shadow


def validate_depth_materials(mesh):
    materials=[mesh.get_material(i) for i in range(mesh.get_num_materials())]
    result={m.get_path_name():str(m.get_blend_mode()) for m in materials}
    assert materials and all(m.get_blend_mode() in (u.BlendMode.BLEND_OPAQUE,u.BlendMode.BLEND_MASKED)
                             for m in materials),('Non-depth-writing cat surface',result)
    return result


def check(out,report):
    assert not r.dirty_packages() and not h.ED.get_game_world()
    assert h.LEVEL.load_level(h.MAPS[0])
    world=h.ED.get_editor_world()
    actors=list(u.GameplayStatics.get_all_actors_of_class(world,u.Actor))
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    director=h.only(r.tagged(actors,'CatrunAuthoredStage1Exit'))
    door=director.get_editor_property('DepartureRearDoor')
    right=director.get_editor_property('DepartureRearDoorRight')
    open_rot=[a.get_actor_rotation().yaw for a in (door,right)]
    portal=director.get_editor_property('PortalPresentation')
    assert door and portal and not r.hidden(door)
    mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
    seq=h.load_asset(h.SEQUENCE)
    s.verify_sequence(seq)
    right_id=h.only(b for b in seq.get_bindings() if s.RIGHT_TAG in map(str,b.get_binding_tags()))
    door_id=h.only(b for b in seq.get_bindings() if s.DOOR_TAG in map(str,b.get_binding_tags()))
    initial=cat.get_actor_transform()
    initial_mode=mesh.get_animation_mode()
    orig_hidden=r.hidden(cat)
    settings=u.MovieSceneSequencePlaybackSettings()
    settings.set_editor_property('finish_completion_state_override',u.MovieSceneCompletionModeOverride.FORCE_RESTORE_STATE)
    player=sequence_actor=capture=target=None
    try:
        assert cat.set_actor_location_and_rotation(u.Vector(101,s.START_Y,25.2),u.Rotator(yaw=-90),False,True)
        staged=cat.get_actor_transform()
        player,sequence_actor=u.LevelSequencePlayer.create_level_sequence_player(world,seq,settings)
        for tag,actor in (('CatrunCat',cat),('CatrunPortal',portal),(s.DOOR_TAG,door),(s.RIGHT_TAG,right)):
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
        assert list(player.get_bound_objects(seq.get_binding_id(right_id)))==[right]
        blue=h.only(c for c in portal.get_components_by_class(u.PointLightComponent) if c.get_name()=='BlueLight')
        fill= h.only(c for c in portal.get_components_by_class(u.PointLightComponent) if c.get_name()==s.SOFT_FILL)
        assert list(player.get_bound_objects(seq.get_binding_id(s.fill_binding(seq))))==[fill]
        report['depth_materials']=validate_depth_materials(mesh)
        if report.get('occlusion_only'):
            all_actors=u.GameplayStatics.get_all_actors_of_class(world,u.Actor)
            for f in range(max(OCCLUSION)+1):
                r.sequence_frame(player,f)
                if f not in OCCLUSION:
                    continue
                camera=player.get_active_camera_component()
                assert camera and r.hidden(cat)==(f>=s.HIDE)
                capture_occlusion_passes(out,world,capture,target,camera,f,all_actors,cat,mesh)
                center,extent,_=u.SystemLibrary.get_component_bounds(mesh)
                rear_y=center.y+extent.y
                if f>=291:
                    assert rear_y<s.PORTAL_Y,(f,rear_y,s.PORTAL_Y)
                report['samples'].append(dict(frame=f,mesh_rear_y=rear_y,portal_y=s.PORTAL_Y,
                                              camera=h.tuple3(camera.get_world_location())))
            player.stop()
            assert not r.hidden(cat) and r.same_transform(staged,cat.get_actor_transform())
            return
        names=[str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]
        report['mesh']={'asset':mesh.get_skeletal_mesh_asset().get_path_name(),'bone_names':names}
        by_name={b.casefold():b for b in names}
        features=[b for b in names if b.casefold() in (*s.PAWS,'pelvis','head') or b.casefold().startswith(('ear','tail'))]
        assert all(b in by_name for b in ('head',*s.PAWS)),report['mesh']
        diff=out/'Occlusion'
        (out/'FaceBackground').mkdir()
        for folder in ('Visible','Hidden'):
            (diff/folder).mkdir(parents=True,exist_ok=False)
        previous_camera,previous_location=None,None
        report['camera_wall_sweeps']=report['subject_sightlines']=0
        for f in range(s.END):
            r.sequence_frame(player,f)
            camera=player.get_active_camera_component()
            assert camera and not any(r.hidden(a) for a in (door,right)) and r.hidden(cat)==(f>=s.HIDE),(f,'visibility or camera')
            if f>=39:
                assert max(abs(a.get_actor_rotation().yaw) for a in (door,right))<.02
            bones={b:h.tuple3(mesh.get_socket_location(b)) for b in features}
            view=camera.get_camera_view(0.)
            camera_name=camera.get_owner().get_name()
            start=previous_location if previous_camera==camera_name else view.location+u.Vector(0,0,.01)
            ignore=[cat,director,portal]
            hit=u.SystemLibrary.sphere_trace_single(world,start,view.location,2.,h.VISIBILITY,False,ignore,h.NONE,False)
            assert not hit,(f,'camera intersects map geometry',camera_name,hit.to_dict())
            report['camera_wall_sweeps']+=1
            previous_location,previous_camera=view.location,camera_name
            if f<s.HIDE and f%4==0:
                hit=u.SystemLibrary.line_trace_single(world,view.location,u.Vector(*bones[by_name['head']]),
                                                       h.VISIBILITY,False,ignore,h.NONE,False)
                assert not hit,(f,'head sightline',camera_name,hit.to_dict())
                report['subject_sightlines']+=1
            center,extent,_=u.SystemLibrary.get_component_bounds(mesh)
            row={'frame':f,'cat':h.tuple3(cat.get_actor_location()),'camera':camera.get_owner().get_name(),
                 'mesh_rear_y':center.y+extent.y,'bones':bones,'leaf_yaws':[a.get_actor_rotation().yaw for a in (door,right)],
                 'blue_fill':blue.intensity,'camera_side_fill_lumens':fill.intensity,
                 'light_positions':[h.tuple3(c.get_world_location()) for c in (blue,fill)],
                 'cat_visible':not r.hidden(cat)}
            if f<s.HIDE:
                view=camera.get_camera_view(0.)
                row['screen']={b:screen_point(view,xyz) for b,xyz in bones.items()}
                if s.REAR<=f<s.SIDE:
                    stone=h.only(c for c in portal.get_components_by_class(u.StaticMeshComponent) if c.get_name()=='Stone')
                    c,e,_=u.SystemLibrary.get_component_bounds(stone)
                    row['arch_top']=screen_point(view,(c.x,c.y,c.z+e.z))
            report['samples'].append(row)
            if f in FRAMES or f in OCCLUSION:
                all_actors=u.GameplayStatics.get_all_actors_of_class(world,u.Actor)
                row['image']=r.capture(world,capture,target,camera,out,f,all_actors)
                (out/'report.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
                if f in FACE_LIGHT:
                    cat.set_actor_hidden_in_game(True)
                    try:
                        r.capture(world,capture,target,camera,out/'FaceBackground',f,all_actors)
                    finally:
                        cat.set_actor_hidden_in_game(False)
                if f in OCCLUSION:
                    prior=r.hidden(cat)
                    cat.set_actor_hidden_in_game(False)
                    try:
                        r.capture(world,capture,target,camera,diff/'Visible',f,all_actors)
                        cat.set_actor_hidden_in_game(True)
                        r.capture(world,capture,target,camera,diff/'Hidden',f,all_actors)
                    finally:
                        cat.set_actor_hidden_in_game(prior)
                    capture_occlusion_passes(out,world,capture,target,camera,f,all_actors,cat,mesh)
        samples=report['samples']
        assert len({row['camera'] for row in samples})==len(s.CUTS)
        assert samples[s.HIDE]['mesh_rear_y']<s.PORTAL_Y
        assert samples[s.HIDE]['cat'][1]<s.PORTAL_Y-60
        assert math.dist(samples[s.STOP]['cat'],[101.,s.INSPECT_Y,25.2])<.1
        speeds=[math.dist(a['cat'],b['cat'])*30 for a,b in zip(samples[:s.WALK],samples[1:s.WALK+1])]
        expected=s.SPEED_PER_FRAME*30
        report['walk_speed_cm_s']={'expected':expected,'minimum':min(speeds),'maximum':max(speeds)}
        assert max(abs(v-expected) for v in speeds)<.1,report['walk_speed_cm_s']
        fills=[r['blue_fill'] for r in samples[s.WALK_START:s.WALK+1]]
        assert all(a<=b+.01 for a,b in zip(fills,fills[1:])) and fills[-1]>10*fills[0]
        paws=[b for b in features if b.casefold() in s.PAWS]
        for first,last in ((0,55),(57,s.WALK-1)):
            travel=[math.dist(a['bones'][b][:2],c['bones'][b][:2]) for a,c in zip(
                samples[first:last],samples[first+1:last+1]) for b in paws
                if max(a['bones'][b][2],c['bones'][b][2])<=4.3 and abs(a['bones'][b][2]-c['bones'][b][2])<=.15]
            assert len(travel)>10,(first,last,'few stance samples')
            med=statistics.median(travel)
            report.setdefault('planted_paw_motion',[]).append(dict(first=first,last=last,n=len(travel),median_cm_per_frame=med))
            assert med<.18,('Planted-paw drift',first,last,med)
        for row in samples:
            f=row['frame']
            if f<s.REAR:
                for b,xy in row['screen'].items():
                    if b.casefold() in ('head','ear_tip_l','ear_tip_r'):
                        assert all(.018<q<.982 for q in xy),('Head or ear cropped',f,b,xy)
                if s.WALK_START<=f<s.WALK:
                    head=row['screen'][by_name['head']]
                    assert abs(head[0]-.5)<.08 and abs(head[1]-.5)<.12,('Tracking center',f,head)
            if s.SIDE<=f<s.HIDE:
                for b,xy in row['screen'].items():
                    assert all(.025<q<.975 for q in xy),('Side/jump subject cropped',f,b,xy)
            if 'arch_top' in row:
                assert .015<row['arch_top'][1]<.45,('Arch top cropped or too low',f,row['arch_top'])
        player.stop()
        assert not any(r.hidden(a) for a in (door,right)) and r.same_transform(staged,cat.get_actor_transform())
        assert all(abs(a.get_actor_rotation().yaw-v)<.02 for a,v in zip((door,right),open_rot))
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
    focused='-catrundepartureocclusion' in u.SystemLibrary.get_command_line().lower()
    category='DepartureOcclusion' if focused else 'DepartureFrames'
    out=ROOT/'Saved/StageRevision20261123'/category/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    report={'samples':[],'completed':False,'occlusion_only':focused,
            'sequence_sha256':h.digest(h.asset_file(h.SEQUENCE)),'capture':'Evaluated scene capture; runtime UMG/fade requires PIE.'}
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
