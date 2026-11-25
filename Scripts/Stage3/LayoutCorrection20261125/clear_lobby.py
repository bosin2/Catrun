import json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
ACT=u.get_editor_subsystem(u.EditorActorSubsystem);lookup={a.get_actor_label():a for a in ACT.get_all_level_actors()}
removed=[]
for label in ('S3_Bench','S3_Maintenance'):
    a=lookup[label];assert 'CatrunStage3_20261125' in map(str,a.tags)
    removed.append({'label':label,'mesh':a.static_mesh_component.static_mesh.get_path_name(),'transform':a.get_actor_transform().export_text()});assert ACT.destroy_actor(a)
grid=lookup['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
ignored=[a for a in ACT.get_all_level_actors() if isinstance(a,(u.CatrunArmor,u.CatrunCandle))]
hit=u.SystemLibrary.capsule_trace_single_by_profile(world,u.Vector(625,420,26.2),u.Vector(625,740,26.2),20,26,'Pawn',False,ignored,u.DrawDebugTrace.NONE,True)
assert not hit,str(hit)
data=json.loads((OUT/'applied.json').read_text(encoding='utf8'))
data['removed_duplicate_lobby_furniture']=removed
def vec(p):return[p.x,p.y,p.z]
data['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
data['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(OUT/'applied.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print('LOBBY_REFERENCE_PASSAGE_CLEAR')
