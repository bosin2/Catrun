import bpy,json
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2']
for fc in list(a.animation_data.drivers):
 if fc.data_path.startswith('pose.bones["skin_') and fc.data_path.endswith('.scale'):a.animation_data.drivers.remove(fc)
for p in a.pose.bones:
 if p.name.startswith('skin_'):p.scale=(1,1,1)
if 'joint_fold_compression' in a:del a['joint_fold_compression']
a['shoulder_clearance_gain']=.6;a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;bpy.context.scene.frame_set(1);a.update_tag();bpy.context.view_layer.update()
a['review_status']='Uniform low-poly revision. Three diagnostic motions validated; arbitrary extreme FK angles are not guaranteed. No Unreal import.'
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
