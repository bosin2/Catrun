import bpy,json
from pathlib import Path
from mathutils import Vector
a=bpy.data.objects['ARM_BlackCat_RigV2'];sc=bpy.context.scene;O=Path(__file__).resolve().parents[1]/'UniformJointRepair'
a.animation_data.action=None;a['controls_enabled']=0.
for p in a.pose.bones:p.matrix_basis.identity()
a.update_tag();bpy.context.view_layer.update();col=bpy.data.collections['Mechanism - Surface Guides'];report={}
a['shoulder_clearance_gain']=.6
restgap=(a.matrix_world@a.pose.bones['CTRL_body'].matrix).translation.z-(a.matrix_world@a.pose.bones['CTRL_world'].matrix).translation.z
for key in ['F_L','F_R','H_L','H_R']:
 front=key[0]=='F';torso='chest' if front else 'pelvis';center=Vector((0,-.036 if front else .038,.074))
 sphere=bpy.data.objects.new('CLEARANCE_'+key,None);col.objects.link(sphere);sphere.location=center;sphere.hide_render=True;sphere.hide_set(True)
 c=sphere.constraints.new('CHILD_OF');c.target=a;c.subtarget=torso;c.inverse_matrix=(a.matrix_world@a.pose.bones[torso].matrix).inverted()
 report[key]=[]
 for k in [2,3]:
  p=bpy.data.objects[f'SMOOTH_3_{key}_{k:02d}'];distance=(p.matrix_world.translation-center).length
  c=p.constraints.new('LIMIT_DISTANCE');c.name='Keep upper limb outside torso';c.target=sphere;c.distance=distance;c.limit_mode='LIMITDIST_OUTSIDE';c.owner_space='WORLD'
  d=c.driver_add('distance').driver;d.type='SCRIPTED';d.expression=f'{distance}+g*max(0,{restgap}-(z-rz))'
  v=d.variables.new();v.name='g';v.type='SINGLE_PROP';v.targets[0].id=a;v.targets[0].data_path='["shoulder_clearance_gain"]'
  for vn,bone in [('z','CTRL_body'),('rz','CTRL_world')]:
   v=d.variables.new();v.name=vn;v.type='TRANSFORMS';v.targets[0].id=a;v.targets[0].bone_target=bone;v.targets[0].transform_type='LOC_Z';v.targets[0].transform_space='WORLD_SPACE'
  report[key].append({'row':k,'distance':distance})
a.update_tag();bpy.context.view_layer.update()
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
(O/'QA/shoulder_clearance.json').write_text(json.dumps(report,indent=2))
