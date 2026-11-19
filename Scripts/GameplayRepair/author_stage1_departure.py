"""Guarded Stage1 departure migration. Use -catrunDepartureAuthor or -catrunDepartureAudit."""
import datetime
import gc
import json
from pathlib import Path
import shutil
import sys
import traceback

import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/GameplayRepair'))
sys.path.insert(0,str(ROOT/'Scripts/Menu'))
import stage1_departure_shots as shots
from menu_graph import Graph, compile_bp, pin, wire

h=shots.h
ACTORS=u.get_editor_subsystem(u.EditorActorSubsystem)
DIRECTOR=h.BASE+'BP_Stage1PortalExit'
PACKAGES=(DIRECTOR,h.SEQUENCE,*h.MAPS)
BASELINE=ROOT/'Saved/GameplayRepair20261112/PortalFollowup/Fill/20261112-202339-934682/report.json'
PREFIX='S1_MagicCorridor_'
MODULES={'Floor_3':'Floor_2','WallEast_3':'WallEast_2','WallWest_3':'WallWest_2',
         'FloorBase_3':'FloorBase','Ceiling_3':'Ceiling','CeilingUnderside_3':'CeilingUnderside',
         'EastOuterShade_3':'EastOuterShade','WestOuterShade_3':'WestOuterShade'}
NATIVE='/Script/Catrun.CatrunExitTransitionComponent:ClearAcceptedStage1PortalMark'
VAR='DepartureRearDoor'


def hashes():
    return {p.relative_to(ROOT).as_posix(): h.digest(p) for p in (ROOT/'Content').rglob('*')
            if p.is_file() and p.suffix.lower() in {'.umap','.uasset','.uexp','.ubulk'}}


def load_map(package):
    assert not h.dirty(),h.dirty()
    gc.collect()
    assert h.LEVEL.load_level(package),package
    w=h.ED.get_editor_world()
    assert w.get_path_name().split('.')[0]==package and not h.ED.get_game_world()
    return list(u.GameplayStatics.get_all_actors_of_class(w,u.Actor))


def graph_nodes(graph, fn):
    return [i.node for i in BP.get_node_infos(BP.find_nodes(graph)) if str(i.type_id).endswith('|'+fn)]


def predecessor(node):
    return h.only(pin(node,'execute').list_connected_pins()).get_owning_node()


def function_timer(node):
    return str(pin(node,'FunctionName').get_pin_value()).strip('"')


def actor_rows(actors, skip):
    return {a.get_name(): (a.get_class().get_path_name(), a.get_actor_label(),a.get_actor_transform().export_text(),
                           tuple(map(str,a.tags)),sorted((c.get_name(), c.get_world_transform().export_text())
                                                       for c in a.get_components_by_class(u.SceneComponent)))
            for a in actors if a.get_name() not in skip}


def graph_rows(g):
    result={}
    for i in BP.get_node_infos(BP.find_nodes(g)):
        node=i.node
        result[node.get_name()]={'type':str(i.type_id),'pins':[
            [str(p.get_pin_direction()),str(p.get_pin_name()),str(p.get_pin_value()),
             sorted((q.get_owning_node().get_name(),str(q.get_pin_name())) for q in p.list_connected_pins())]
            for p in node.list_all_pins()]}
    return result


def director_state(bp):
    graph=BP.get_graph(bp,'EventGraph')
    play=h.only(graph_nodes(graph,'Play'))
    prev=predecessor(play)
    clear=graph_nodes(graph,'ClearAcceptedStage1PortalMark')
    if clear:
        assert prev==h.only(clear)
        prev=predecessor(prev)
    assert prev in graph_nodes(graph,'SetTimerbyFunctionName') and function_timer(prev)=='CinematicExpired', (prev.get_name(),function_timer(prev))
    door_bind=[n for n in graph_nodes(graph,'AddBindingByTag')
               if str(pin(n,'BindingTag').get_pin_value()).strip('"')==shots.DOOR_TAG]
    assert bool(clear)==bool(door_bind)
    if door_bind:
        node=h.only(door_bind)
        assert str(h.only(pin(node,'Actor').list_connected_pins()).get_pin_name())==VAR
        assert str(pin(predecessor(node),'BindingTag').get_pin_value()).strip('"')=='CatrunPortal'
        assert u.get_default_object(bp.generated_class()).get_editor_property('CinematicTimeout')==30.
    return bool(clear)


