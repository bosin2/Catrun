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
VAR,RIGHT_VAR='DepartureRearDoor','DepartureRearDoorRight'
MESH_PATH='/Game/Environment/Stage2/Architecture/Doors/ArchedIronDoor/Meshes/SM_Stage2_ArchedIronDoor_'
TRIGGER_CENTER=(100.,-315.,25.2)
TRIGGER_EXTENT=(100.,300.,80.)
FRAME_ORIGIN=(.9,15.,-.8)
GATE_Z_SCALE=.92


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


def tagged(actors,tag):
    return h.only(a for a in actors if tag in map(str,a.tags))


def label(actors,name):
    return h.only(a for a in actors if a.get_actor_label()==name)


def binding_nodes(bp):
    graph=BP.get_graph(bp,'EventGraph')
    return {str(pin(n,'BindingTag').get_pin_value()).strip('"'):n for n in graph_nodes(graph,'AddBindingByTag')}


def director_state(bp):
    by_tag=binding_nodes(bp)
    left=by_tag[shots.DOOR_TAG]
    assert str(h.only(pin(left,'Actor').list_connected_pins()).get_pin_name())==VAR
    if shots.RIGHT_TAG not in by_tag:
        return False
    right=by_tag[shots.RIGHT_TAG]
    assert predecessor(right)==left and str(h.only(pin(right,'Actor').list_connected_pins()).get_pin_name())==RIGHT_VAR
    return True


def patch_director(bp):
    bp.modify()
    BP.add_object_variable(bp,RIGHT_VAR,u.Actor.static_class())
    BP.set_variable_instance_editable(bp,RIGHT_VAR,True)
    compile_bp(bp)
    g=BP.get_graph(bp,'EventGraph')
    before=graph_rows(g)
    left=binding_nodes(bp)[shots.DOOR_TAG]
    link=pin(left,'then',True)
    downstream=h.only(link.list_connected_pins())
    changed={left.get_name(),downstream.get_owning_node().get_name()}
    q=Graph(g,3020,-950)
    right=q.fn('/Script/LevelSequence.LevelSequenceActor:AddBindingByTag',target=q.ref('CinematicActor'),
               BindingTag=shots.RIGHT_TAG,Actor=q.ref(RIGHT_VAR),bAllowBindingsFromAsset='false')
    link.break_single_pin_link(downstream)
    wire(left,'then',right,'execute')
    assert pin(right,'then',True).try_create_connection(downstream)
    compile_bp(bp)
    after=graph_rows(g)
    assert before.keys()<=after.keys() and all(before[k]==after[k] for k in before if k not in changed)
    assert director_state(bp)


def checked_meshes():
    expected={'Frame':((0,-30,0),(200,0,300)),
              'Leaf_L':((-1.4,-17.1084,1),(68,1.5084,237.995)),
              'Leaf_R':((-68,-17.1084,1),(1.4,1.5084,237.995))}
    meshes={}
    for name,(low,high) in expected.items():
        mesh=meshes[name]=h.load_asset(MESH_PATH+name)
        box=mesh.get_bounding_box()
        assert (box.min-u.Vector(*low)).length()<.02 and (box.max-u.Vector(*high)).length()<.02,(name,box)
    return meshes


def setup_part(actor,mesh,location,yaw,movable):
    actor.modify()
    c=actor.static_mesh_component
    c.modify()
    c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(mesh)
    c.set_editor_property('override_materials',[])
    c.set_collision_profile_name('BlockAllDynamic' if movable else 'BlockAll')
    c.set_editor_property('generate_overlap_events',False)
    actor.set_actor_scale3d(u.Vector(1.,1.,GATE_Z_SCALE))
    assert actor.set_actor_location_and_rotation(u.Vector(*location),u.Rotator(yaw=yaw),False,True)
    if not movable:
        c.set_mobility(u.ComponentMobility.STATIC)
    assert c.get_material(0)==mesh.get_material(0)


