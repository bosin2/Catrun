import bpy,bmesh
m=bpy.data.objects['SK_BlackCat_RigV2'];bm=bmesh.new();bm.from_mesh(m.data);bm.edges.index_update();bm.faces.index_update()
for e in bm.edges:
 if len(e.link_faces)>2 or len(e.link_faces)==0:
  print('BAD',e.index,[tuple(v.co) for v in e.verts],[(f.index,f.calc_area(),[tuple(v.co) for v in f.verts]) for f in e.link_faces])
