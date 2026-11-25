import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent));from retained_mesh_cleanup import cleanup
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check
a=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');m=bpy.data.objects['SK_BlackCat_Final']
action=a.animation_data.action;a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update();result=cleanup(m,a);bpy.context.view_layer.update()
result['qa']=qa_check.run(objects=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render],profile='game',eps=.0001,tol=.002)
(HERE/'cleanup_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
