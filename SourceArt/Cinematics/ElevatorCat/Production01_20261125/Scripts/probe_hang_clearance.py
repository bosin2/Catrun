import ast,bpy,pathlib,json
from mathutils import Vector,Quaternion,Matrix
from mathutils.bvhtree import BVHTree
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];pb=arm.pose.bones;mesh=bpy.data.objects['SK_BlackCat_Final'];ring=bpy.data.objects['SM_E23_ControlRing']
tree=ast.parse((OUT/'Scripts/author.py').read_text());exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='solve'],type_ignores=[]),'solve','exec'))
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];sc.frame_set(24)
base={p.name:p.matrix_basis.copy() for p in pb};targets={s:pb['paw_F_'+s].head.copy() for s in ['L','R']};footrot={n:pb[n].matrix.to_quaternion() for n in ['paw_F_L','paw_F_R']}
groups={g.index:g.name for g in mesh.vertex_groups};mesh.data.calc_loop_triangles();tri=[list(t.vertices) for t in mesh.data.loop_triangles]
def group(t):
 d={}
 for i in t:
  for g in mesh.data.vertices[i].groups:d[groups[g.group]]=d.get(groups[g.group],0)+g.weight
 return max(d,key=d.get)
labels=[group(t) for t in tri];cf=[t for t,l in zip(tri,labels) if l=='collar'];af=[t for t,l in zip(tri,labels) if l.startswith(('forearm','upperarm'))];hf=[t for t,l in zip(tri,labels) if l in ['head','neck','ear_L','ear_R','ear_tip_L','ear_tip_R']]
rt=BVHTree.FromPolygons([ring.matrix_world@v.co for v in ring.data.vertices],[list(p.vertices) for p in ring.data.polygons]);rows=[]
for dz in [0,.01,.02,.025]:
 for spread in [.035,.06,.09]:
  for p in pb:p.matrix_basis=base[p.name]
  pb['root'].location.z+=dz;bpy.context.view_layer.update()
  for side,sign in [('L',1),('R',-1)]:solve(['scapula_'+side,'upperarm_'+side,'forearm_'+side],targets[side],'paw_F_'+side,footrot['paw_F_'+side],sign*spread)
  ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();vs=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
  ct=BVHTree.FromPolygons(vs,cf);at=BVHTree.FromPolygons(vs,af);ht=BVHTree.FromPolygons(vs,hf)
  rows.append({'dz':dz,'spread':spread,'collar_arm':len(ct.overlap(at)),'head_ring':len(ht.overlap(rt)),'contact_error_cm':max((pb['paw_F_'+s].head-targets[s]).length for s in targets)*200})
(OUT/'QA/hang_clearance_trials.json').write_text(json.dumps(rows,indent=2));print('CLEARANCE_TRIALS',rows)
