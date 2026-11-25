import bpy,sys,json
from pathlib import Path
O=Path(__file__).resolve().parents[1]
sys.path.insert(0,r'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts')
import qa_check
a=next(o for o in bpy.data.objects if o.type=='ARMATURE');meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.vertex_groups]
a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
if 'controls_enabled' in a:a['controls_enabled']=0.;a.update_tag()
bpy.context.view_layer.update()
r={m.name:qa_check.run(objects=[m.name],profile='game',eps=.00003,tol=.0005) for m in meshes}
(O/'QA'/'asset_qa_v2.json').write_text(json.dumps(r,indent=2))
print(json.dumps({n:{'pass':v['pass'],'errors':v['errors'],'warnings':v['warnings']} for n,v in r.items()}))
