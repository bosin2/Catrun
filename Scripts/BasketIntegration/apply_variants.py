"""Replace existing basket presentation only, keeping actor identities and level layout."""
import unreal as u,json,hashlib,shutil,traceback
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/BasketIntegration20261125'
I=json.loads((OUT/'import_report.json').read_text());assert I['success']
EA=u.EditorAssetLibrary;LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem);ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
DIRS=['F','FR','R','BR','B','BL','L','FL'];REPORT={'maps':{}}
def persist(): (OUT/'apply_report.json').write_text(json.dumps(REPORT,indent=2,ensure_ascii=False),encoding='utf8')
def load(path):
    a=EA.load_asset(path);assert a,path;return a
AN={k:load(v['path']) for k,v in I['animations'].items()}
MESH={int(k):{n:load(v[n]) for n in ['body','cloth']} for k,v in I['stages'].items()}
def xyz(v):return [round(v.x,5),round(v.y,5),round(v.z,5)]
def rotation(v):return [round(v.pitch,5),round(v.yaw,5),round(v.roll,5)]
def prop_actor(a):
    return {'class':a.get_class().get_path_name(),'location':xyz(a.get_actor_location()),'rotation':rotation(a.get_actor_rotation()),'scale':xyz(a.get_actor_scale3d()),'tags':[str(t) for t in a.tags]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def backup(rel):
    src=ROOT/rel;dst=OUT/'Before'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    # Preserve the first pre-edit disk version; parallel work is loaded fresh per map.
    if not dst.exists():shutil.copy2(src,dst)
    return sha(src)
def setup_cloth(c,stage):
    c.set_skeletal_mesh_asset(MESH[stage]['cloth'])
    c.set_editor_property('override_materials',[])
    c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    c.set_editor_property('animation_mode',u.AnimationMode.ANIMATION_SINGLE_NODE)
    data=u.SingleAnimationPlayData(anim_to_play=AN['AN_Cloth_IdleEmpty'],saved_looping=False,saved_playing=False,saved_position=0.,saved_play_rate=1.)
    c.set_editor_property('animation_data',data)
def setup_actor(a,defaults=False):
    a.set_editor_property('ClothEnterDirections',[AN['AN_Cloth_Enter_'+d] for d in DIRS])
    a.set_editor_property('ClothExitDirections',[AN['AN_Cloth_Exit_'+d] for d in DIRS])
    if defaults:
        a.set_editor_property('ClothEnterAnimation',AN['AN_Cloth_Enter_F']);a.set_editor_property('ClothExitAnimation',AN['AN_Cloth_Exit_F'])
        a.set_editor_property('ClothIdleAnimation',AN['AN_Cloth_IdleEmpty'])
    a.set_editor_property('ClothHiddenAnimation',AN['AN_Cloth_IdleHidden'])
def templates(bp):
    sys=u.get_engine_subsystem(u.SubobjectDataSubsystem);lib=u.SubobjectDataBlueprintFunctionLibrary
    objs=[lib.get_associated_object(lib.get_data(h)) for h in sys.k2_gather_subobject_data_for_blueprint(bp)]
    return {o.get_name().removesuffix('_GEN_VARIABLE'):o for o in objs if isinstance(o,u.ActorComponent)}
try:
    bp_path='/Game/Systems/Interaction/Hiding/BP_HideBasket';bp=load(bp_path)
    backup('Content/Systems/Interaction/Hiding/BP_HideBasket.uasset')
    comps=templates(bp);comps['BasketBody'].set_static_mesh(MESH[1]['body']);comps['BasketBody'].set_editor_property('override_materials',[]);setup_cloth(comps['BasketCloth'],1)
    cdo=u.get_default_object(bp.generated_class());setup_actor(cdo,True)
    u.BlueprintEditorLibrary.compile_blueprint(bp);assert EA.save_loaded_asset(bp,False)
    REPORT['blueprint']=bp_path;persist()
    for name,stage in [('Stage1',1),('SoundTest_Stage1',1),('Stage2',2),('SoundTest_Stage2',2),('Tutorial',1),('SoundTest_Tutorial',1)]:
        rel=f'Content/Maps/{name}.umap';disk_before=backup(rel);assert LEVEL.load_level('/Game/Maps/'+name)
        allactors=list(ACT.get_all_level_actors());baskets=[a for a in allactors if isinstance(a,u.CatrunHideBasket)];owned=set(baskets)
        for a in baskets:
            body=a.get_editor_property('ExternalBody');cloth=a.get_editor_property('ExternalCloth')
            if body:owned.add(body)
            if cloth:owned.add(cloth.get_owner())
        nonowned_before={a.get_path_name():prop_actor(a) for a in allactors if a not in owned}
        row=REPORT['maps'][name]={'stage':stage,'hash_before':disk_before,'baskets':[]}
        cameras=[]
        for a in allactors:
            if 'QuarterViewCamera' in a.get_class().get_name():
                c=a.get_component_by_class(u.CameraComponent)
                if c:cameras.append({'actor':a.get_actor_label(),'rotation':rotation(c.get_world_rotation())})
        row['cameras']=cameras
        for a in baskets:
            before=prop_actor(a);local={c.get_name():c for c in a.get_components_by_class(u.SceneComponent)}
            ext_body=a.get_editor_property('ExternalBody');ext_cloth=a.get_editor_property('ExternalCloth')
            body=ext_body.get_component_by_class(u.StaticMeshComponent) if ext_body else local['BasketBody']
            cloth=ext_cloth or local['BasketCloth'];body_origin=body.get_world_location();body_rotation=body.get_world_rotation()
            setup_actor(a);body.set_static_mesh(MESH[stage]['body']);body.set_editor_property('override_materials',[])
            setup_cloth(cloth,stage)
            cloth.set_world_location_and_rotation(body_origin,body_rotation,False,False)
            if ext_body:
                local['BasketBody'].set_static_mesh(None);local['BasketBody'].set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            if ext_cloth:
                local['BasketCloth'].set_skeletal_mesh_asset(None);local['BasketCloth'].set_editor_property('animation_data',u.SingleAnimationPlayData());local['BasketCloth'].set_component_tick_enabled(False)
            assert prop_actor(a)==before,'Basket actor identity/placement changed'
            row['baskets'].append({'actor':a.get_actor_label(),'path':a.get_path_name(),'body':body.get_path_name(),'cloth':cloth.get_path_name(),'body_origin':xyz(body_origin),'body_rotation':rotation(body_rotation),'hidden':xyz(local['HiddenPoint'].get_world_location()),'body_mesh':body.static_mesh.get_path_name(),'cloth_mesh':cloth.skeletal_mesh_asset.get_path_name(),'edge_f':xyz(cloth.get_socket_location('Edge_F')-cloth.get_world_location()),'edge_r':xyz(cloth.get_socket_location('Edge_R')-cloth.get_world_location())})
        nonowned_after={a.get_path_name():prop_actor(a) for a in ACT.get_all_level_actors() if a not in owned}
        assert nonowned_before==nonowned_after,'Unrelated actor layout changed'
        assert sha(ROOT/rel)==disk_before,'Map changed externally during authoring; refuse stale save'
        assert LEVEL.save_current_level();row['hash_after']=sha(ROOT/rel);row['unrelated_actor_layout_preserved']=True;persist()
    REPORT['success']=True;persist();print('BASKET_APPLY_COMPLETE', {k:len(v['baskets']) for k,v in REPORT['maps'].items()})
except Exception:
    REPORT['success']=False;REPORT['error']=traceback.format_exc();persist();raise
