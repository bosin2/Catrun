"""Isolated, reproducible animation authoring. No source file is saved."""
import bpy, math, json, hashlib, pathlib, sys
from mathutils import Vector, Quaternion, Matrix
OUT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=pathlib.Path(r'C:/Users/whghk/Desktop/CastleKit/BlackCat/Final/SK_BlackCat_Final.blend')
ELEV=pathlib.Path(r'C:/Users/whghk/Desktop/CastleKit/Stage2To3_Elevator/Production01_20261125/Assemblies/ASM_E23_Elevator.blend')
sc=bpy.context.scene; sc.render.fps=30
arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final'];pb=arm.pose.bones
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def curves(a):
 return [f for l in a.layers for s in l.strips for bag in s.channelbags for f in bag.fcurves]
def signature():
 d={'verts':[list(v.co) for v in mesh.data.vertices], 'faces':[list(p.vertices) for p in mesh.data.polygons], 'edges':[list(e.vertices) for e in mesh.data.edges],
 'uv':[[list(x.uv) for x in l.data] for l in mesh.data.uv_layers], 'weights':[[[g.group,g.weight] for g in v.groups] for v in mesh.data.vertices],
 'groups':[g.name for g in mesh.vertex_groups], 'materials':[(m.name,list(m.diffuse_color),[(n.name,n.type,[(i.name,str(i.default_value)) for i in n.inputs if hasattr(i,'default_value')]) for n in m.node_tree.nodes]) for m in mesh.data.materials],
 'bones':[(b.name,b.parent.name if b.parent else None,[list(r) for r in b.matrix_local],b.use_deform,b.inherit_scale) for b in arm.data.bones],
 'objects':[(o.name,list(o.location),list(o.rotation_euler),list(o.scale)) for o in [arm,mesh]],
 'old_actions':{a.name:[(c.data_path,c.array_index,[(list(k.co),k.interpolation,list(k.handle_left),list(k.handle_right)) for k in c.keyframe_points]) for c in curves(a)] for a in bpy.data.actions if not a.name.startswith('AN_BlackCat_Elevator_')}}
 return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
before=signature();source_sha=sha(SOURCE);elevator_sha=sha(ELEV)
def capture():return {p.name:(p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()) for p in pb}
def apply(pose):
 for p in pb:
  p.rotation_mode='QUATERNION';p.location,p.rotation_quaternion,p.scale=pose[p.name]
def sample(a,f):
 arm.animation_data.action=bpy.data.actions['AN_BlackCat_'+a];sc.frame_set(int(f),subframe=f-int(f));return capture()
