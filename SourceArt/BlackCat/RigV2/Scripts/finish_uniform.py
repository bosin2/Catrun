import bpy,bmesh
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';m=bpy.data.objects['SK_BlackCat_RigV2'];a=bpy.data.objects['ARM_BlackCat_RigV2']
bm=bmesh.new();bm.from_mesh(m.data);uv=bm.loops.layers.uv.active
for f in list(bm.faces):
 if len(f.verts)<=4:continue
 vs=list(f.verts);uvs={l.vert:l[uv].uv.copy() for l in f.loops};mat=f.material_index
 def area_at(start):
  row=vs[start:]+vs[:start]
  return min((row[j].co-row[0].co).cross(row[j+1].co-row[0].co).length for j in range(1,len(row)-1))
 start=max(range(len(vs)),key=area_at);row=vs[start:]+vs[:start];bm.faces.remove(f)
 for j in range(1,len(row)-1):
  t=bm.faces.new([row[0],row[j],row[j+1]]);t.material_index=mat;t.smooth=False
  for l in t.loops:l[uv].uv=uvs[l.vert]
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
used={p.material_index for p in m.data.polygons}
for i in reversed(range(len(m.data.materials))):
 if i not in used:m.data.materials.pop(index=i)
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;bpy.context.scene.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