def verify_map(actors):
    director=tagged(actors,'CatrunAuthoredStage1Exit')
    portal=tagged(actors,'CatrunAuthoredStage1Portal')
    assert director.get_editor_property('PortalPresentation')==portal
    assert director.get_editor_property('CinematicActor').get_sequence()==h.load_asset(h.SEQUENCE)
    assert (director.get_actor_location()-u.Vector(*TRIGGER_CENTER)).length()<.02
    assert (director.get_editor_property('Trigger').get_unscaled_box_extent()-u.Vector(*TRIGGER_EXTENT)).length()<.02
    assert director.get_editor_property('bProtectStage1Corridor') and director.get_editor_property('bUseExitTransition')
    assert director.get_editor_property('bRequireCenterInside')
    assert (director.get_editor_property('InteriorDirectionLocal')-u.Vector(0,-1,0)).length()<.001
    assert abs(director.get_editor_property('CorridorEntryDepth')-(TRIGGER_CENTER[1]-shots.THRESHOLD_Y))<.001
    assert abs(director.get_editor_property('MinimumInteriorDepth')-(TRIGGER_CENTER[1]-shots.START_Y))<.001
    assert (portal.get_actor_location()-u.Vector(101.,shots.PORTAL_Y,-.8)).length()<.01
    assert (portal.get_actor_scale3d()-u.Vector(1.25,1.25,1.25)).length()<.01
    stone=h.only(c for c in portal.get_components_by_class(u.StaticMeshComponent) if c.get_name()=='Stone')
    center,extent,_=u.SystemLibrary.get_component_bounds(stone)
    assert center.z+extent.z<=279 and center.x-extent.x>=-1 and center.x+extent.x<=201,(center,extent)
    left,right=director.get_editor_property(VAR),director.get_editor_property(RIGHT_VAR)
    for actor,key,yaw,x,y in ((label(actors,shots.FRAME_LABEL),'Frame',0.,0.,0.),
                              (left,'Leaf_L',-100.,31.5,-1.6),(right,'Leaf_R',100.,168.5,-1.6)):
        c=actor.static_mesh_component
        assert c.get_editor_property('static_mesh')==h.load_asset(MESH_PATH+key)
        assert abs(actor.get_actor_rotation().yaw-yaw)<.01
        assert (actor.get_actor_location()-u.Vector(FRAME_ORIGIN[0]+x,FRAME_ORIGIN[1]+y,FRAME_ORIGIN[2])).length()<.01
        assert c.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_BLOCK
    return director,portal,left,right


def map_work(package,author):
    actors=load_map(package)
    director=tagged(actors,'CatrunAuthoredStage1Exit')
    portal=tagged(actors,'CatrunAuthoredStage1Portal')
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    movement=cat.get_component_by_class(u.CharacterMovementComponent)
    assert abs(movement.max_walk_speed-shots.WALK_SPEED)<.01,movement.max_walk_speed
    motion=shots.calibrate(cat.get_component_by_class(u.SkeletalMeshComponent))
    seq=h.load_asset(h.SEQUENCE)
    saved=False
    if not director.get_editor_property(RIGHT_VAR):
        assert author,('Stage1 exit requires migration',package)
        left=director.get_editor_property(VAR)
        frame=label(actors,shots.FRAME_LABEL)
        assert left==label(actors,shots.DOOR_LABEL)
        assert 'Stage2TransitionDoor' in map(str,left.tags) and 'Stage2TransitionDoorFrame' in map(str,frame.tags)
        assert not any(a.get_actor_label()==shots.RIGHT_LABEL for a in actors)
        assert (portal.get_actor_location()-u.Vector(101.,-493.9189189,-.8)).length()<.01
        meshes=checked_meshes()
        excluded={a.get_name() for a in (frame,left,portal,director)}
        before=actor_rows(actors,excluded)
        right=ACTORS.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*FRAME_ORIGIN),u.Rotator())
        right.set_actor_label(shots.RIGHT_LABEL)
        right.set_folder_path(left.get_folder_path())
        right.tags=['Stage2TransitionDoorRight']
        excluded.add(right.get_name())
        for a,name,x,y,yaw in ((frame,'Frame',0.,0.,0.),(left,'Leaf_L',31.5,-1.6,-100.),
                               (right,'Leaf_R',168.5,-1.6,100.)):
            setup_part(a,meshes[name],(FRAME_ORIGIN[0]+x,FRAME_ORIGIN[1]+y,FRAME_ORIGIN[2]),yaw,a!=frame)
        director.modify()
        trigger=director.get_editor_property('Trigger')
        trigger.modify()
        assert director.set_actor_location(u.Vector(*TRIGGER_CENTER),False,True)
        trigger.set_box_extent(u.Vector(*TRIGGER_EXTENT),False)
        director.set_editor_property('InteriorDirectionLocal',u.Vector(0,-1,0))
        director.set_editor_property('bProtectStage1Corridor',True)
        director.set_editor_property('bRequireCenterInside',True)
        director.set_editor_property('CorridorEntryDepth',TRIGGER_CENTER[1]-shots.THRESHOLD_Y)
        director.set_editor_property('MinimumInteriorDepth',TRIGGER_CENTER[1]-shots.START_Y)
        director.set_editor_property(RIGHT_VAR,right)
        portal.modify()
        portal.set_actor_scale3d(u.Vector(1.25,1.25,1.25))
        assert portal.set_actor_location(u.Vector(101.,shots.PORTAL_Y,-.8),False,True)
        actors=list(u.GameplayStatics.get_all_actors_of_class(h.ED.get_editor_world(),u.Actor))
        assert actor_rows(actors,excluded)==before
        saved=True
    _,_,left,right=verify_map(actors)
    door_checks=door_collision(cat,director,left,right) if saved else {}
    migration=seq.get_playback_end()!=shots.END
    if migration or not shots.fill_binding(seq):
        assert author and package==h.MAPS[0]
        if migration:
            shots.patch(seq,left,right,motion)
        else:
            # The 312-frame published-in-workspace revision has known IDs and known bytes.
            # For it change only camera properties/tracks and the two existing portal lights.
            assert h.digest(h.asset_file(h.SEQUENCE))==shots.PREVIOUS_SEQUENCE_SHA
        shots.apply_lens_and_fill(seq,portal)
        shots.verify_sequence(seq)
        assert set(h.dirty())<={package,h.SEQUENCE},h.dirty()
        assert h.AS.save_loaded_asset(seq,False)
    state=shots.verify_sequence(seq)
    if saved:
        assert set(h.dirty())<={package},h.dirty()
        assert h.LEVEL.save_current_level()
    return dict(saved=saved,portal_y=shots.PORTAL_Y,ground_walk_speed=movement.max_walk_speed,
                start_y=shots.START_Y,door_checks=door_checks,gait=motion,cuts=state['cuts'],animations=state['animations'])


