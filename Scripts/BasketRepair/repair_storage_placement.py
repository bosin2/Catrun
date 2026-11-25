"""Move only the first Stage1 basket group 50cm away from the room entrance."""
import unreal as u,json,shutil,hashlib
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();OUT=ROOT/'Saved/BasketRepair20261125';OUT.mkdir(parents=True,exist_ok=True)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
def xyz(v):return [v.x,v.y,v.z]
def pose(a):
 r=a.get_actor_rotation();return [xyz(a.get_actor_location()),[r.pitch,r.yaw,r.roll],xyz(a.get_actor_scale3d())]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report={}
for name in ['Stage1','SoundTest_Stage1']:
 disk=ROOT/'Content/Maps'/(name+'.umap');backup=OUT/'Before'/(name+'.umap');backup.parent.mkdir(parents=True,exist_ok=True)
 if not backup.exists():shutil.copy2(disk,backup)
 before_hash=sha(disk);assert LEVEL.load_level('/Game/Maps/'+name)
 actors=list(ACT.get_all_level_actors());b=next(a for a in actors if a.get_actor_label()=='BP_S1_storage_HideBasket_26_Interaction')
 members=[b,b.get_editor_property('ExternalBody'),b.get_editor_property('ExternalCloth').get_owner()]
 other={a.get_path_name():pose(a) for a in actors if a not in members}
 old=b.get_actor_location();assert abs(old.y-1750)<.01 and min(abs(old.x-710),abs(old.x-760))<.01
 delta=u.Vector(760-old.x,0,0);rows=[]
 for a in members:
  start=a.get_actor_location();a.modify();a.set_actor_location(start+delta,False,True)
  assert (a.get_actor_location()-start-delta).length()<.01
  rows.append({'actor':a.get_actor_label(),'before':xyz(start),'after':xyz(a.get_actor_location())})
 assert other=={a.get_path_name():pose(a) for a in ACT.get_all_level_actors() if a not in members}
 assert sha(disk)==before_hash,'Map changed externally; refuse stale save'
 assert LEVEL.save_current_level()
 report[name]={'actors':rows,'unrelated_transforms_unchanged':True,'hash_after':sha(disk)}
(OUT/'placement_repair.json').write_text(json.dumps(report,indent=2),encoding='utf8')
