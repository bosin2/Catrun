import bpy,bmesh,math
from pathlib import Path
from mathutils import Vector,Matrix
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';m=bpy.data.objects['SK_BlackCat_RigV2'];bm=bmesh.new();bm.from_mesh(m.data);rid=bm.verts.layers.int['uniform_ring_id'];reg=bm.faces.layers.int['V3_leg_region'];surf=bm.faces.layers.int['uniform_body_surface'];uv=bm.loops.layers.uv.active;shapes=list(bm.verts.layers.shape.values())
for code,key in enumerate(['F_L','F_R','H_L','H_R'],1):
 cx=.026*(1 if key[-1]=='L' else -1);cy=-.036 if key[0]=='F' else .038
 A=sorted([v for v in bm.verts if v[rid]==code*100+3],key=lambda v:math.atan2(v.co.y-cy,v.co.x-cx));B=sorted([v for v in bm.verts if v[rid]==code*100+5],key=lambda v:math.atan2(v.co.y-cy+.002,v.co.x-cx));assert len(A)==len(B)==8
 old=[f for f in bm.faces if f[reg]==code and any(v[rid]==code*100+4 for v in f.verts)];assert len(old)==32
 bmesh.ops.delete(bm,geom=old,context='FACES_ONLY');loose=[e for e in bm.edges if not e.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
 loose=[v for v in bm.verts if not v.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
 rot=Matrix.Rotation(math.pi/8,3,'Z');center=Vector((cx,cy,.027))
 for v in A:
  co=center+rot@(v.co-center);delta=co-v.co;v.co=co
  for layer in shapes:v[layer]+=delta
 for j in range(8):
  f=bm.faces.new([A[j],A[(j+1)%8],B[(j+1)%8],B[j]]);f.material_index=0;f[reg]=code;f[surf]=1;f.smooth=False
  for l in f.loops:l[uv].uv=(l.vert.co.x*7+.5,l.vert.co.y*5+l.vert.co.z*3+.5)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3 and f[reg]>0]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformDensity.blend'))
code=Path(__file__).with_name('review_uniform_motion.py').read_text(encoding='utf-8-sig').replace('report={}',"O=O/'UniformDensity';O.mkdir(exist_ok=True);(O/'QA').mkdir(exist_ok=True);report={}")
exec(compile(code,__file__,'exec'))
