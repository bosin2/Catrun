"""Restore the reference's 1.5m route around the lower lobby partition."""
import json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3LayoutCorrection20261125'
ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
actors={a.get_actor_label():a for a in ACT.get_all_level_actors()}
groups=json.loads((ROOT/'Saved/Stage3GothicRevision20261125/occlusion_report.json').read_text())['groups']
target=actors['S3_Wall_0101'];p,e=target.get_actor_bounds(False)
assert abs(p.x-625)<.1 and abs(p.y-500)<.1 and abs(e.x-75)<.1
members=groups['S3_Wall_0101']['members']
removed=[]
for label in members:
    assert label=='S3_Wall_0101' or label.startswith('S3_Gothic_Wall'),label
    if label in actors:assert ACT.destroy_actor(actors[label]);removed.append(label)
grid=actors['S3_SoundGrid'];grid.build_grid();assert grid.has_grid()
data=json.loads((OUT/'applied.json').read_text(encoding='utf8'))
def vec(p):return[p.x,p.y,p.z]
data['bounds']=[{'label':a.get_actor_label(),'min':vec(a.get_actor_bounds(False)[0]-a.get_actor_bounds(False)[1]),'max':vec(a.get_actor_bounds(False)[0]+a.get_actor_bounds(False)[1]),'tags':list(map(str,a.tags))} for a in ACT.get_all_level_actors() if isinstance(a,u.StaticMeshActor)]
data['lobby_partition_gap']={'x_min':550,'x_max':700,'removed':removed}
data['grid']=json.loads(grid.call_method('ExportBakedGridSnapshot'))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(OUT/'applied.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print('LOBBY_REFERENCE_GAP_SAVED',removed)
