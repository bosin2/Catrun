import bpy,bmesh,sys,json
from pathlib import Path
from collections import Counter,defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).parent
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts')
import qa_check as Q
a=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update();m=bpy.data.objects['SK_BlackCat_Final'];bm=Q._mesh_world(m,True);isl=Q._islands(bm)
groups=defaultdict(list)
for i,g in enumerate(isl):groups[g].append(i)
data=[]
for g,ids in groups.items():
 vs=[bm.verts[i].co for i in ids];ws=Counter();materials=Counter()
 for i in ids:
  for e in m.data.vertices[i].groups:ws[m.vertex_groups[e.group].name]+=e.weight
 for f in bm.faces:
  if isl[f.verts[0].index]==g:materials[m.material_slots[f.material_index].name]+=len(f.verts)-2
 data.append({'island':g,'verts':len(ids),'bounds':[[min(v[k] for v in vs) for k in range(3)],[max(v[k] for v in vs) for k in range(3)]],'weights':ws.most_common(10),'materials':dict(materials)})
bmesh.ops.triangulate(bm,faces=bm.faces[:]);bm.faces.ensure_lookup_table();tris=[tuple(v.index for v in f.verts) for f in bm.faces];vco=[v.co.copy() for v in bm.verts];norms=[f.normal.copy() for f in bm.faces];bvh=BVHTree.FromPolygons(vco,tris,epsilon=0);sets=list(map(set,tris));pairs=set()
for ti,tri in enumerate(tris):
 av,b,c=[vco[i] for i in tri];n=norms[ti];cen=(av+b+c)/3
 for p in (cen,cen.lerp(av,.6),cen.lerp(b,.6),cen.lerp(c,.6)):
  for _,_,tj,_ in bvh.find_nearest_range(p,.0001):
   if tj is None or tj==ti or sets[ti]&sets[tj]:continue
   n2=norms[tj]
   if n.dot(n2)<.999:continue
   aa,bb,cc=[vco[i] for i in tris[tj]];q=p-n2*n2.dot(p-aa)
   if Q._point_in_tri(q,aa,bb,cc,n2):pairs.add(tuple(sorted((ti,tj))))
pairdata=[{'tris':[i,j],'islands':[isl[tris[i][0]],isl[tris[j][0]]],'materials':[m.material_slots[bm.faces[i].material_index].name,m.material_slots[bm.faces[j].material_index].name],'centers':[list(sum((vco[k] for k in tris[t]),Vector())/3) for t in [i,j]]} for i,j in pairs]
over=[{'vertex':v.index,'coord':list(v.co),'weights':[(m.vertex_groups[e.group].name,e.weight) for e in v.groups if e.weight>.0001]} for v in m.data.vertices if len([e for e in v.groups if e.weight>.0001])>4]
output_name='original_inspection.json' if Path(bpy.data.filepath).stem=='SK_BlackCat_PortalCinematic' else 'inspection.json'
(HERE/output_name).write_text(json.dumps({'file':bpy.data.filepath,'islands':data,'coplanar_pairs':pairdata,'overweight':over},indent=2))
print(json.dumps({'islands':data,'pair_islands':dict(Counter(str(tuple(p['islands'])) for p in pairdata)),'overweight_top':over[:4]},indent=2))
