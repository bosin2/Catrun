import bpy,math
from pathlib import Path
m=bpy.data.objects['SK_BlackCat_RigV2'];a=bpy.data.objects['ARM_BlackCat_RigV2'];sc=bpy.context.scene;O=Path(__file__).resolve().parents[1]/'UniformJointRepair'
bpy.ops.object.select_all(action='DESELECT');m.select_set(True);bpy.context.view_layer.objects.active=m
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.01,area_weight=0.,correct_aspect=True,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
