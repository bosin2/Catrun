import bpy,math,json
from pathlib import Path
from mathutils import Vector,Quaternion
O=Path(__file__).resolve().parents[1]/'JointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];s=bpy.context.scene
a.animation_data.action=None;a['controls_enabled']=1.
for p in a.pose.bones:
 p.matrix_basis.identity()
 if p.name.startswith('CTRL_IK_'):p['ik']=0.
for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
cam=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.095;cam.location=(.25,-.25,.09);cam.rotation_euler=(Vector((.026,-.035,.026))-cam.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=900;s.render.resolution_y=900;s.render.resolution_percentage=100
s.display.shading.light='STUDIO';s.display.shading.color_type='SINGLE';s.display.shading.single_color=(.55,.58,.62);s.display.shading.show_cavity=True;s.display.shading.show_shadows=True
s.display.shading.background_type='WORLD'
if not s.world:s.world=bpy.data.worlds.new('QA_World')
s.world.color=(.15,.15,.15)
for stem,angle in [('forearm_L',0),('forearm_L',5),('forearm_L',60),('paw_F_L',45)]:
 for p in a.pose.bones:p.matrix_basis.identity()
 a.pose.bones['CTRL_'+stem].rotation_quaternion=Quaternion((1,0,0),math.radians(angle));a.update_tag();bpy.context.view_layer.update()
 s.render.filepath=str(O/'Previews'/f'gray_{stem}_{angle}.png');bpy.ops.render.render(write_still=True)
print('GRAY_CASES_DONE')
