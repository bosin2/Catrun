"""Uniform low-poly topology over the entire shoulder-to-paw region."""
from pathlib import Path
source=Path(__file__).with_name('rebuild_leg_topology.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('bm=bmesh.new();')[0],str(__file__),'exec'))
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';O.mkdir(exist_ok=True);(O/'QA').mkdir(exist_ok=True);(O/'Previews').mkdir(exist_ok=True)
bm=bmesh.new();bm.from_mesh(m.data);dv=bm.verts.layers.deform.verify();uv=bm.loops.layers.uv.active;shapes=list(bm.verts.layers.shape.values());region=bm.faces.layers.int.new('V3_leg_region');ringid=bm.verts.layers.int.new('uniform_ring_id')
for v in bm.verts:v[ringid]=0
for f in bm.faces:f[region]=0
# Replace narrow shoulder chamfer ridges with one broad outer facet. Move only
# this small fur patch; keep all facial, collar and upper-back vertices intact.
for v in bm.verts:
 if not (.027<abs(v.co.x)<.049 and .050<v.co.z<.079) or not v.link_faces or any(f.material_index!=0 for f in v.link_faces):continue
 front=v.co.y<0;cy=-.036 if front else .038;sg=1 if front else -1
 if abs(v.co.y-cy)>.019:continue
 p0=Vector((.026,cy,.040));p1=Vector((.0348,cy-.006*sg,.070));p2=Vector((.04755,cy+.0156*sg,.076));normal=(p1-p0).cross(p2-p0)
 target=p0.x-(normal.y*(v.co.y-p0.y)+normal.z*(v.co.z-p0.z))/normal.x
 delta=Vector((math.copysign(target,v.co.x)-v.co.x,0,0));v.co+=delta
 for layer in shapes:v[layer]+=delta
# Clear old coplanar subdivisions before creating the joint boundary. Reducing a
# dense boundary alone creates long triangle fans in the retained shoulder.
edges=[e for e in bm.edges if len(e.link_faces)==2 and all(f.material_index==0 for f in e.link_faces) and all(.032<v.co.z<.085 for v in e.verts)]
bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(12),verts=[],edges=edges,use_dissolve_boundaries=False)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4])
def label(c):
 if c.z>=.059 or abs(c.x)<=.012:return None
 if c.y<-.014:return 'F_'+('L' if c.x>0 else 'R')
 if c.y>.014:return 'H_'+('L' if c.x>0 else 'R')
cut={f for f in bm.faces if f.material_index==0 and label(f.calc_center_median())}
borders={k:[] for k in ['F_L','F_R','H_L','H_R']}
for e in bm.edges:
 fs=[f for f in e.link_faces if f in cut]
 if len(fs)==1 and len(e.link_faces)==2:borders[label(fs[0].calc_center_median())].append(e)
def loop(es):
 adj={}
 for e in es:
  v,w=e.verts;adj.setdefault(v,[]).append(w);adj.setdefault(w,[]).append(v)
 assert all(len(v)==2 for v in adj.values())
 start=next(iter(adj));out=[start];prev=None;cur=start
 while True:
  nxt=next(n for n in adj[cur] if n!=prev)
  if nxt==start:break
  out.append(nxt);prev,cur=cur,nxt
 assert len(out)==len(adj);return out
boundaries={k:loop(v) for k,v in borders.items()};retained={v:tuple(v.co) for v in bm.verts if any(f not in cut for f in v.link_faces)}
bmesh.ops.delete(bm,geom=list(cut),context='FACES_ONLY');unused=[e for e in bm.edges if not e.link_faces]
if unused:bmesh.ops.delete(bm,geom=unused,context='EDGES')
unused=[v for v in bm.verts if not v.link_faces]
if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
gi={g.name:g.index for g in m.vertex_groups};leggroups={gi[n] for n in set(limb_bones)|{'support_'+n for n in limb_bones} if n in gi}
for v in bm.verts:
 w=v[dv];rem=sum(w.get(g,0) for g in leggroups)
 if rem:
  for g in list(w.keys()):
   if g in leggroups:del w[g]
  target=gi['chest' if v.co.y<0 else 'pelvis'];w[target]=w.get(target,0)+rem
def setweights(v,weights):
 for g in list(v[dv].keys()):del v[dv][g]
 for n,w in weights.items():v[dv][gi[n]]=w
def newvert(co,weights,code):
 v=bm.verts.new(co);v[ringid]=code
 for l in shapes:v[l]=co
 setweights(v,weights);return v
def face(vs,reg):
 f=bm.faces.new(vs);f[region]=reg;f.material_index=0;f.smooth=False
 for l in f.loops:l[uv].uv=(l.vert.co.x*8+.5,l.vert.co.y*6+l.vert.co.z*4+.5)
 return f
