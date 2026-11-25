"""Author a new arrival glance on the existing BlackCat skeleton.
Only the isolated derived AnimSequence is saved. The source clip/mesh/skeleton
and every other original asset remain untouched. Run in the root-owned editor.
"""
from pathlib import Path
import hashlib,json,math
import unreal as u

ROOT=Path(u.Paths.project_dir()).resolve()
BASE='/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalInspect'
MESH='/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final'
DEST='/Game/Cinematics/ElevatorTransition/Animations/AN_BlackCat_Elevator_ArrivalLookAround'
OWNER='ElevatorArrivalLookAround20261125'
FPS=30;DURATION=3.2;FRAMES=96;BASE_START=26/30
EA=u.EditorAssetLibrary

def normalize(q):
 n=math.sqrt(sum(v*v for v in q));assert n>.00001
 return tuple(v/n for v in q)
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return normalize((w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z))
def inv(q):return (-q[0],-q[1],-q[2],q[3])
def yaw(degrees):
 a=math.radians(degrees)/2;return (0,0,math.sin(a),math.cos(a))
def slerp(a,b,t):
 dot=sum(x*y for x,y in zip(a,b))
 if dot<0:b=tuple(-v for v in b);dot=-dot
 if dot>.9995:return normalize(tuple(x+(y-x)*t for x,y in zip(a,b)))
 theta=math.acos(min(1,dot));s=math.sin(theta)
 return normalize(tuple((math.sin((1-t)*theta)*x+math.sin(t*theta)*y)/s for x,y in zip(a,b)))
def qtuple(q):return normalize((q.x,q.y,q.z,q.w))
def vtuple(v):return (v.x,v.y,v.z)
def smooth(t):
 t=max(0,min(1,t));return t*t*t*(t*(t*6-15)+10)
def cue(t):
 # Readable glance holds, soft scan past center, and a neutral recovery.
 keys=[(0,0),(.25,0),(.80,24),(1.05,24),(1.95,-24),(2.25,-24),(3.00,0),(3.20,0)]
 for (a,x),(b,y) in zip(keys,keys[1:]):
  if t<=b:return x+(y-x)*smooth((t-a)/(b-a))
 return 0

def package_file(path):return ROOT/'Content'/(path.removeprefix('/Game/')+'.uasset')
mesh=EA.load_asset(MESH);source=EA.load_asset(BASE);skeleton=mesh.get_editor_property('skeleton')
assert source.get_editor_property('skeleton')==skeleton
original_paths=[package_file(BASE),package_file(MESH),package_file(skeleton.get_path_name().split('.')[0])]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in original_paths}
names=[str(n) for n in u.AnimationLibrary.get_animation_track_names(source)]
assert len(names)==78 and len(set(n.lower() for n in names))==78
lookup={n.lower():n for n in names}
neck,head=lookup['neck'],lookup['head'];paws=[lookup[n] for n in ('paw_f_l','paw_f_r','paw_h_l','paw_h_r')]
# A transient component exposes the installed mesh hierarchy, without a scene actor.
component=u.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(mesh)
parents={n:lookup.get(str(component.get_parent_bone(n)).lower()) for n in names}
assert parents[head]==neck,(head,parents[head])
options=u.AnimPoseEvaluationOptions()
for k,v in {'evaluation_type':u.AnimDataEvalType.SOURCE,'extract_root_motion':False,'incorporate_root_motion_into_pose':False,'should_retarget':False,'optional_skeletal_mesh':mesh}.items():options.set_editor_property(k,v)

def sample(clip,t):
 p=u.AnimPoseExtensions.get_anim_pose_at_time(clip,t,options)
 assert u.AnimPoseExtensions.is_valid(p)
 return p

def local_rows(pose):
 result={}
 for n in names:
  tr=u.AnimPoseExtensions.get_bone_pose(pose,n,u.AnimPoseSpaces.LOCAL)
  result[n]=(vtuple(tr.translation),qtuple(tr.rotation),vtuple(tr.scale3d))
 return result

def world_quats(rows):
 world={}
 def get(n):
  if n not in world:world[n]=mul(get(parents[n]),rows[n][1]) if parents[n] else rows[n][1]
  return world[n]
 for n in names:get(n)
 return world

start=local_rows(sample(source,BASE_START))
keys={n:{'p':[],'q':[],'s':[]} for n in names}
expected=[];base_quats=[]
for frame in range(FRAMES+1):
 t=frame/FPS
 # Keep the source's subtle tail/ear/blink movement. Close the final 0.45 s
 # back onto the first planted pose so the clip has an exact neutral endpoint.
 src_t=BASE_START+(source.get_play_length()-BASE_START)*t/DURATION
 rows=local_rows(sample(source,src_t));recover=smooth((t-2.75)/.45)
 for n in names:
  p,q,s=rows[n];P,Q,S=start[n]
  rows[n]=(tuple(a+(b-a)*recover for a,b in zip(p,P)),slerp(q,Q,recover),tuple(a+(b-a)*recover for a,b in zip(s,S)))
 original_world=world_quats(rows);base_quats.append(original_world)
 angle=cue(t);expected.append(angle)
 # Apply a world-Z yaw, using each actual parent's quaternion to map back
 # into that bone's local space. Neck carries 7/24 of the total turn.
 neck_parent=original_world[parents[neck]]
 p,q,s=rows[neck]
 rows[neck]=(p,mul(inv(neck_parent),mul(yaw(angle*7/24),original_world[neck])),s)
 turned_world=world_quats(rows)
 p,q,s=rows[head]
 rows[head]=(p,mul(inv(turned_world[parents[head]]),mul(yaw(angle),original_world[head])),s)
 for n,(p,q,s) in rows.items():
  assert all(math.isfinite(v) for v in p+q+s),(n,frame)
  keys[n]['p'].append(u.Vector(*p));keys[n]['q'].append(u.Quat(*q));keys[n]['s'].append(u.Vector(*s))