def patch_director(bp):
    bp.modify()
    BP.add_object_variable(bp,VAR,u.Actor.static_class())
    BP.set_variable_instance_editable(bp,VAR,True)
    compile_bp(bp)
    graph=BP.get_graph(bp,'EventGraph')
    before=graph_rows(graph)
    play=h.only(graph_nodes(graph,'Play'))
    watch=predecessor(play)
    bind=h.only(n for n in graph_nodes(graph,'AddBindingByTag')
                if str(pin(n,'BindingTag').get_pin_value()).strip('"')=='CatrunPortal')
    def insert_after(before_node, inserted):
        out=pin(before_node,'then',True)
        old=h.only(out.list_connected_pins())
        target=old.get_owning_node().get_name()
        out.break_single_pin_link(old)
        wire(before_node,'then',inserted,'execute')
        assert pin(inserted,'then',True).try_create_connection(old)
        return target
    q=Graph(graph,2150,-600)
    clear=q.fn(NATIVE,target=q.ref('ExitTransition'))
    add=q.fn('/Script/LevelSequence.LevelSequenceActor:AddBindingByTag',target=q.ref('CinematicActor'),
             BindingTag=shots.DOOR_TAG,Actor=q.ref(VAR),bAllowBindingsFromAsset='false')
    changed={watch.get_name(),insert_after(watch,clear),bind.get_name(),insert_after(bind,add)}
    compile_bp(bp)
    u.get_default_object(bp.generated_class()).set_editor_property('CinematicTimeout',30.)
    after=graph_rows(graph)
    assert before.keys()<=after.keys() and all(after[k]==v for k,v in before.items() if k not in changed)
    assert director_state(bp)


def tagged(actors,tag):
    return h.only(a for a in actors if tag in map(str,a.tags))


def label(actors,name):
    return h.only(a for a in actors if a.get_actor_label()==name)


def new_module(src,name):
    # Reuse the actual static mesh, every instance material, actor transform and ground/collision profile.
    old=src.static_mesh_component
    src_loc=src.get_actor_location()
    loc=u.Vector(src_loc.x,src_loc.y-200,src_loc.z)
    scale=src.get_actor_scale3d()
    if name not in ('Floor_3','WallEast_3','WallWest_3'):
        center,extent=src.get_actor_bounds(False)
        assert abs((center.y-extent.y)+415)<.1 and abs(src.get_actor_rotation().yaw)<.1
        loc=u.Vector(src_loc.x,-515,src_loc.z)
        scale=u.Vector(scale.x,scale.y*100/extent.y,scale.z)
    actor=ACTORS.spawn_actor_from_class(u.StaticMeshActor,loc,src.get_actor_rotation())
    assert actor
    actor.set_actor_label(PREFIX+name)
    actor.set_folder_path(src.get_folder_path())
    actor.tags=list(src.tags)
    c=actor.static_mesh_component
    c.set_static_mesh(old.get_editor_property('static_mesh'))
    for i in range(old.get_num_materials()):
        c.set_material(i,old.get_material(i))
    c.set_collision_profile_name(old.get_collision_profile_name())
    for prop in ('generate_overlap_events','cast_shadow','visible','hidden_in_game'):
        c.set_editor_property(prop,old.get_editor_property(prop))
    actor.set_actor_scale3d(scale)
    c.set_mobility(old.get_editor_property('mobility'))
    return actor


def saved_keys(channel, expected, tolerance=.001):
    keys=h.key_data(channel)
    assert len(keys)==len(expected) and all(t==h.tick(f) and abs(v-w)<=tolerance
        for (t,v),(f,w) in zip(keys,expected)), (str(channel),keys,expected)


