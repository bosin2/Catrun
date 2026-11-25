import bpy,json
from pathlib import Path
m=bpy.data.objects['SK_BlackCat_RigV2'];ring=m.data.attributes['uniform_ring_id']
for p in m.data.polygons:
 if p.material_index==0 and p.center.x>.01 and -.06<p.center.y<-.02 and .05<p.center.z<.075:
  print('FACE',p.index,'AREA',p.area,'VERTS',[(i,tuple(round(x,5) for x in m.data.vertices[i].co),ring.data[i].value) for i in p.vertices])
print('TINY',[(p.index,p.area,list(p.center)) for p in m.data.polygons if p.area<1e-10])
