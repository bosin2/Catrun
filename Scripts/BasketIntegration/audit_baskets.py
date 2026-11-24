import unreal as u,json,hashlib
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/BasketIntegration20261125';OUT.mkdir(parents=True,exist_ok=True)
level=u.get_editor_subsystem(u.LevelEditorSubsystem);actors=u.get_editor_subsystem(u.EditorActorSubsystem)
def vec(v):return [v.x,v.y,v.z]
def ref(o):return o.get_path_name() if o else None
def props(o,names):
    r={}
    for n in names:
        try:
            v=o.get_editor_property(n);r[n]=ref(v) if isinstance(v,u.Object) else str(v)
        except Exception as e:r[n]='UNAVAILABLE '+str(e)[:120]
    return r
report={}
for name in ['Stage1','SoundTest_Stage1','Stage2','SoundTest_Stage2','Tutorial','SoundTest_Tutorial']:
    assert level.load_level('/Game/Maps/'+name)
    rows=[]
    for a in actors.get_all_level_actors():
        if not isinstance(a,u.CatrunHideBasket):continue
        row={'actor':a.get_actor_label(),'path':ref(a),'location':vec(a.get_actor_location()),'rotation':str(a.get_actor_rotation()),'scale':vec(a.get_actor_scale3d()),'properties':props(a,['ExternalBody','ExternalCloth','OpenDirectionLocal','ClothEnterAnimation','ClothExitAnimation','ClothIdleAnimation']),'components':[]}
        linked=[a]
        for key in ['ExternalBody','ExternalCloth']:
            ob=a.get_editor_property(key)
            if ob:
                owner=ob.get_owner() if isinstance(ob,u.ActorComponent) else ob
                if owner not in linked:linked.append(owner)
        for owner in linked:
            for c in owner.get_components_by_class(u.SceneComponent):
                row['components'].append({'owner':owner.get_actor_label(),'name':c.get_name(),'class':c.get_class().get_name(),'location':vec(c.get_world_location()),'rotation':str(c.get_world_rotation()),'scale':vec(c.get_world_scale()),'properties':props(c,['relative_location','relative_rotation','relative_scale3d','static_mesh','skeletal_mesh_asset','animation_data','collision_profile_name'])})
        rows.append(row)
    p=ROOT/'Content/Maps'/f'{name}.umap'
    report[name]={'hash':hashlib.sha256(p.read_bytes()).hexdigest(),'baskets':rows}
(OUT/'map_audit_before.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
print('BASKET_AUDIT', {k:len(v['baskets']) for k,v in report.items()})
