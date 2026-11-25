import bpy,math,json,sys
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
report={'ik':{},'poses':{},'drivers':[]}
def update():a.update_tag();sc.frame_set(sc.frame_current);bpy.context.view_layer.update()
def reset():
 a.animation_data.action=None
 for p in a.pose.bones:p.matrix_basis.identity()
 for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
 for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
 a.pose.bones['CTRL_jaw']['open']=0.;a.pose.bones['CTRL_tongue']['extend']=0.
 a['controls_enabled']=1.;update()
def coords():
 e=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();ar=np.array([v.co[:] for v in me.vertices]);e.to_mesh_clear();return ar
reset()
# Calibrate each pole angle against the authored rest pose, not a guessed left/right convention.
for side in ['L','R']:
 for limb,end,chain in [('F','forearm_',['upperarm_','forearm_']),('H','hock_',['thigh_','shin_','hock_'])]:
  c=a.pose.bones[end+side].constraints['V2 planted '+limb]
  target=a.data.bones[('paw_F_' if limb=='F' else 'paw_H_')+side].head_local
  def err(angle):
   c.pole_angle=angle;update()
   return sum((a.pose.bones[n+side].head-a.data.bones[n+side].head_local).length_squared for n in chain)+(a.pose.bones[end+side].tail-target).length_squared
  angles=np.linspace(-math.pi,math.pi,73);best=min(angles,key=err)
  angles=np.linspace(best-.09,best+.09,61);best=min(angles,key=err);error=err(best)
  report['ik'][limb+'_'+side]={'pole_angle':float(best),'joint_position_error_m':math.sqrt(error),'target_error_m':(a.pose.bones[end+side].tail-target).length}
reset();rest=coords()
report['ik_neutral_dimensions']=(rest.max(0)-rest.min(0)).tolist()
# Save calibrated source before adding the review setup.
a['controls_enabled']=1.;a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO'
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
sc.display.shading.light='STUDIO';sc.display.shading.color_type='MATERIAL';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True
sc.display.shading.background_type='WORLD'
if not sc.world:sc.world=bpy.data.worlds.new('QA_World')
sc.world.color=(.18,.18,.18)
def shot(name,face=False,side=False):
 target=Vector((0,-.057,.14) if face else (0,0,.105));cam.location=(0,-.6,.17) if face else (.6,0,.17) if side else (.4,-.5,.25)
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.16 if face else .32
 sc.render.filepath=str(O/'Previews'/name);bpy.ops.render.render(write_still=True)
def metric(name):
 v=coords();report['poses'][name]={'finite':bool(np.isfinite(v).all()),'bounds_min':v.min(0).tolist(),'bounds_max':v.max(0).tolist(),'foot_target_errors':{p:(a.pose.bones[p].head-a.pose.bones['CTRL_IK_'+p[4:]].head).length for p in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']}}
reset();shot('after_neutral_threequarter.png');shot('after_neutral_face.png',True);metric('neutral')
for blink in [.25,.5,.75,1.]:
 reset();a.pose.bones['CTRL_face']['blink_L']=blink;a.pose.bones['CTRL_face']['blink_R']=blink;update();shot('after_blink_'+str(int(blink*100))+'.png',True);metric('blink_'+str(blink))
reset();a.pose.bones['CTRL_face']['blink_L']=1.;a.pose.bones['CTRL_face']['look_x']=.6;update();shot('after_wink_gaze.png',True)
reset();a.pose.bones['CTRL_jaw']['open']=.7;a.pose.bones['CTRL_tongue']['extend']=.8;update();shot('after_jaw_open.png',True);metric('jaw')
reset();body=a.pose.bones['CTRL_body'];worldmat=body.matrix.copy();worldmat.translation.z-=.020;body.matrix=worldmat;update();shot('after_crouch.png');metric('crouch')
reset();ctl=a.pose.bones['CTRL_IK_F_L'];mat=ctl.matrix.copy();mat.translation+=Vector((0,-.025,.035));ctl.matrix=mat;update();shot('after_paw_reach.png');metric('reach')
reset();a.pose.bones['CTRL_spine']['side_bend']=45.;a.pose.bones['CTRL_neck'].rotation_quaternion=Quaternion((0,1,0),math.radians(25));update();shot('after_side_bend.png');metric('side_bend')
reset();a.pose.bones['CTRL_spine']['twist']=60.;update();shot('after_twist60.png');metric('twist60')
reset();a.pose.bones['CTRL_spine']['bend']=45.;update();shot('after_arch.png',side=True);metric('arch')
for owner in [a,m.data.shape_keys]:
 if owner.animation_data:
  for fc in owner.animation_data.drivers:report['drivers'].append({'path':fc.data_path,'valid':fc.driver.is_valid})
(O/'QA/rig_review.json').write_text(json.dumps(report,indent=2))
print('RIG_REVIEW_DONE')
