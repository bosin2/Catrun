"""Broad faceted skin on native helper bones; original 78 bind matrices untouched.

initialize(armature, original_mesh) at the neutral/rest pose, then update(armature,
frame=None) after posing the original bones. Supply frame to bake the helpers.
No handlers or custom runtime code are needed after baking.
"""
import bpy,bmesh,json,math
from mathutils import Vector,Matrix

_state={}
PREFIX='PSkin_'

def _frame(pos,tangent,xhint=Vector((1,0,0))):
 y=Vector(tangent).normalized();x=Vector(xhint)-y*Vector(xhint).dot(y)
 if x.length<1e-7:x=Vector((0,1,0))-y*y.y
 x.normalize();z=x.cross(y).normalized()
 return Matrix(((x.x,y.x,z.x,pos.x),(x.y,y.y,z.y,pos.y),(x.z,y.z,z.z,pos.z),(0,0,0,1)))

def _sample(points,count):
 # Two corner-cutting passes spread a joint bend over several broad sections.
 pts=[Vector(p) for p in points]
 for _ in range(2):
  out=[pts[0]]
  for a,b in zip(pts,pts[1:]):out.extend([a.lerp(b,.25),a.lerp(b,.75)])
  out.append(pts[-1]);pts=out
 lengths=[0.]
 for a,b in zip(pts,pts[1:]):lengths.append(lengths[-1]+(b-a).length)
 result=[]
 for j in range(count):
  s=lengths[-1]*j/(count-1);i=next((i for i in range(len(pts)-1) if lengths[i+1]>=s),len(pts)-2);t=(s-lengths[i])/max(1e-9,lengths[i+1]-lengths[i]);result.append(pts[i].lerp(pts[i+1],t))
 return result

def _get_state(a):
 if a.name not in _state:_state[a.name]=json.loads(a['portal_surface_state'])
 return _state[a.name]

def _matrices(a,state):
 rest={n:Matrix(v) for n,v in state['rest'].items()};out={}
 # Body follows actual torso landmarks. Cross-section planes follow the torso,
 # not the camera, with a consistently transported left/right axis.
 body=[]
 for n,offset,rx,rz in state['body']:
  p=a.pose.bones[n];D=p.matrix@rest[n].inverted();body.append(D@Vector(offset))
 for j,pos in enumerate(body):
  tangent=body[min(j+1,len(body)-1)]-body[max(j-1,0)]
  out[f'{PREFIX}Body_{j}']=_frame(pos,tangent)
 for key in ['F_L','F_R','H_L','H_R']:
  front=key.startswith('F');side=key[-1];upper=('upperarm_' if front else 'thigh_')+side;mid=('forearm_' if front else 'shin_')+side;paw=('paw_F_' if front else 'paw_H_')+side
  S=a.pose.bones[upper].head.copy();E=a.pose.bones[mid].head.copy();P=a.pose.bones[paw].head.copy();R=a.pose.bones[paw].matrix.to_3x3()@rest[paw].to_3x3().inverted();wrist=P+R@Vector((0,0,.006))
  torso='chest' if front else 'pelvis';td=a.pose.bones[torso].matrix@rest[torso].inverted();side_sign=1 if side=='L' else -1
  # Hide the root cap inside the torso. Starting at the anatomical shoulder
  # exposes a round end-cap whenever the arm is brought forward.
  anchor=rest[torso].translation+Vector((side_sign*.015,-.004 if front else -.002,-.004 if front else .010))
  start=td@anchor
  def ease(v):v=max(0.,min(1.,v));return v*v*(3-2*v)
  if front:
   angle=math.degrees((S-E).angle(P-E));fold=ease((65-angle)/40)
   # A tightly tucked front arm is covered by the chest. Do not force its
   # external skin into the complete internal elbow loop.
   controls=[start,S.lerp(start.lerp(wrist,.25),fold),E.lerp(start.lerp(wrist,.68),fold),wrist]
  else:
   A=a.pose.bones['hock_'+side].head.copy();angle=math.degrees((S-E).angle(A-E));fold=ease((95-angle)/50)
   outer=start.lerp(wrist,.45)+Vector((side_sign*.007,0,.003));K=E.lerp(outer,fold)
   controls=[start,S.lerp(start.lerp(K,.3),fold),K,A.lerp(K.lerp(wrist,.52),fold),wrist]
  # Skin is an outer envelope, not a visible diagram of every internal hinge.
  # Keep its centers ordered along the overall limb so a folded joint cannot
  # double back and turn the broad polygon sections inside out.
  axis=(wrist-start).normalized();span=(wrist-start).length
  for j in range(1,len(controls)-1):
   v=controls[j]-start;t=v.dot(axis)/max(span,1e-8);lo=(j-.55)/(len(controls)-1);hi=(j+.55)/(len(controls)-1);t=max(lo,min(hi,t));perp=v-axis*v.dot(axis);limit=span*.38*math.sin(math.pi*t)
   if perp.length>limit:perp=perp.normalized()*limit
   controls[j]=start+axis*(span*t)+perp
  centers=_sample(controls,6)
  base_paw=_frame(Vector(),Vector((0,0,-1)))
  if front:
   # Arrive at the wrist along its own normal. A centerline aimed at the
   # old elbow while the palm rotates makes the final two broad rings
   # collide, even though the paw itself remains rigid and correctly placed.
   terminal=(R@Vector((0,0,-1))).normalized()
   c1=start.lerp(controls[2],.65)
   c2=wrist-terminal*span*.40
   centers=_sample([start*(1-t)**3+c1*(3*(1-t)**2*t)+c2*(3*(1-t)*t*t)+wrist*t**3 for t in [i/40 for i in range(41)]],6)
   tangents=[(centers[min(j+1,5)]-centers[max(j-1,0)]).normalized() for j in range(6)]
   tangents[5]=terminal
   xs=[None]*6;xs[5]=(R@Vector((1,0,0))).normalized()
   for j in range(4,-1,-1):
    xs[j]=tangents[j+1].rotation_difference(tangents[j])@xs[j+1]
  for j,pos in enumerate(centers):
   if front:
    mat=_frame(pos,tangents[j],xs[j])
   elif j==5:
    mat=Matrix.Translation(pos)@R.to_4x4()@base_paw
   else:
    tangent=centers[min(j+1,5)]-centers[max(j-1,0)];mat=_frame(pos,tangent)
    if j==4:
     q=mat.to_quaternion().slerp((R.to_4x4()@base_paw).to_quaternion(),.45);mat=Matrix.Translation(pos)@q.to_matrix().to_4x4()
   out[f'{PREFIX}{key}_{j}']=mat
  out[f'{PREFIX}{key}_Paw']=Matrix.Translation(P)@R.to_4x4()
 return out

