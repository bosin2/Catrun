import bpy,math,json,sys
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
O=Path(__file__).resolve().parents[1];a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
POSES=['Body','PawReach','Face','Jump','Curl','Roll']
def update():a.update_tag();bpy.context.view_layer.update()
def reset():
 for p in a.pose.bones:p.matrix_basis.identity()
 a['controls_enabled']=1.
 for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
 for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
 a.pose.bones['CTRL_jaw']['open']=0.;a.pose.bones['CTRL_tongue']['extend']=0.
 for p in a.pose.bones:
  if p.name.startswith('CTRL_IK_'):p['ik']=1.
 update()
def move(n,offset):
 p=a.pose.bones[n];mat=p.matrix.copy();mat.translation+=Vector(offset);p.matrix=mat
def pose(kind,t):
 reset();u=math.sin(math.pi*t)**2;sp=a.pose.bones['CTRL_spine'];face=a.pose.bones['CTRL_face']
 if kind=='Body':
  move('CTRL_body',(0,0,-.012*u));sp['side_bend']=18*math.sin(math.tau*t)*u;sp['twist']=30*math.sin(math.tau*t)*u;sp['bend']=-12*u
 elif kind=='PawReach':move('CTRL_IK_F_L',(0,-.023*u,.025*u));face['look_z']=-.5*u
 elif kind=='Face':
  blink=max(0,1-abs(t-.22)/.075);wink=max(0,1-abs(t-.48)/.09);mouth=max(0,math.sin(math.pi*max(0,min(1,(t-.58)/.36))))
  face['blink_L']=max(blink,wink);face['blink_R']=blink;face['look_x']=.45*math.sin(math.tau*t)*u;face['look_z']=.2*math.sin(2*math.tau*t)*u
  a.pose.bones['CTRL_jaw']['open']=.65*mouth;a.pose.bones['CTRL_tongue']['extend']=.85*mouth
 elif kind=='Jump':
  z=.055*math.sin(math.pi*t)**4;move('CTRL_world',(0,0,z));move('CTRL_body',(0,0,-.010*math.sin(2*math.pi*t)**2))
  for side in ['L','R']:move('CTRL_IK_F_'+side,(0,-.008*u,.008*u));move('CTRL_IK_H_'+side,(0,.004*u,.005*u))
  sp['bend']=-10*u
 elif kind=='Curl':
  for p in a.pose.bones:
   if p.name.startswith('CTRL_IK_'):p['ik']=0.
  sp['bend']=-50*u;move('CTRL_body',(0,0,.015*u))
  for side in ['L','R']:
   a.pose.bones['CTRL_upperarm_'+side].rotation_quaternion=Quaternion((1,0,0),-.35*u)
   a.pose.bones['CTRL_forearm_'+side].rotation_quaternion=Quaternion((1,0,0),.75*u)
   a.pose.bones['CTRL_shin_'+side].rotation_quaternion=Quaternion((1,0,0),-.55*u)
  for j in range(1,8):a.pose.bones[f'CTRL_tail_{j:02d}'].rotation_quaternion=Quaternion((1,0,0),.16*u)
 elif kind=='Roll':
  # A deformation test: rotate the complete character about its trunk, not one spine joint.
  mat=a.data.bones['CTRL_world'].matrix_local.copy();pivot=Vector((0,0,.085));r=Matrix.Rotation(math.tau*t,4,'Y')
  a.pose.bones['CTRL_world'].matrix=Matrix.Translation(pivot)@r@Matrix.Translation(-pivot)@mat
  sp['bend']=-15*u
 update()
 if kind in ['Curl','Roll']:
  e=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();z=min(v.co.z for v in me.vertices);e.to_mesh_clear()
  move('CTRL_world',(0,0,-z-.0014));update()
def keyframe(f):
 a.keyframe_insert('["controls_enabled"]',frame=f)
 for p in a.pose.bones:
  if not p.name.startswith('CTRL_'):continue
  for channel in ['location','rotation_quaternion','rotation_euler']:p.keyframe_insert(channel,frame=f,group=p.name)
  for k in p.keys():
   if isinstance(p[k],(int,float)):p.keyframe_insert(f'["{k}"]',frame=f,group=p.name)

report={}
for kind in POSES:
 a.animation_data.action=None;reset();action=bpy.data.actions.new('V2_TEST_'+kind);action.use_fake_user=True;a.animation_data.action=action
 for f in range(1,92):sc.frame_set(f);pose(kind,(f-1)/90);keyframe(f)
 # Linear baked control channels avoid overshoot between frames.
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
 report[kind]={'frames':91,'seconds':3,'type':'rig capability test, not a production gameplay clip'}
a.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];a['controls_enabled']=0.;sc.frame_set(1);update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_RigV2.blend'))
# Render all frames at readable size for review; no state is saved after this point.
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO'
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=640;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
sc.display.shading.light='STUDIO';sc.display.shading.color_type='MATERIAL';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True;sc.display.shading.background_type='WORLD'
if not sc.world:sc.world=bpy.data.worlds.new('QA_World')
sc.world.color=(.18,.18,.18)
for kind in POSES:
 out=O/'Previews'/'Frames'/kind;out.mkdir(parents=True,exist_ok=True)
 a.animation_data.action=bpy.data.actions['V2_TEST_'+kind]
 target=Vector((0,-.057,.14) if kind=='Face' else (0,0,.105));cam.location=(0,-.6,.17) if kind=='Face' else (.4,-.5,.25);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.17 if kind=='Face' else .35
 finite=True;maxfeet=0.;mins=[];invalid=[]
 for f in range(1,92):
  sc.frame_set(f);update();e=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();coords=np.array([v.co[:] for v in me.vertices]);e.to_mesh_clear();finite &= bool(np.isfinite(coords).all());mins.append(float(coords[:,2].min()))
  if kind in ['Body','PawReach','Jump']:
   for paw in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']:maxfeet=max(maxfeet,(a.pose.bones[paw].head-a.pose.bones['CTRL_IK_'+paw[4:]].head).length)
  if any(min(p.scale)<=0 for p in a.pose.bones):invalid.append(f)
  sc.render.filepath=str(out/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
 report[kind].update(finite=finite,negative_scale_frames=invalid,min_ground_z=min(mins),max_ik_target_error_m=maxfeet)
 print('REVIEWED',kind,json.dumps(report[kind]),flush=True)
(O/'QA/motion_tests.json').write_text(json.dumps(report,indent=2))