idle=sample('Idle',1);sleep=sample('Sleep',1)
walks=[sample('Walk',f) for f in range(1,242)]
sleeps=[sample('Sleep',f) for f in range(1,242)]
stands=[sample('StandUp',f) for f in range(1,92)]
arm.animation_data.action=None;apply(idle);bpy.context.view_layer.update()
feet={n:pb[n].head.copy() for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']}
footrot={n:pb[n].matrix.to_quaternion() for n in feet}
def s(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def mix(a,b,t):return {n:(a[n][0].lerp(b[n][0],t),a[n][1].slerp(b[n][1],t),a[n][2].lerp(b[n][2],t)) for n in a}
def rot(n,deg,axis=(1,0,0)):
 pb[n].rotation_quaternion=pb[n].rotation_quaternion@Quaternion(axis,math.radians(deg))
def move_world(n,delta):
 bpy.context.view_layer.update();m=pb[n].matrix.copy();m.translation+=Vector(delta);pb[n].matrix=m;bpy.context.view_layer.update()
def solve(chain,target,paw,rotation=None,spread=0):
 bpy.context.view_layer.update();pts=[pb[n].head.copy() for n in chain]+[pb[chain[-1]].tail.copy()]; anchor=pts[0].copy()
 lens=[arm.data.bones[n].length for n in chain];target=Vector(target)
 if spread:
  pts[1].x+=spread;pts[2].x+=spread*.7
 if (target-anchor).length>=sum(lens)*.9999:
  direction=(target-anchor).normalized();pts=[anchor.copy()]
  for le in lens:pts.append(pts[-1]+direction*le)
 else:
  for it in range(40):
   pts[-1]=target.copy()
   for i in reversed(range(len(lens))):pts[i]=pts[i+1]+(pts[i]-pts[i+1]).normalized()*lens[i]
   pts[0]=anchor.copy()
   for i,le in enumerate(lens):pts[i+1]=pts[i]+(pts[i+1]-pts[i]).normalized()*le
   if (pts[-1]-target).length<1e-8:break
 for i,n in enumerate(chain):
  p=pb[n];m=p.matrix.copy();q=m.to_quaternion();direction=(pts[i+1]-pts[i]).normalized();q=(q@Vector((0,1,0))).rotation_difference(direction)@q
  p.matrix=Matrix.LocRotScale(pts[i],q,Vector((1,1,1)));bpy.context.view_layer.update()
 p=pb[paw];p.matrix=Matrix.LocRotScale(pts[-1],rotation or footrot[paw],Vector((1,1,1)));bpy.context.view_layer.update()
 return (p.head-target).length
def solve_feet(targets,front_all=False,front_rotation=None):
 errs={}
 for side in ['L','R']:
  n='paw_F_'+side
  chain=(['scapula_'+side] if front_all else [])+['upperarm_'+side,'forearm_'+side]
  errs[n]=solve(chain,targets[n],n,front_rotation)
  n='paw_H_'+side;errs[n]=solve(['thigh_'+side,'shin_'+side,'hock_'+side],targets[n],n)
 return errs
def ground(crouch=0,look=0,sway=0,ear=0,tail=0,offset=(0,0,0)):
 apply(idle);pb['root'].location=offset;move_world('pelvis',(sway,0,-crouch));rot('neck',look*.45);rot('head',look*.55)
 rot('ear_L',ear,(0,0,1));rot('ear_R',-ear,(0,0,1))
 for i in range(1,8):rot('tail_%02d'%i,tail*math.sin(i*.45),(0,0,1))
 solve_feet({n:v+Vector(offset) for n,v in feet.items()})
 return capture()
prepare=ground(.018,-38,ear=-6,tail=3)
# Append elevator read-only source into a separate preview collection, uniformly half sized:
# source character stays native scale 1; preview game meters = native meters * 2.
preview=bpy.data.collections.new('QA_Elevator_reference_half_scale');sc.collection.children.link(preview)
with bpy.data.libraries.load(str(ELEV),link=False) as (a,b):b.objects=a.objects
holder=bpy.data.objects.new('QA_GAME_TO_NATIVE_0p5',None);preview.objects.link(holder);holder.scale=(.5,.5,.5)
for o in b.objects:
 if o:
  preview.objects.link(o)
  if o.parent is None:o.parent=holder
  if o.type in {'CAMERA','LIGHT'}:o.hide_render=True
bpy.context.view_layer.update();ring=bpy.data.objects['SM_E23_ControlRing'];pull=bpy.data.objects['ROOT_ControlPull'];pull_base=pull.location.copy()
# Actual lower-left/lower-right ring mesh surface near +/-7cm game, avoiding a shared center contact.
from mathutils.bvhtree import BVHTree
verts=[ring.matrix_world@v.co for v in ring.data.vertices];polys=[list(p.vertices) for p in ring.data.polygons];tree=BVHTree.FromPolygons(verts,polys)
contacts={}
for side,sign in [('L',1),('R',-1)]:
 hit=tree.find_nearest(Vector((sign*.035,-.13,.658)))
 contacts[side]=hit[0]
(OUT/'QA/grip_surface_targets.json').write_text(json.dumps({'native_m':{n:list(v) for n,v in contacts.items()},'game_cm':{n:list(v*200) for n,v in contacts.items()},'ring_source':str(ELEV)},indent=2))
def hang(drop=0,swing=0):
 apply(idle);pb['root'].location=(0,-.115,.445-drop);rot('pelvis',-66);rot('neck',-10);rot('head',-10)
 for side in ['L','R']:
  rot('thigh_'+side,-22);rot('shin_'+side,28);rot('hock_'+side,-8)
  # Face toward -Y, forelimbs reach above the head, paw surface curls over lower ring.
  target=contacts[side]-Vector((0,0,drop))
  paw='paw_F_'+side
  qr=Quaternion((1,0,0),math.radians(-100))@footrot[paw]
  # Pad contact is a point 5mm below the native ankle in the standing pose.
  off=qr@Vector((0,.002,-.004))
  solve(['scapula_'+side,'upperarm_'+side,'forearm_'+side],target-off,paw,qr,.035 if side=='L' else -.035)
 for i in range(1,8):rot('tail_%02d'%i,6*math.sin(i*.5+swing),(0,0,1))
 bpy.context.view_layer.update();return capture()
hangtop=hang();hangbottom=hang(.09,(55-24)*.15)
def master_pose(f):
 if f<=7:
  t=(f-1)/6;return ground(.018*(1-t),-38+13*t,ear=-6*(1-t),tail=3-6*t)
 if f<=24:
  t=(f-7)/17;apply(mix(ground(0,-25),hangtop,s(t)))
  # Smooth deceleration into the grab; vertical displacement is authored on root only.
  pb['root'].location.z=.445*(2*t-t*t);pb['root'].location.y=-.115*s(t)
  return capture()
 if f<=29:return hang(0,(f-24)*.15)
 if f<=48:return hang(.09*s((f-29)/19),(f-24)*.15)
 if f<=55:return hang(.09,(f-24)*.15)
 if f<=73:
  t=(f-55)/18;apply(mix(hangbottom,ground(0,-5),s(t)))
  pb['root'].location.z=.355*(1-t*t);pb['root'].location.y=-.115*(1-s(t));return capture()
 if f<=78:return ground(.023*s((f-73)/5),8,ear=8,tail=5)
 return ground(.023*(1-s((f-78)/24)),8*(1-s((f-78)/24)),ear=8*(1-s((f-78)/24)),tail=5*(1-s((f-78)/24)))
def pull_amount(f):
 if f<=29:return 0
 if f<=48:return .18*s((f-29)/19)
 if f<=55:return .18
 return .18*(1-s((f-55)/18))
def bake(name,poses):
 a=bpy.data.actions.new('AN_BlackCat_Elevator_'+name);a.use_fake_user=True;arm.animation_data.action=a
 for f,pose in enumerate(poses,1):
  apply(pose)
  for p in pb:
   p.keyframe_insert('location',frame=f,group=p.name);p.keyframe_insert('rotation_quaternion',frame=f,group=p.name);p.keyframe_insert('scale',frame=f,group=p.name)
 for c in curves(a):
  for k in c.keyframe_points:k.interpolation='LINEAR'
 arm.animation_data.action=None;return a
# All motion is evaluated before creating new actions, preventing active curves from contaminating authoring.
master=[master_pose(f) for f in range(1,103)]
look=[ground(.018*s((f-28)/15),-38*s((f-5)/23),ear=-6*s((f-1)/10),tail=3*s((f-12)/31)) for f in range(1,44)]
look[-1]=prepare
startle=[]
for f in range(1,62):
 a=s((f-8)/3)*(1-s((f-17)/32));p=ground(.009*a,-10*a,.003*math.sin((f-8)*.5)*a,ear=18*a,tail=12*a)
 apply(p)
 # Existing seven tail deform bones only; no new morphs or changes to bind data.
 # Uniform radial ratio is distributed over the chain to avoid exponential thickening.
 puff=1+.55*a
 bpy.context.view_layer.update()
 tail_mats={i:pb['tail_%02d'%i].matrix.copy() for i in range(1,8)}
 for i in range(1,8):
  p=pb['tail_%02d'%i];p.matrix=tail_mats[i]@Matrix.Diagonal((puff,1,puff,1));bpy.context.view_layer.update()
  # Decomposition under a scaled parent introduces shear. Correct the longitudinal
  # component after decomposition, without changing bind matrices or inherit mode.
  desired_length=(tail_mats[i].to_3x3()@Vector((0,p.bone.length,0))).length
  p.scale.y*=desired_length/(p.tail-p.head).length;bpy.context.view_layer.update()
 startle.append(capture())
balance=[ground(.002*(1-math.cos(2*math.pi*(f-1)/90)),0,.0025*math.sin(2*math.pi*(f-1)/90),ear=3*math.sin(2*math.pi*(f-1)/90),tail=3*math.sin(2*math.pi*(f-1)/90)) for f in range(1,92)]
balance[-1]=balance[0]
# A short diagonal walking gait with explicit world-space stance targets.
# Six-frame swing phases, stationary support paws, no scaled limb lengths.
def approach():
 poses=[];stance={n:v.copy() for n,v in feet.items()};pairs=[['paw_F_L','paw_H_R'],['paw_F_R','paw_H_L']]
 for half in range(17):
  start=-.38*min(half,16)/16;end=-.38*min(half+1,16)/16;moving=pairs[half%2]
  goals={n:feet[n]+Vector((0,end,0)) for n in moving}
  for k in range(6):
   t=(k+1)/6;offset=start+(end-start)*s(t)
   ground(.004,2,ear=2,tail=2*math.sin(half*.7),offset=(0,offset,0))
   tar={n:v.copy() for n,v in stance.items()}
   for n in moving:tar[n]=stance[n].lerp(goals[n],s(t))+Vector((0,0,.012*math.sin(math.pi*t)))
   solve_feet(tar);poses.append(capture())
  for n in moving:stance[n]=goals[n]
 return poses
approach_poses=approach();peek=[idle]+approach_poses
for f in range(1,71):
 t=s((f-9)/20)*(1-s((f-50)/20));peek.append(ground(.004+.006*t,44*t,ear=2+5*t,tail=2*t,offset=(0,-.38,0)))
peek+=list(reversed(approach_poses));peek.append(idle)
rise=[]
for f in range(1,83):
 if f<=37:apply(sleeps[f-1])
 elif f<=41:
  apply(sleep);a=s((f-37)/4)
  for n in pb.keys():
   if n.startswith('Lid_'):
    pb[n].location=sleep[n][0].lerp(idle[n][0],a);pb[n].rotation_quaternion=sleep[n][1].slerp(idle[n][1],a);pb[n].scale=sleep[n][2].lerp(idle[n][2],a)
  rot('ear_L',-12*a,(0,0,1));rot('ear_R',12*a,(0,0,1))
 elif f<=59:
  t=(f-41)/18;apply(stands[min(90,int(s(t)*90))])
  for n in pb.keys():
   if n.startswith('Lid_'):pb[n].location,pb[n].rotation_quaternion,pb[n].scale=idle[n]
 else:ground(.004*math.sin(math.pi*s((f-59)/23)),ear=3*(1-s((f-59)/23)),tail=3*(1-s((f-59)/23)))
 rise.append(capture())
rise[-1]=idle
clips=[('C01','LookPrepare',look,False),('C02','JumpGrab',master[:25],False),('C03','HangPull',master[24:55],False),('C04','ReleaseLand',master[54:],False),('C05','StartleTail',startle,False),('C06','PeekDown',peek,False),('C07','RideBalance',balance,True),('C08','LoafIdle',sleeps,True),('C09','LoafStartleRise',rise,False)]
actions={name:bake(name,poses) for _,name,poses,_ in clips};actions['MASTER_JumpPullLand']=bake('MASTER_JumpPullLand',master)
assert signature()==before,'Original geometry, rig, objects or actions changed'
assert sha(SOURCE)==source_sha and sha(ELEV)==elevator_sha
(OUT/'QA/preservation.json').write_text(json.dumps({'source_sha256_before':source_sha,'source_sha256_after':sha(SOURCE),'elevator_sha256_before':elevator_sha,'elevator_sha256_after':sha(ELEV),'source_data_before':before,'source_data_after':signature(),'bones':len(pb),'original_actions':11,'new_actions':10,'geometry_changed':False},indent=2))
manifest={'fps':30,'native_to_game_scale':2,'coordinates':'Blender -Y forward +Z up. Preview elevator is uniformly half-scale; cat mesh and armature stay scale 1. Export native meters. root bone translation already contains trajectory. Do not add a second Actor jump.','clips':[{'id':i,'action':a.name,'frames':[1,len(p)],'seconds':(len(p)-1)/30,'loop':loop,'fbx':'FBX/'+a.name+'.fbx'} for i,n,p,loop in clips for a in [actions[n]]], 'master':{'action':actions['MASTER_JumpPullLand'].name,'frames':[1,102],'splits':{'C02':[1,25],'C03':[25,55],'C04':[55,102]}},'events_master':{'takeoff':7,'both_front_paws_grab':24,'pull_start':29,'pull_full':48,'release':55,'landing':73,'settled':102},'events':{'C05':{'cabin_start_impact':9,'tail_peak':12},'C06':{'edge_arrival':103,'look_down':133,'retreat':174},'C09':{'loaf_read':[1,37],'lock_impact':38,'eyes_open':41,'rise':42,'standing':59}},'tail':'Existing seven tail bones use radial scaling to 1.55, preserving bone centerline. No morph or new bones. Smooth thicker silhouette, no fur geometry.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
# Keep master and its moving reference in the saved production scene.
arm.animation_data.action=actions['MASTER_JumpPullLand']
for f in range(1,103):
 pull.location=pull_base-Vector((0,0,pull_amount(f)));pull.keyframe_insert('location',frame=f)
for a in bpy.data.actions:
 if a.name.startswith('ROOT_ControlPull'):
  for c in curves(a):
   for k in c.keyframe_points:k.interpolation='LINEAR'
sc.frame_start=1;sc.frame_end=102;sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SK_BlackCat_Elevator.blend'))
print('AUTHORED',len(clips),'clips plus master')
