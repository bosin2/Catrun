"""Read-only same-skeleton arrival clip/stance inspection; no editor/map/asset edits."""
import json, math, statistics
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
mesh=u.load_asset('/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final')
sk=mesh.get_editor_property('skeleton')
paths=[
 '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_CautiousWalk',
 '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Walk',
 '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Idle',
 '/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalInspect',
 '/Game/Cinematics/ElevatorTransition/Animations/AN_BlackCat_Elevator_LoafStartleRise',
]
options=u.AnimPoseEvaluationOptions()
for name,value in {'evaluation_type':u.AnimDataEvalType.SOURCE,'extract_root_motion':False,'incorporate_root_motion_into_pose':False,'should_retarget':False,'optional_skeletal_mesh':mesh}.items():options.set_editor_property(name,value)
pa=['paw_f_l','paw_f_r','paw_h_l','paw_h_r'];bones=['root','pelvis','head']+pa
report={'mesh':mesh.get_path_name(),'skeleton':sk.get_path_name(),'mesh_scale_for_cm':2,'clips':[]}
all_samples={}
def vec(v):return list(v.to_tuple())
def qangle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
for path in paths:
 clip=u.load_asset(path)
 assert isinstance(clip,u.AnimSequence),path
 length=clip.get_editor_property('sequence_length');count=round(length*30)
 row={'path':clip.get_path_name(),'seconds':length,'same_skeleton':clip.get_editor_property('skeleton')==sk,'root_motion':clip.get_editor_property('enable_root_motion'),'samples':[]}
 samples=[]
 for f in range(count+1):
  pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,min(f/30,length),options)
  assert u.AnimPoseExtensions.is_valid(pose)
  state={'time':min(f/30,length)}
  for b in bones:
   t=u.AnimPoseExtensions.get_bone_pose(pose,b,u.AnimPoseSpaces.WORLD);q=t.rotation
   state[b]={'p':vec(t.translation),'q':[q.x,q.y,q.z,q.w]}
  samples.append(state)
 row['root_translation_span_cm']=[2*(max(s['root']['p'][j] for s in samples)-min(s['root']['p'][j] for s in samples)) for j in range(3)]
 row['head_total_angle_degrees']=max(qangle(samples[0]['head']['q'],s['head']['q']) for s in samples)
 for f in sorted(set([0,count]+[min(count,x) for x in [15,25,30,45,60,90,120]])):
  row['samples'].append(samples[f])
 if 'Walk' in path:
  stance=[abs(a[b]['p'][1]-c[b]['p'][1])*30*2 for a,c in zip(samples,samples[1:]) for b in pa if max(a[b]['p'][2],c[b]['p'][2])<1.42 and abs(a[b]['p'][1]-c[b]['p'][1])>.12]
  row['planted_paw_speed_cm_s_at_mesh_2']=statistics.median(stance) if stance else None
  row['planted_paw_samples']=len(stance)
 if 'PortalInspect' in path:
  after=samples[26:]
  row['after_0_867_seconds']={'head_angle_degrees':max(qangle(after[0]['head']['q'],s['head']['q']) for s in after),'max_paw_travel_cm':max(math.dist(after[0][b]['p'],s[b]['p'])*2 for b in pa for s in after)}
 report['clips'].append(row);all_samples[path]=samples
walk=all_samples[paths[0]];rise=all_samples[paths[-1]][-1];inspect=all_samples[paths[3]][26]
for label,target in [('rise_end',rise),('inspect_0_867',inspect)]:
 errors=[math.sqrt(sum(math.dist(s[b]['p'],target[b]['p'])**2 for b in ['pelvis','head']+pa)/6)*2 for s in walk]
 i=min(range(len(errors)),key=errors.__getitem__)
 report['cautious_walk_nearest_'+label]={'source_seconds':i/30,'bone_position_rms_cm':errors[i]}
out=ROOT/'Saved/ElevatorTransition/arrival_clip_probe.json';out.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({'report':str(out),'clips':[{k:v for k,v in r.items() if k!='samples'} for r in report['clips']]},ensure_ascii=False))