def verified_tracks(seq,door,motion):
    state=shots.verify_sequence(seq)
    parts=h.sequence_parts(seq)
    animations=state['animations']
    rates=(motion['rate'],1.,17.5/(shots.LIFT-shots.JUMP),18.5/(shots.AIR_END-shots.LIFT),0.)
    for row,rate,st,off in zip(animations,rates,(0,0,0,17.5,0),(motion['first_loop_offset'],0,0,0,36.-1/800)):
        assert row['play_rate']==u.MovieSceneTimeWarpExtensions.make_time_warp(rate).export_text(),row
        assert (row['start_offset'],row['first_loop_offset'])==(h.tick(st),h.tick(off)),row
        assert row['custom_mode'] and row['skip_notifiers'],row
    for section,curve in zip(parts['camera_sections'],shots.CAMERAS):
        for i,ch in enumerate(h.transform_channels(section)):
            saved_keys(ch,[(f,axes[i]) for f,axes in curve])
    original=h.only(b for b in seq.get_bindings() if shots.DOOR_TAG in map(str,b.get_binding_tags()))
    proxy=h.only(b for b in seq.get_bindings() if b.get_name()==shots.PROXY)
    bound_mesh=proxy.get_object_template().static_mesh_component
    assert bound_mesh.get_editor_property('static_mesh')==door.static_mesh_component.get_editor_property('static_mesh')
    assert [bound_mesh.get_material(i) for i in range(bound_mesh.get_num_materials())]==[
        door.static_mesh_component.get_material(i) for i in range(door.static_mesh_component.get_num_materials())]
    start,closed=shots.door_profile(door)
    channels=h.transform_channels(h.property_section(proxy,u.MovieScene3DTransformTrack))
    for ch,value in zip(channels,start):
        assert abs(ch.get_default()-value)<.001
    yaw=[]
    for f in (0,15,20,25,30,35,40,45,50,54,shots.END-1):
        t=min(1.,max(0.,(f-15)/39))
        yaw.append((f,h.lerp(start[5],closed,t*t*(3-2*t))))
    saved_keys(channels[5],yaw)
    for actor,expected in ((original,[(0,False)]),(parts['bindings'][0],[(0,True),(shots.HIDE,False)])):
        track=h.property_track(actor,u.MovieSceneVisibilityTrack)
        section=h.only(track.get_sections())
        assert str(track.get_property_path())=='bHidden' and section.get_completion_mode()==shots.RESTORE
        saved_keys(h.only(section.get_all_channels()),expected)
    return {'camera_bindings':state['bindings'],'cuts':state['cuts'],'animations':animations,
            'closed_door_yaw':closed,'visibility_cut_frame':shots.HIDE}


def map_state(actors):
    director=tagged(actors,'CatrunAuthoredStage1Exit')
    portal=tagged(actors,'CatrunAuthoredStage1Portal')
    assert director.get_editor_property('PortalPresentation')==portal
    door=label(actors,shots.DOOR_LABEL)
    shots.door_profile(door)
    assert director.get_editor_property('CinematicActor').get_sequence()==h.load_asset(h.SEQUENCE)
    assert (director.get_actor_location()-u.Vector(101,-80,25.2)).length()<.1
    assert (director.get_editor_property('Trigger').get_unscaled_box_extent()-u.Vector(30,35,80)).length()<.1
    cap=label(actors,PREFIX+'DarkEnd')
    present={a.get_actor_label().removeprefix(PREFIX) for a in actors if a.get_actor_label() in [PREFIX+k for k in MODULES]}
    assert not present or present==set(MODULES), ('Partial corridor in saved map',present)
    done=bool(present)
    expected_y=shots.PORTAL_Y if done else shots.PORTAL_Y+200
    assert (portal.get_actor_location()-u.Vector(101,expected_y,-.8)).length()<.1
    assert abs(cap.get_actor_location().y-(-625 if done else -425))<.1
    if done:
        assert director.get_editor_property(VAR)==door and director.get_editor_property('CinematicTimeout')==30.
        for name in MODULES:
            a=label(actors,PREFIX+name)
            c,e=a.get_actor_bounds(False)
            assert abs(c.y+515)<.1 and abs(e.y-100)<.1,(name,c,e)
    return director,portal,cap,door,done


def map_work(package,author,original):
    actors=load_map(package)
    d,p,cap,door,done=map_state(actors)
    motion=shots.calibrate(h.only(a for a in actors if a.get_name()=='BP_Cat_C_0').get_component_by_class(u.SkeletalMeshComponent))
    seq=h.load_asset(h.SEQUENCE)
    if seq.get_playback_end()!=shots.END:
        allowed=(original[h.SEQUENCE],'52a45c63114aed4d5b963ac61a62ccc16c9d9dfe6ae77f965b4c2ba404ef3b58')
        assert author and package==h.MAPS[0] and h.digest(h.asset_file(h.SEQUENCE)) in allowed
        shots.patch(seq,door,motion)
        shots.verify_sequence(seq)
        assert h.AS.save_loaded_asset(seq,False)
    else:
        shots.verify_sequence(seq)
    if not done:
        assert author and h.digest(h.asset_file(package))==original[package], ('Unknown map',package)
        excluded={a.get_name() for a in (d,p,cap)}
        before=actor_rows(actors,excluded)
        for name,sourcename in MODULES.items():
            actor=new_module(label(actors,PREFIX+sourcename),name)
            excluded.add(actor.get_name())
        for a in (cap,p):
            a.modify()
            xyz=a.get_actor_location()
            assert a.set_actor_location(u.Vector(xyz.x,xyz.y-200,xyz.z),False,True)
        d.modify()
        d.set_editor_property(VAR,door)
        d.set_editor_property('CinematicTimeout',30.)
        current=list(u.GameplayStatics.get_all_actors_of_class(h.ED.get_editor_world(),u.Actor))
        assert actor_rows(current,excluded)==before, ('Unrelated actor changed',package)
        assert map_state(current)[-1]
        assert set(h.dirty())<={package},h.dirty()
        assert h.LEVEL.save_current_level()
    return dict(saved_map=not done,portal_y=shots.PORTAL_Y,gate_yaw=shots.door_profile(door),gait=motion,
                persisted_tracks=verified_tracks(seq,door,motion))


