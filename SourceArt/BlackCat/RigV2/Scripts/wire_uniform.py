import bpy,sys
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;bpy.context.scene.frame_set(1);a.update_tag();bpy.context.view_layer.update()
sys.path.insert(0,r'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import review_shots
print(review_shots.run(objects=['SK_BlackCat_RigV2','SK_BlackCat_BellClapper_V2'],out=str(O/'Previews/wire_review.png'),views=['front','right','three_quarter'],mode='wire',res=640))
