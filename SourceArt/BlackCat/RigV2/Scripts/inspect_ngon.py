import bpy
m=bpy.data.objects['SK_BlackCat_RigV2']
for p in m.data.polygons:
 if len(p.vertices)>4:
  print('NGON',p.index,'normal',list(p.normal),'vertices',[(i,list(m.data.vertices[i].co),[(m.vertex_groups[g.group].name,g.weight) for g in m.data.vertices[i].groups]) for i in p.vertices])