def geometry(package):
    # The former exact capsule sweeps, sampled floor support and camera traces are retained for the new curve.
    h.END,h.LIFT,h.AIR_END,h.EASE_FRAMES=shots.END,shots.LIFT,shots.AIR_END,shots.WALK
    h.PORTAL_Y,h.INSPECT_Y,h.ENTRY_Y=shots.PORTAL_Y,shots.INSPECT_Y,shots.ENTRY_Y
    h.CUTS,h.CAMERA_CURVES,h.cat_point=shots.CUTS,shots.CAMERAS,shots.position
    result=h.verify_map(package)
    # Validate capsule chords over delayed render/game ticks (8, 15 and 30 display frames),
    # including lift and the curved airborne path. Native checks each straight frame-to-frame chord.
    world=h.ED.get_editor_world()
    actors=list(u.GameplayStatics.get_all_actors_of_class(world,u.Actor))
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    radius,half=capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height()
    ignored=[cat,tagged(actors,'CatrunAuthoredStage1Exit')]
    chords=0
    for gap in (8,15,30):
        for frame in range(0,shots.END-1):
            end=min(frame+gap,shots.END-1)
            a,b=u.Vector(*shots.position(frame)),u.Vector(*shots.position(end))
            if (a-b).length()<.01:
                continue
            hit=u.SystemLibrary.capsule_trace_single_by_profile(world,a,b,radius,half,'Pawn',False,ignored,h.NONE,False)
            assert not hit,(package,'long-frame capsule chord',frame,end,hit.to_dict())
            chords+=1
    result['delayed_frame_sweeps']=chords
    lo,hi=shots.LIFT,shots.AIR_END
    for _ in range(24):
        mid=(lo+hi)/2
        if shots.position(mid)[1]>shots.PORTAL_Y: lo=mid
        else: hi=mid
    result['crossing_frame']=hi
    result['crossing_position']=shots.position(hi)
    assert abs(result['crossing_position'][1]-shots.PORTAL_Y)<.001
    return result


def main():
    cmd=u.SystemLibrary.get_command_line().lower()
    author='-catrundepartureauthor' in cmd
    assert author!=('-catrundepartureaudit' in cmd) and '-run=pythonscript' in cmd
    out=ROOT/'Saved/PresentationFix20261119/DepartureAuthor'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    report={'author':author,'completed':False,'maps':{},'geometry':{},'backups':{},'saved_packages':[]}
    before=None
    def persist():
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        assert not h.ED.get_game_world() and not h.dirty()
        original=json.loads(BASELINE.read_text(encoding='utf-8'))['after_hashes']
        before=hashes()
        (out/'before-sha256.json').write_text(json.dumps(before,indent=1),encoding='utf-8')
        report['content_packages']=len(before)
        if author:
            for package in PACKAGES:
                source=h.asset_file(package)
                dest=out/'Backup'/source.relative_to(ROOT/'Content')
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,dest)
                report['backups'][package]={'path':str(dest),'sha256':h.digest(dest)}
        persist()
        bp=h.load_asset(DIRECTOR)
        if not director_state(bp):
            assert author and h.digest(h.asset_file(DIRECTOR))==original[DIRECTOR]
            patch_director(bp)
            assert set(h.dirty())<={DIRECTOR} and h.AS.save_loaded_asset(bp,False)
        for package in h.MAPS:
            report['maps'][package]=map_work(package,author,original)
            persist()
        for package in h.MAPS:
            gc.collect()
            report['geometry'][package]=geometry(package)
            persist()
        assert not h.dirty(),h.dirty()
        after=hashes()
        report['changed_files']=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
        allowed={h.asset_file(p).relative_to(ROOT).as_posix() for p in PACKAGES} if author else set()
        assert set(report['changed_files'])<=allowed,report['changed_files']
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        if before is not None:
            now=hashes()
            (out/'after-sha256.json').write_text(json.dumps(now,indent=1),encoding='utf-8')
            report['changed_files']=sorted(k for k in before.keys()|now.keys() if before.get(k)!=now.get(k))
            report['saved_packages']=[p for p in PACKAGES if h.asset_file(p).relative_to(ROOT).as_posix() in report['changed_files']]
        persist()
        print('CATRUN_STAGE1_DEPARTURE',str(out),report['completed'])


if __name__=='__main__':
    main()
