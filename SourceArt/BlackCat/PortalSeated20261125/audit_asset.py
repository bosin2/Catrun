import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts')
import qa_check
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render]
a=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update()
result=qa_check.run(objects=[o.name for o in meshes],profile='game',eps=.0001,tol=.002)
(HERE/'QA'/'whole_asset_structural.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps({'objects':[{ 'name':o.name,'vertices':len(o.data.vertices),'tris':sum(len(p.vertices)-2 for p in o.data.polygons)} for o in meshes],'bones':len(a.data.bones),'errors':result['errors'],'warnings':result['warnings']},indent=2))
