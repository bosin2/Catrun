import bpy,bmesh,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';m=bpy.data.objects['SK_BlackCat_RigV2'];bm=bmesh.new();bm.from_mesh(m.data);dv=bm.verts.layers.deform.verify();rid=bm.verts.layers.int['uniform_ring_id'];reg=bm.faces.layers.int['V3_leg_region'];surf=bm.faces.layers.int['uniform_body_surface'];uv=bm.loops.layers.uv.active;shapes=list(bm.verts.layers.shape.values())
for code,key in enumerate(['F_L','F_R','H_L','H_R'],1):
 cx=.026*(1 if key[-1]=='L' else -1);cy=-.036 if key[0]=='F' else .038
 root=sorted([v for v in bm.verts if v[rid]==code*100+1],key=lambda v:math.atan2(v.co.y-cy,v.co.x-cx));low=sorted([v for v in bm.verts if v[rid]==code*100+2],key=lambda v:math.atan2(v.co.y-cy,v.co.x-cx))
 assert len(root)==len(low)==8
 shift=min(range(8),key=lambda k:sum((root[j].co-low[(j+k)%8].co).length_squared for j in range(8)));low=low[shift:]+low[:shift]
 old=[f for f in bm.faces if f[reg]==code and all(v[rid] in [code*100+1,code*100+2] for v in f.verts)];assert len(old)==16
 bmesh.ops.delete(bm,geom=old,context='FACES_ONLY');loose=[e for e in bm.edges if not e.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
 middle=[]
 for j in range(8):
  co=(root[j].co+low[j].co)*.5;co.x+=math.copysign(.0008,cx)
  v=bm.verts.new(co);v[rid]=code*100+7
  for layer in shapes:v[layer]=co
  weights={}
  for src in [root[j],low[j]]:
   for gi,w in src[dv].items():weights[gi]=weights.get(gi,0)+w*.5
  for gi,w in weights.items():v[dv][gi]=w
  middle.append(v)
 for A,B in [(root,middle),(middle,low)]:
  for j in range(8):
   f=bm.faces.new([A[j],A[(j+1)%8],B[(j+1)%8],B[j]]);f.material_index=0;f[reg]=code;f[surf]=1;f.smooth=False
   for l in f.loops:l[uv].uv=(l.vert.co.x*7+.5,l.vert.co.y*5+l.vert.co.z*3+.5)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3 and f[reg]>0]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
