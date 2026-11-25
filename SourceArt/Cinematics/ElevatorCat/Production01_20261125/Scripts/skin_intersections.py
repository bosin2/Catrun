"""Screen skin surface intersections; never silently change the original topology."""
import bpy,json,pathlib
from mathutils.bvhtree import BVHTree
OUT=pathlib.Path(__file__).resolve().parents[1];arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final'];sc=bpy.context.scene
mesh.data.calc_loop_triangles();triangles=[list(t.vertices) for t in mesh.data.loop_triangles];sets=[set(t) for t in triangles]
groups={g.index:g.name for g in mesh.vertex_groups}
def dominant(ids):
 scores={}
 for i in ids:
  for g in mesh.data.vertices[i].groups:scores[groups[g.group]]=scores.get(groups[g.group],0)+g.weight
 return max(scores,key=scores.get) if scores else 'none'
labels=[dominant(t) for t in triangles]
def measure(action,f):
 arm.animation_data.action=bpy.data.actions[action];sc.frame_set(f);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();vs=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
 tree=BVHTree.FromPolygons(vs,triangles,all_triangles=True);pairs=[];kinds={}
 for a,b in tree.overlap(tree):
  if a>=b or sets[a]&sets[b]:continue
  key=' / '.join(sorted([labels[a],labels[b]]));kinds[key]=kinds.get(key,0)+1
 return {'action':action,'frame':f,'nonadjacent_intersecting_triangle_pairs':sum(kinds.values()),'regions':kinds}
rows=[]
for a,fs in [('AN_BlackCat_Idle',[1]),('AN_BlackCat_Sleep',[1]),('AN_BlackCat_Elevator_MASTER_JumpPullLand',[1,13,24,48,62,78]),('AN_BlackCat_Elevator_StartleTail',[12]),('AN_BlackCat_Elevator_PeekDown',[49,133]),('AN_BlackCat_Elevator_LoafStartleRise',[38,39,48])]:
 for f in fs:rows.append(measure(a,f))
(OUT/'QA/skin_intersections.json').write_text(json.dumps({'method':'Nonadjacent triangle surface overlaps. Includes intended eye/lid/internal features; region labels are dominant bone heuristic. Sampled poses only. Existing topology was not repaired under preservation contract.','samples':rows},indent=2));print('SKIN_SCREEN',[(r['action'],r['frame'],r['nonadjacent_intersecting_triangle_pairs']) for r in rows])
