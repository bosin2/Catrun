import bpy,bmesh,sys,json
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE.parent));from retained_mesh_cleanup import cleanup
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check
a=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');m=bpy.data.objects['SK_BlackCat_Final'];body=bpy.data.objects['BlackCat_PortalBody']
a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
cleanup(m,a);bpy.context.view_layer.update()
clapper_slot=next(i for i,s in enumerate(m.material_slots) if s.name=='Bell_Clapper')
copies=[]
for only_clapper in (False,True):
 o=m.copy();o.data=m.data.copy();o.name='QA_BellClapper' if only_clapper else 'QA_FaceAndAttachments';bpy.context.scene.collection.objects.link(o)
 bm=bmesh.new();bm.from_mesh(o.data)
 remove=[f for f in bm.faces if (f.material_index==clapper_slot)!=only_clapper]
 bmesh.ops.delete(bm,geom=remove,context='FACES')
 loose=[v for v in bm.verts if not v.link_faces]
 bmesh.ops.delete(bm,geom=loose,context='VERTS');bm.to_mesh(o.data);bm.free();copies.append(o)
main=qa_check.run(objects=[copies[0].name,body.name],profile='game',eps=.0001,tol=.002)
clapper=qa_check.run(objects=[copies[1].name],profile='game',eps=.0001,tol=.002)
result={'pass':main['pass'] and clapper['pass'],'classification':'Bell_Clapper is an intentionally free internal bell part; inspected separately as required by asset-qa. Copies only; no scene or delivery mesh saved by this script.','main':main,'clapper':clapper,'accepted_warnings':['UVs intentionally stack flat-color material islands; no texture bake in this revision.','Ten back-to-back pairs belong to retained hidden eyelid caps. They are internal, separated from visible green eye shells, and preserved for existing blink rig.','Bell clapper lowest point need not rest on world ground; it moves with the bell.','Unused material slots only on temporary QA copies made by splitting the bell clapper.']}
(HERE/'classified_structural.json').write_text(json.dumps(result,indent=2))
print('CLASSIFIED_PASS',result['pass'],'main_errors',main['errors'],'clapper_errors',clapper['errors'])