if EA.does_asset_exist(DEST):
 clip=EA.load_asset(DEST)
 assert EA.get_metadata_tag(clip,'Catrun_AuthoringOwner')==OWNER,'Refusing to overwrite an unrelated asset'
else:
 clip=EA.duplicate_asset(BASE,DEST)
 assert isinstance(clip,u.AnimSequence)
 EA.set_metadata_tag(clip,'Catrun_AuthoringOwner',OWNER)
assert clip.get_editor_property('skeleton')==skeleton
controller=clip.get_editor_property('controller')
controller.open_bracket('Author gentle arrival glances without changing the BlackCat rig')
try:
 controller.set_frame_rate(u.FrameRate(FPS,1))
 controller.set_number_of_frames(u.FrameNumber(FRAMES))
 for n in names:
  k=keys[n]
  assert controller.set_bone_track_keys(n,k['p'],k['q'],k['s']),n
finally:controller.close_bracket()
clip.set_editor_property('enable_root_motion',False)
clip.set_editor_property('force_root_lock',False)
clip.set_editor_property('rate_scale',1.0)
EA.set_metadata_tag(clip,'Catrun_DerivedSource',BASE+'; planted segment from 26/30 seconds')
EA.set_metadata_tag(clip,'Catrun_MotionContract','97 keys, 30 fps, 3.2 seconds, stationary paws/root, neck 7 and head 17 degree glances, original rig')
assert EA.save_loaded_asset(clip)
assert [str(n) for n in u.AnimationLibrary.get_animation_track_names(clip)]==names
assert u.AnimationLibrary.get_num_keys(clip)==FRAMES+1
assert abs(clip.get_play_length()-DURATION)<.001

checks={};first=sample(clip,0);last=sample(clip,DURATION)
paw_rest={n:vtuple(u.AnimPoseExtensions.get_bone_pose(first,n,u.AnimPoseSpaces.WORLD).translation) for n in paws}
max_paw=0;max_root=0;max_head_error=0;max_scale_error=0;max_endpoint=0
head_yaws=[]
for frame in range(FRAMES+1):
 pose=sample(clip,frame/FPS)
 for n in paws:
  p=vtuple(u.AnimPoseExtensions.get_bone_pose(pose,n,u.AnimPoseSpaces.WORLD).translation)
  max_paw=max(max_paw,math.dist(p,paw_rest[n])*2)
 root=u.AnimPoseExtensions.get_bone_pose(pose,lookup['root'],u.AnimPoseSpaces.LOCAL)
 max_root=max(max_root,root.translation.length())
 h=qtuple(u.AnimPoseExtensions.get_bone_pose(pose,head,u.AnimPoseSpaces.WORLD).rotation)
 delta=mul(h,inv(base_quats[frame][head]));measured=math.degrees(2*math.atan2(delta[2],delta[3]));measured=(measured+180)%360-180
 head_yaws.append(measured);max_head_error=max(max_head_error,abs(measured-expected[frame]))
 for n in names:
  tr=u.AnimPoseExtensions.get_bone_pose(pose,n,u.AnimPoseSpaces.LOCAL)
  max_scale_error=max(max_scale_error,math.dist(vtuple(tr.scale3d),vtuple(keys[n]['s'][frame])))
for n in names:
 a=u.AnimPoseExtensions.get_bone_pose(first,n,u.AnimPoseSpaces.LOCAL);b=u.AnimPoseExtensions.get_bone_pose(last,n,u.AnimPoseSpaces.LOCAL)
 max_endpoint=max(max_endpoint,math.dist(vtuple(a.translation),vtuple(b.translation)),math.dist(vtuple(a.scale3d),vtuple(b.scale3d)),1-abs(sum(x*y for x,y in zip(qtuple(a.rotation),qtuple(b.rotation)))))
assert max_paw<.01,('paw travel cm',max_paw)
assert max_root<.001,('root travel',max_root)
assert max_head_error<.05,('head world yaw error',max_head_error)
assert max_scale_error<.0001,('scale changed',max_scale_error)
assert max_endpoint<.0001,('endpoint mismatch',max_endpoint)
assert min(head_yaws)<-23.9 and max(head_yaws)>23.9
for p in original_paths:assert hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)],str(p)
report={'success':True,'asset':clip.get_path_name(),'source':source.get_path_name(),'skeleton':skeleton.get_path_name(),'duration':clip.get_play_length(),'keys':FRAMES+1,'bone_tracks':names,'hierarchy':{neck:parents[neck],head:parents[head]},'max_paw_travel_cm_at_mesh2':max_paw,'max_root_translation':max_root,'head_yaw_range_degrees':[min(head_yaws),max(head_yaws)],'max_expected_head_yaw_error_degrees':max_head_error,'max_scale_error':max_scale_error,'max_endpoint_error':max_endpoint,'original_sha256':before,'notes':['Source data verified; visual playback and compressed-data viewport check remain for root.','Derived animation only; original mesh, skeleton and source sequence unchanged.']}
out=ROOT/'Saved/ElevatorTransition/arrival_look_author_report.json';out.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
