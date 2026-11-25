import unreal as u
import json,shutil
from pathlib import Path
root=Path(u.Paths.project_dir()).resolve(); out=root/'Saved/ElevatorTransition';out.mkdir(parents=True,exist_ok=True)
assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Unsaved map edits'
assert not u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),'Unsaved content edits'
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem); le=u.get_editor_subsystem(u.LevelEditorSubsystem); ac=u.get_editor_subsystem(u.EditorActorSubsystem)
original=ed.get_editor_world().get_outermost().get_name()
data={}
for mapname in ['Stage3','Stage2']:
    src=root/'Content/Maps'/f'{mapname}.umap';dst=out/'Backups'/src.name;dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists():shutil.copy2(src,dst)
    le.load_level('/Game/Maps/'+mapname)
    rows=[]
    for a in ac.get_all_level_actors():
        p=a.get_actor_location(); l=a.get_actor_label()
        near=(mapname=='Stage2' and p.y<200 and p.x>100 and p.x<1400) or (mapname=='Stage3' and p.y>-450)
        if near or any(s in l.lower() for s in ['flow','playerstart','followcamera']):
            center,extent=a.get_actor_bounds(False)
            m=a.get_component_by_class(u.StaticMeshComponent)
            rows.append({'label':l,'class':a.get_class().get_path_name(),'location':p.to_tuple(),'rotation':a.get_actor_rotation().to_tuple(),'scale':a.get_actor_scale3d().to_tuple(),'center':center.to_tuple(),'extent':extent.to_tuple(),'mesh':m.static_mesh.get_path_name() if m and m.static_mesh else None,'tags':[str(t) for t in a.tags]})
    data[mapname]=rows
    del a,rows
(out/'map_probes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print({k:len(v) for k,v in data.items()})