def capsule_hit(cat,director,start,end):
    c=cat.get_component_by_class(u.CapsuleComponent)
    return u.SystemLibrary.capsule_trace_single_by_profile(h.ED.get_editor_world(),u.Vector(*start),u.Vector(*end),
        c.get_scaled_capsule_radius(),c.get_scaled_capsule_half_height(),'Pawn',False,[cat,director],h.NONE,False)


def door_collision(cat,director,left,right):
    # Validate the installed leaf bodies (including the central seam) before saving.
    rots=[a.get_actor_rotation() for a in (left,right)]
    across=lambda x:capsule_hit(cat,director,(x,70.,25.2),(x,-80.,25.2))
    opened=[across(x) for x in (79.,101.,123.)]
    assert not any(opened),('open door obstruction',[hit.to_dict() if hit else None for hit in opened])
    try:
        for a in (left,right):
            assert a.set_actor_rotation(u.Rotator(),True)
        closed=[across(x) for x in (70.,101.,130.)]
        assert all(hit and hit.to_dict()['hit_actor'] in (left,right) for hit in closed),[
            hit.to_dict() if hit else None for hit in closed]
        assert {hit.to_dict()['hit_actor'] for hit in closed}=={left,right}
        return {'open_sweeps':3,'closed_hits':[hit.to_dict()['hit_actor'].get_actor_label() for hit in closed]}
    finally:
        for actor,rotation in zip((left,right),rots):
            actor.set_actor_rotation(rotation,True)


def geometry(package):
    actors=load_map(package)
    d,p,left,right=verify_map(actors)
    cat=h.only(a for a in actors if a.get_name()=='BP_Cat_C_0')
    rows={'capsule_sweeps':0,'floor_supports':0}
    for x in (25.,101.,175.):
        origin=(x,shots.START_Y,25.2)
        for gap in (1,8,15,30):
            for f in range(0,shots.END-1,2):
                start=shots.position(f,origin)
                end=shots.position(min(f+gap,shots.END-1),origin)
                hit=capsule_hit(cat,d,start,end)
                assert not hit,(package,'capsule chord',x,f,gap,hit.to_dict())
                rows['capsule_sweeps']+=1
                if gap==1 and f<shots.LIFT:
                    x_,y,z=start
                    floor=capsule_hit(cat,d,(x_,y,z+12),(x_,y,z-9))
                    assert floor and floor.to_dict()['impact_normal'].z>=.65,(package,f,start)
                    rows['floor_supports']+=1
    assert not h.dirty(),h.dirty()
    return rows


def main():
    cmd=u.SystemLibrary.get_command_line().lower()
    author='-catrundepartureauthor' in cmd
    assert author!=('-catrundepartureaudit' in cmd) and '-run=pythonscript' in cmd
    out=ROOT/'Saved/StageRevision20261123/DepartureAuthor'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    report={'author':author,'completed':False,'maps':{},'geometry':{},'backups':{},'saved_packages':[]}
    before=None
    def persist():
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        assert not h.ED.get_game_world() and not h.dirty()
        checked_meshes()
        before=hashes()
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
            assert author
            patch_director(bp)
            assert set(h.dirty())<={DIRECTOR} and h.AS.save_loaded_asset(bp,False)
        for pkg in h.MAPS:
            report['maps'][pkg]=map_work(pkg,author)
            persist()
        for pkg in h.MAPS:
            report['geometry'][pkg]=geometry(pkg)
            persist()
        assert not h.dirty(),h.dirty()
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        if before is not None:
            after=hashes()
            changed=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
            report['changed_files']=changed
            report['saved_packages']=[p for p in PACKAGES if h.asset_file(p).relative_to(ROOT).as_posix() in changed]
            allowed={h.asset_file(p).relative_to(ROOT).as_posix() for p in PACKAGES} if author else set()
            if not set(changed)<=allowed:
                report['completed']=False
                report['unexpected_saves']=sorted(set(changed)-allowed)
        persist()
        print('CATRUN_STAGE1_DEPARTURE',str(out),report['completed'])
        assert 'unexpected_saves' not in report,report


if __name__=='__main__':
    main()