records={}
for reg,(key,B) in enumerate(boundaries.items(),1):
 side=key[-1];front=key[0]=='F';cx=.026*(1 if side=='L' else -1);cy=-.036 if front else .038;torso='chest' if front else 'pelvis'
 area=sum((B[i].co.x-cx)*(B[(i+1)%len(B)].co.y-cy)-(B[(i+1)%len(B)].co.x-cx)*(B[i].co.y-cy) for i in range(len(B)))
 if area<0:B=list(reversed(B))
 start=min(range(len(B)),key=lambda i:abs(math.atan2(B[i].co.y-cy,B[i].co.x-cx)+math.pi));B=B[start:]+B[:start]
 for v in B:setweights(v,{torso:1})
 lens=[math.hypot(B[(i+1)%len(B)].co.x-B[i].co.x,B[(i+1)%len(B)].co.y-B[i].co.y) for i in range(len(B))];total=sum(lens);fra=[0]
 for length in lens:fra.append(fra[-1]+length/total)
 N=8
 cyclic=lambda x,y:min(abs(x-y),1-abs(x-y))
 anchor_ids=[min(range(len(B)),key=lambda i:cyclic(fra[i],j/N)) for j in range(N)]
 assert len(set(anchor_ids))==N
 anchors=[B[i] for i in anchor_ids];root=[v.co.copy() for v in anchors]
 rootfra=[fra[i] for i in anchor_ids]+[1.]
 upper=('upperarm_' if front else 'thigh_')+side
 ws=[{torso:1},{upper:1},{('support_forearm_' if front else 'support_shin_')+side:1},{('forearm_' if front else 'support_hock_')+side:1},{('paw_F_' if front else 'paw_H_')+side:1},{('paw_F_' if front else 'paw_H_')+side:1}]
 rings=[]
 for k in range(6):
  row=[]
  for j,r in enumerate(root):
   theta=-math.pi+j*math.tau/N+(math.pi/8 if k in [1,3] else 0)
   if k==0:co=r-Vector((0,0,.006))
   else:
    # Broad, evenly sized facets: no dense ankle band or separate-looking boot.
    z=(r.z-.006)*(1-k/5)-.0009*(k/5)
    rx=[0,.012,.011,.010,.010,.0105][k];ry=[0,.012,.011,.010,.0115,.0122][k]
    ex=math.copysign(abs(math.cos(theta))**.75,math.cos(theta));ey=math.copysign(abs(math.sin(theta))**.75,math.sin(theta))
    co=Vector((cx+rx*ex,cy-(.002 if k>=4 else 0)+ry*ey,z))
   row.append(newvert(co,ws[k],reg*100+k+1))
  rings.append(row)
 nb=len(B)
 # Keep the torso boundary intact and bridge it across a real 6 mm transition.
 # Collapsing its vertices onto eight anchors can fold the adjacent body faces.
 i=j=0
 while i<nb or j<N:
  oldnext=fra[i+1] if i<nb else 2.;newnext=rootfra[j+1] if j<N else 2.
  if abs(oldnext-newnext)<1e-7:
   face([B[i%nb],B[(i+1)%nb],rings[0][(j+1)%N],rings[0][j%N]],reg);i+=1;j+=1
  elif oldnext<newnext:
   face([B[i%nb],B[(i+1)%nb],rings[0][j%N]],reg);i+=1
  else:
   face([B[i%nb],rings[0][(j+1)%N],rings[0][j%N]],reg);j+=1
 for k in range(5):
  for j in range(N):face([rings[k][j],rings[k][(j+1)%N],rings[k+1][(j+1)%N],rings[k+1][j]],reg)
 center=newvert(Vector((cx,cy-.002,-.0009)),ws[-1],reg*100+6)
 for j in range(N):face([rings[-1][j],rings[-1][(j+1)%N],center],reg)
 records[key]={'rings':6,'vertices_per_ring':8,'boundary_vertices':nb}
error=max((v.co-Vector(p)).length for v,p in retained.items() if v.is_valid)
# Remove legacy sub-millimeter chamfer strips on the shoulders. They become
# conspicuous wedges after reducing the boundary to broad limb facets.
def shoulder(v):return not v[ringid] and .032<v.co.z<.081 and v.link_faces and all(f.material_index==0 for f in v.link_faces)
for iteration in range(0):
 candidates=sorted([e for e in bm.edges if len(e.link_faces)==2 and e.calc_length()<.004 and all(shoulder(v) for v in e.verts)],key=lambda e:e.calc_length())
 chosen=None
 for e in candidates:
  v,w=e.verts
  nv={q.other_vert(v) for q in v.link_edges};nw={q.other_vert(w) for q in w.link_edges}
  opposite={x for f in e.link_faces if len(f.verts)==3 for x in f.verts if x not in [v,w]}
  if nv&nw==opposite:chosen=e;break
 if chosen is None:break
 v,w=chosen.verts;bmesh.ops.weld_verts(bm,targetmap={w:v})
eligible=[e for e in bm.edges if len(e.link_faces)==2 and all(f.material_index==0 and f[region]==0 for f in e.link_faces) and all(.032<v.co.z<.081 for v in e.verts)]
bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(2),verts=[],edges=eligible,use_dissolve_boundaries=False)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4 or f[region]>0]);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
if m.data.has_custom_normals:
 bpy.context.view_layer.objects.active=m
 with bpy.context.temp_override(object=m,active_object=m,selected_objects=[m],selected_editable_objects=[m]):bpy.ops.mesh.customdata_custom_splitnormals_clear()
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
a['uniform_topology_note']='Entire limbs rebuilt with 8 vertices per ring and 6 broad rings. No ankle-only dense patch.'
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
(O/'QA/rebuild.json').write_text(json.dumps({'retained_face_body_coordinate_error_m':error,'limbs':records,'vertices':len(m.data.vertices),'triangles':sum(len(p.vertices)-2 for p in m.data.polygons)},indent=2));print('UNIFORM_LIMBS_BUILT')
