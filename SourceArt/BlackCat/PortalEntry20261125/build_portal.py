import bpy,math,json,sys,hashlib
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
O=Path(__file__).parent;sc=bpy.context.scene;sc.render.fps=30
a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH');bones=list(a.pose.bones)
rest={b.name:b.matrix_local.copy() for b in a.data.bones};length={b.name:b.length for b in a.data.bones}
def update():a.update_tag();bpy.context.view_layer.update()
def sample(action,f):
 a.animation_data.action=bpy.data.actions[action];sc.frame_set(int(f),subframe=f%1);update()
 return {p.name:p.matrix_basis.copy() for p in bones},{p.name:p.matrix.copy() for p in bones}
base,world=sample('AN_BlackCat_PortalJumpIn',1);jump12,jump12world=sample('AN_BlackCat_PortalJumpIn',12);air,airworld=sample('AN_BlackCat_PortalJumpIn',19)
def apply(pose):
 a.animation_data.action=None
 for p in bones:p.rotation_mode='QUATERNION';p.matrix_basis=pose[p.name]
 update()
def place(n,pos,rot):a.pose.bones[n].matrix=Matrix.Translation(Vector(pos))@rot.to_4x4();update()
def aim(n,pos,direction):
 q=rest[n].col[1].to_3d().normalized().rotation_difference(Vector(direction).normalized());place(n,pos,q.to_matrix()@rest[n].to_3x3())
def ease(x):x=max(0,min(1,x));return x*x*(3-2*x)
def ramp(f,start,end):return ease((f-start)/(end-start))
def curve(f,keys):
 if f<=keys[0][0]:return Vector(keys[0][1])
 for (f0,p0),(f1,p1) in zip(keys,keys[1:]):
  if f<=f1:return Vector(p0).lerp(Vector(p1),ease((f-f0)/(f1-f0)))
 return Vector(keys[-1][1])
def two_bone(n1,n2,S,T,pole):
 D=T-S;d=D.length;u=D.normalized();l1=length[n1];l2=length[n2]
 if d>l1+l2-1e-6:raise RuntimeError('unreachable '+n1+' '+str(d-l1-l2))
 h=(l1*l1-l2*l2+d*d)/(2*d);v=Vector(pole);v=(v-u*v.dot(u)).normalized();E=S+u*h+v*math.sqrt(max(0,l1*l1-h*h));aim(n1,S,E-S);aim(n2,E,T-E)