def initialize(a,m):
 """Return {body, helper_names, vertex_groups, triangles, paw_contract}."""
 if any(b.name.startswith(PREFIX) for b in a.data.bones):raise RuntimeError('Surface already initialized')
 bpy.context.view_layer.update();original={b.name:[list(r) for r in b.matrix_local] for b in a.data.bones}
 # Centers are stored in armature rest-space, transformed by their source bone.
 spec=[('pelvis',(0,.063,.079),.011,.014),('pelvis',(0,.036,.079),.035,.029),('lumbar',(0,.018,.085),.035,.026),('spine',(0,-.002,.085),.033,.025),('chest',(0,-.027,.085),.030,.025),('neck',(0,-.047,.108),.024,.023)]
 state={'rest':original,'body':spec,'mesh_name':'BlackCat_PortalBody','helper_names':[],'foot_vertices':{},'limb_vertices':{},'body_vertices':[]}
 matrices=_matrices(a,state)
 bpy.context.view_layer.objects.active=a
 if a.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 bpy.ops.object.mode_set(mode='EDIT')
 for name,mat in matrices.items():
  b=a.data.edit_bones.new(name);b.length=.004;b.matrix=mat;b.parent=a.data.edit_bones['root'];b.use_deform=True
 bpy.ops.object.mode_set(mode='OBJECT');state['helper_names']=list(matrices)
 # Retain the original head, eyes, ears, collar, bell and separate tail.
 fur={i for p in m.data.polygons if p.material_index==0 for i in p.vertices};remove=[]
 for v in m.data.vertices:
  tail=sum(g.weight for g in v.groups if m.vertex_groups[g.group].name.startswith('tail_'))
  face=v.co.z>.083 and v.co.y<-.047
  head_weight=sum(g.weight for g in v.groups if m.vertex_groups[g.group].name=='head' or m.vertex_groups[g.group].name.startswith(('ear_','Lid_')))
  if v.index in fur and v.co.z<.145 and tail<.5 and head_weight<.45 and not face:remove.append(v.index)
  elif v.index in fur and tail<.5 and .083<v.co.z<.145 and head_weight>.45:
   special=sum(g.weight for g in v.groups if m.vertex_groups[g.group].name.startswith(('ear_','Lid_')))
   if special<.01:
    # Preserve the angular head as one rigid shell instead of leaving tiny
    # neck-weighted wedges along the removed body boundary.
    for g in list(v.groups):m.vertex_groups[g.group].remove([v.index])
    m.vertex_groups['head'].add([v.index],1.,'REPLACE')
 bm=bmesh.new();bm.from_mesh(m.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in remove],context='VERTS')
 loose=[v for v in bm.verts if not v.link_faces]
 if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
 bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free()
 verts=[];faces=[];groups={n:[] for n in matrices}
 def vertex(co,n):
  i=len(verts);verts.append(tuple(co));groups[n].append(i);return i
 def ring(n,rx,rz,N,offset=0):
  mat=matrices[n];return [vertex(mat@Vector((rx*math.cos(math.tau*j/N+offset),0,rz*math.sin(math.tau*j/N+offset))),n) for j in range(N)]
 def bridge(A,B):
  for j in range(len(A)):
   k=(j+1)%len(A);faces.extend([(A[j],B[j],B[k]),(A[j],B[k],A[k])])
 def cap(row,n):
  c=vertex(sum((Vector(verts[i]) for i in row),Vector())/len(row),n)
  for j in range(len(row)):faces.append((row[j],row[(j+1)%len(row)],c))
 rows=[]
 for j,(_,_,rx,rz) in enumerate(spec):
  rows.append(ring(f'{PREFIX}Body_{j}',rx,rz,10));state['body_vertices'].extend(rows[-1])
 for A,B in zip(rows,rows[1:]):bridge(A,B)
 cap(rows[0],f'{PREFIX}Body_0');cap(rows[-1],f'{PREFIX}Body_5')
 for key in ['F_L','F_R','H_L','H_R']:
  first=len(verts);front=key.startswith('F');rows=[]
  radii=([.009,.013,.012,.011,.0105,.010] if front else [.011,.019,.017,.013,.0105,.010])
  for j,r in enumerate(radii):rows.append(ring(f'{PREFIX}{key}_{j}',r,r,8))
  for A,B in zip(rows,rows[1:]):bridge(A,B)
  cap(rows[0],f'{PREFIX}{key}_0')
  # A broad compact foot. Entire foot is rigid to its paw helper, including
  # the flat contact face. Local front is -Y and contact-face normal is -Z.
  n=f'{PREFIX}{key}_Paw';mat=matrices[n];sole=-.012 if front else -.011
  top=[];bottom=[]
  for z,rx,ry,row in [(-.004,.0125,.016,top),(sole,.012,.015,bottom)]:
   for j in range(8):
    t=math.tau*j/8;row.append(vertex(mat@Vector((rx*math.cos(t),-.003+ry*math.sin(t),z)),n))
  bridge(rows[-1],top);bridge(top,bottom);cap(bottom,n)
  state['foot_vertices'][key]=top+bottom;state['limb_vertices'][key]=list(range(first,len(verts)))
 mesh=bpy.data.meshes.new('BlackCat_PortalBodyMesh');mesh.from_pydata(verts,[],faces);mesh.update();body=bpy.data.objects.new(state['mesh_name'],mesh);bpy.context.scene.collection.objects.link(body);body.parent=a;mesh.materials.append(m.data.materials[0])
 for n,ids in groups.items():body.vertex_groups.new(name=n).add(ids,1.,'REPLACE')
 for key,ids in state['foot_vertices'].items():body.vertex_groups.new(name='QA_Foot_'+key).add(ids,1.,'REPLACE')
 for key,ids in state['limb_vertices'].items():body.vertex_groups.new(name='QA_Limb_'+key).add(ids,1.,'REPLACE')
 body.vertex_groups.new(name='QA_Body').add(state['body_vertices'],1.,'REPLACE')
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 for p in mesh.polygons:p.use_smooth=False
 uv=mesh.uv_layers.new(name='UVMap')
 for p in mesh.polygons:
  axis=max(range(3),key=lambda k:abs(p.normal[k]));axes=[k for k in range(3) if k!=axis]
  for li in p.loop_indices:
   co=mesh.vertices[mesh.loops[li].vertex_index].co;uv.data[li].uv=(co[axes[0]]*3+.5,co[axes[1]]*3+.5)
 mod=body.modifiers.new('Skin','ARMATURE');mod.object=a;mod.use_deform_preserve_volume=False
 a['portal_surface_state']=json.dumps(state);_state[a.name]=state
 if any(max(abs(a.data.bones[n].matrix_local[i][j]-rows[i][j]) for i in range(4) for j in range(4))>1e-7 for n,rows in original.items()):raise RuntimeError('Original bone bind changed')
 return {'body':body,'helper_names':list(matrices),'vertex_groups':state['foot_vertices'],'triangles':len(faces),'paw_contract':{'front_sole_local_z':-.012,'hind_sole_local_z':-.011,'sole_normal_local':[0,0,-1],'toe_min_local_y':-.019,'palm_contact_rotation':'relative to rest paw, rotate X=-90 degrees for a -Y-facing portal; front pawn head y=portal_y+0.012'}}

def update(a,frame=None):
 state=_get_state(a);bpy.context.view_layer.update();matrices=_matrices(a,state)
 for n,mat in matrices.items():
  p=a.pose.bones[n];p.rotation_mode='QUATERNION';p.matrix=mat
 bpy.context.view_layer.update()
 if frame is not None:
  for n in matrices:
   p=a.pose.bones[n]
   for channel in ['location','rotation_quaternion','scale']:p.keyframe_insert(channel,frame=frame,group=n)
 return matrices
