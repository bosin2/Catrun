import bpy,json,sys
from collections import Counter
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check
O=Path(__file__).resolve().parents[1]/'SitSleep';m=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.name!='BlackCat_SeatedBody');ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles();verts=[v.co.copy() for v in me.vertices];tris=[tuple(t.vertices) for t in me.loop_triangles];norm=[t.normal.copy() for t in me.loop_triangles];bvh=BVHTree.FromPolygons(verts,tris);pairs=set()
for i,t in enumerate(tris):
 a,b,c=[verts[j] for j in t];cen=(a+b+c)/3;n=norm[i]
 for p in [cen,cen.lerp(a,.6),cen.lerp(b,.6),cen.lerp(c,.6)]:
  for _,_,j,_ in bvh.find_nearest_range(p,.0001):
   if i==j or set(t)&set(tris[j]) or n.dot(norm[j])<.999:continue
   a2,b2,c2=[verts[k] for k in tris[j]];q=p-norm[j]*norm[j].dot(p-a2)
   if qa_check._point_in_tri(q,a2,b2,c2,norm[j]):pairs.add(tuple(sorted([i,j])))
def describe(i):
 t=me.loop_triangles[i];ids=list(t.vertices);g=Counter()
 for vi in ids:
  for w in m.data.vertices[vi].groups:g[m.vertex_groups[w.group].name]+=w.weight
 return {'tri':i,'mat':t.material_index,'center':list(sum((verts[j] for j in ids),Vector())/3),'weights':g.most_common(3)}
(O/'layer_overlap.json').write_text(json.dumps([[describe(i),describe(j)] for i,j in pairs],indent=2));print('PAIRS',len(pairs))
seen=set();components=[];adj=[[] for v in me.vertices]
for e in me.edges:adj[e.vertices[0]].append(e.vertices[1]);adj[e.vertices[1]].append(e.vertices[0])
for v in me.vertices:
 if v.index in seen:continue
 stack=[v.index];seen.add(v.index);ids=[]
 while stack:
  i=stack.pop();ids.append(i)
  for j in adj[i]:
   if j not in seen:seen.add(j);stack.append(j)
 if len(ids)==42:
  print('42_COMPONENT',json.dumps({'center':list(sum((verts[i] for i in ids),Vector())/len(ids)),'min':list(Vector((min(verts[i][k] for i in ids) for k in range(3)))),'max':list(Vector((max(verts[i][k] for i in ids) for k in range(3)))),'weights':[(m.vertex_groups[g.group].name,g.weight) for g in m.data.vertices[ids[0]].groups],'materials':list({p.material_index for p in me.polygons if p.vertices[0] in ids})}),flush=True)