feet={n:world[n].translation.copy() for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']}
def legs(targets=None,compression=0):
 targets=targets or feet
 for side,sgn in [('L',1),('R',-1)]:
  n='upperarm_'+side;S=a.pose.bones[n].head.copy();T=targets['paw_F_'+side]
  # Let the scapula glide for the cautious reaching paw only.
  d=(T-S).length;limit=length[n]+length['forearm_'+side]-.0003
  if d>limit:
   shift=(T-S).normalized()*(d-limit);scap=a.pose.bones['scapula_'+side];mat=scap.matrix.copy();mat.translation+=shift;scap.matrix=mat;update();S=a.pose.bones[n].head.copy()
  two_bone(n,'forearm_'+side,S,T,(sgn*.13,1,0));place('paw_F_'+side,T,world['paw_F_'+side].to_3x3())
  P=targets['paw_H_'+side];H=a.pose.bones['thigh_'+side].head.copy()
  hock_vec=(world['paw_H_'+side].translation-world['hock_'+side].translation).normalized()
  hock_vec=(Matrix.Rotation(math.radians(-14)*compression,3,'X')@hock_vec).normalized();A=P-hock_vec*length['hock_'+side]
  two_bone('thigh_'+side,'shin_'+side,H,A,(sgn*.20,-1,0));aim('hock_'+side,A,P-A);place('paw_H_'+side,P,world['paw_H_'+side].to_3x3())
def head_ears(look=0,tilt=0,ear=0):
 p=a.pose.bones['head'];place('head',p.head.copy(),Matrix.Rotation(math.radians(tilt),3,'Y')@Matrix.Rotation(math.radians(look),3,'X')@p.matrix.to_3x3())
 for side,deg in [('L',-12),('R',3)]:
  p=a.pose.bones['ear_'+side];place(p.name,p.head.copy(),Matrix.Rotation(math.radians(deg)*ear,3,'Z')@p.matrix.to_3x3())
def clip1(f):
 apply(base);weight=ramp(f,1,7)*(1-ramp(f,20,29));pelvis=a.pose.bones['pelvis'];mat=pelvis.matrix.copy();mat.translation.x-=.0028*weight;pelvis.matrix=mat;update()
 chest=a.pose.bones['chest'];mat=chest.matrix.copy();mat.translation.x-=.0024*weight;chest.matrix=mat;update()
 targets={n:p.copy() for n,p in feet.items()};P=feet['paw_F_L'];targets['paw_F_L']=curve(f,[(1,P),(4,P),(9,P+Vector((0,-.012,.016))),(13,P+Vector((0,-.024,0))),(15,P+Vector((0,-.024,0))),(18,P+Vector((0,-.012,.012))),(23,P)])
 legs(targets);head_ears(look=9*ramp(f,1,8)*(1-ramp(f,15,23)),tilt=6*ramp(f,26,33),ear=ramp(f,23,29))
 if f==1:apply(base)
def clip2(f):
 apply(base);lower=ramp(f,1,10);compress=ramp(f,26,37)
 sway=0.
 if 10<f<26:
  u=(f-10)/16;sway=.0034*math.sin(4*math.pi*u)*ease(u/.10)*(1-ease((u-.90)/.10))
 mat=a.pose.bones['pelvis'].matrix.copy();mat.translation+=Vector((sway,.002*compress,-.003*lower-.015*compress));a.pose.bones['pelvis'].matrix=mat;update()
 # Shoulder lowering precedes the final pelvic compression; chest remains centered.
 mat=a.pose.bones['chest'].matrix.copy();mat.translation=world['chest'].translation+Vector((0,-.0015*lower,-.013*lower-.004*compress));a.pose.bones['chest'].matrix=mat;update()
 legs(compression=compress);head_ears(look=-3*lower,tilt=6*(1-ramp(f,1,9)),ear=1-ramp(f,1,10))
 if f==1:clip1(49)
def snapshot():return {p.name:p.matrix_basis.copy() for p in bones}
clip1(49);end1=snapshot();clip2(37);end2=snapshot();end2world={p.name:p.matrix.copy() for p in bones}
def bridge(f):
 # Nine-frame extension from the new anatomical crouch to existing airborne f19.
 t=(f-1)/9;s=ease(t);pose={n:end2[n].lerp(air[n],s) for n in end2};apply(pose)
 if f<10:
  # Keep the rear soles planted until the last push, extending each joint.
  targets={n:p.copy() for n,p in feet.items()}
  for side in ['L','R']:
   n='paw_F_'+side;targets[n]=feet[n].lerp(airworld[n].translation,ease(min(1,t*1.55)))+Vector((0,-.007*math.sin(math.pi*t),.010*math.sin(math.pi*t)))
   n='paw_H_'+side;u=max(0,min(1,(f-7)/3));targets[n]=feet[n].lerp(airworld[n].translation,ease(u))+Vector((0,0,.004*math.sin(math.pi*u)))
  legs(targets,compression=1-s)
 if f==1:apply(end2)
 if f==10:apply(air)
def fcurves(act):
 for layer in act.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    yield from bag.fcurves
def bake(name,end,fn):
 act=bpy.data.actions.new(name);act.use_fake_user=True;prev={};poses=[]
 for f in range(1,end+1):
  fn(f);poses.append({p.name:[list(r) for r in p.matrix] for p in bones});a.animation_data.action=act
  for p in bones:
   q=p.rotation_quaternion.copy()
   if p.name in prev and q.dot(prev[p.name])<0:q.negate();p.rotation_quaternion=q
   prev[p.name]=q.copy()
   for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
 for fc in fcurves(act):
  for key in fc.keyframe_points:key.interpolation='LINEAR'
 return act,poses
clips=[];samples={}
for name,end,fn in [('AN_BlackCat_PortalPawEar',49,clip1),('AN_BlackCat_PortalCrouchWiggle',37,clip2),('AN_BlackCat_PortalTakeoffBridge',10,bridge)]:
 act,poses=bake(name,end,fn);clips.append(act);samples[name]=poses
(O/'source_pose_samples.json').write_text(json.dumps(samples),encoding='utf8')
# Retain all original actions, and store only original asset objects in the .blend.
sc.frame_start=1;sc.frame_end=49;a.animation_data.action=clips[0];sc.frame_set(1);update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_PortalEntry_Actions.blend'))
# Animation-only FBX has no mesh BindPose. Write original rest transforms as
# Model defaults instead of the currently evaluated first animation pose.
from io_scene_fbx import export_fbx_bin,fbx_utils
original_writer=export_fbx_bin.fbx_data_object_elements
def rest_model_writer(root,ob,scene_data):
 original_tx=fbx_utils.ObjectWrapper.fbx_object_tx
 if ob.is_bone:
  def rest_tx(self,sd,rest=False,rot_euler_compat=None):return original_tx(self,sd,rest=True,rot_euler_compat=rot_euler_compat)
  fbx_utils.ObjectWrapper.fbx_object_tx=rest_tx
 try:return original_writer(root,ob,scene_data)
 finally:fbx_utils.ObjectWrapper.fbx_object_tx=original_tx
export_fbx_bin.fbx_data_object_elements=rest_model_writer
for act in clips:
 a.animation_data.action=act;sc.frame_start=1;sc.frame_end=int(act.frame_range[1]);sc.frame_set(1)
 bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a
 bpy.ops.export_scene.fbx(filepath=str(O/(act.name+'.fbx')),use_selection=True,object_types={'ARMATURE'},global_scale=1.,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',use_space_transform=True,bake_space_transform=False,add_leaf_bones=False,use_armature_deform_only=False,armature_nodetype='NULL',bake_anim=True,bake_anim_use_all_bones=True,bake_anim_use_nla_strips=False,bake_anim_use_all_actions=False,bake_anim_force_startend_keying=True,bake_anim_step=1.,bake_anim_simplify_factor=0.,path_mode='AUTO')
print('BUILT',[(c.name,list(c.frame_range)) for c in clips],flush=True)
