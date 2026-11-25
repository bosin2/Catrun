"""V3: replace irregular leg surfaces by ordered rings; preserve the retained face/body."""
import bpy,bmesh,math,json,hashlib
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1]/'JointRepair';O.mkdir(exist_ok=True);(O/'QA').mkdir(exist_ok=True);(O/'Previews').mkdir(exist_ok=True)
a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
a.animation_data.action=None;a['controls_enabled']=0.
for p in a.pose.bones:p.matrix_basis.identity()
for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
a.pose.bones['CTRL_jaw']['open']=0.;a.pose.bones['CTRL_tongue']['extend']=0.;a.update_tag();bpy.context.view_layer.update()
# Old limb corrective morphs encode the defective topology and must not be reused.
remove_keys=[key.name for key in m.data.shape_keys.key_blocks if key.name.startswith('Corrective_') and 'neck' not in key.name]
for name in remove_keys:
 key=m.data.shape_keys.key_blocks[name];key.driver_remove('value');m.shape_key_remove(key)
old_rest={b.name:{'head':list(b.head_local),'tail':list(b.tail_local)} for b in a.data.bones}
bpy.context.view_layer.objects.active=a;bpy.ops.object.mode_set(mode='EDIT');eb=a.data.edit_bones
limb_bones={}
for side,sign in [('L',1),('R',-1)]:
 x=.026*sign
 specs={
 'upperarm_':((x,-.036,.065),(x,-.033,.025)),
 'forearm_':((x,-.033,.025),(x,-.038,.011)),
 'paw_F_':((x,-.038,.011),(x,-.047,.007)),
 'toes_F_':((x,-.047,.007),(x,-.051,.007)),
 'thigh_':((x,.036,.065),(x,.033,.027)),
 'shin_':((x,.033,.027),(x,.040,.019)),
 'hock_':((x,.040,.019),(x,.036,.011)),
 'paw_H_':((x,.036,.011),(x,.027,.007)),
 'toes_H_':((x,.027,.007),(x,.023,.007))}
 for stem,(head,tail) in specs.items():
  n=stem+side;b=eb[n];b.head=head;b.tail=tail;b.roll=0;b.use_connect=False;limb_bones[n]=stem
  ctl=eb.get('CTRL_'+n)
  if ctl:ctl.length=b.length;ctl.matrix=b.matrix.copy()
 for limb,paw in [('F','paw_F_'),('H','paw_H_')]:
  b=eb['CTRL_IK_'+limb+'_'+side];b.length=eb[paw+side].length;b.matrix=eb[paw+side].matrix.copy()
  c=eb['CTRL_pole_'+limb+'_'+side];pos=Vector((x,-.033+.09,.030)) if limb=='F' else Vector((x,.033-.09,.032));c.head=pos;c.tail=pos+Vector((0,0,.012))
 for child in ['forearm_','shin_','hock_','paw_F_','paw_H_']:
  n='support_'+child+side;b=eb.get(n) or eb.new(n);c=eb[child+side];b.length=c.length;b.matrix=c.matrix.copy();b.parent=c.parent;b.use_deform=True
bpy.ops.object.mode_set(mode='OBJECT')
for side in ['L','R']:
 for child in ['forearm_','shin_','hock_','paw_F_','paw_H_']:
  n='support_'+child+side
  if not m.vertex_groups.get(n):m.vertex_groups.new(name=n)
  p=a.pose.bones[n]
  if not p.constraints:
   c=p.constraints.new('COPY_ROTATION');c.name='Joint midpoint';c.target=a;c.subtarget=child+side;c.owner_space='LOCAL';c.target_space='LOCAL';c.influence=.5
  a.data.collections['Deform - Export'].assign(a.data.bones[n])

bm=bmesh.new();bm.from_mesh(m.data);bm.verts.ensure_lookup_table();dv=bm.verts.layers.deform.verify();uv=bm.loops.layers.uv.active;shape_layers=list(bm.verts.layers.shape.values());region=bm.faces.layers.int.new('V3_leg_region')
# A planar cut below the belly preserves the complete shoulder silhouette and gives
# four simple cross-sections; irregular high cuts can produce twisted connector fans.
cutgeom=set()
for f in bm.faces:
 if f.material_index==0 and any(v.co.z<.08 for v in f.verts):cutgeom.add(f);cutgeom.update(f.edges);cutgeom.update(f.verts)
bmesh.ops.bisect_plane(bm,geom=list(cutgeom),dist=1e-8,plane_co=(0,0,.031),plane_no=(0,0,1),clear_inner=False,clear_outer=False)
def limb(c):
 if c.z>=.031 or abs(c.x)<=.005:return None
 if c.y<0:return 'F_'+('L' if c.x>0 else 'R')
 if c.y>0:return 'H_'+('L' if c.x>0 else 'R')
cut={f for f in bm.faces if f.material_index==0 and max(v.co.z for v in f.verts)<.0310001 and min(v.co.z for v in f.verts)<.0309999 and limb(f.calc_center_median())}
borders={k:[] for k in ['F_L','F_R','H_L','H_R']}
for e in bm.edges:
 fs=[f for f in e.link_faces if f in cut]
 if len(fs)==1 and len(e.link_faces)==2:borders[limb(fs[0].calc_center_median())].append(e)
def ordered_loop(edges):
 adj={}
 for e in edges:
  v,w=e.verts;adj.setdefault(v,[]).append(w);adj.setdefault(w,[]).append(v)
 assert all(len(ns)==2 for ns in adj.values()),'Non-simple cut boundary '+str([(list(v.co),len(ns)) for v,ns in adj.items() if len(ns)!=2])
 first=next(iter(adj));out=[first];last=None;cur=first
 while True:
  nxt=next(n for n in adj[cur] if n!=last)
  if nxt==first:break
  out.append(nxt);last,cur=cur,nxt
 assert len(out)==len(adj),'Multiple boundary components'
 return out
loops={k:ordered_loop(es) for k,es in borders.items()}
kept_before={v:tuple(v.co) for v in bm.verts if any(f not in cut for f in v.link_faces)}
removed_faces=len(cut);bmesh.ops.delete(bm,geom=list(cut),context='FACES_ONLY')
orphan_edges=[e for e in bm.edges if not e.link_faces]
if orphan_edges:bmesh.ops.delete(bm,geom=orphan_edges,context='EDGES')
orphans=[v for v in bm.verts if not v.link_faces]
if orphans:bmesh.ops.delete(bm,geom=orphans,context='VERTS')
gidx={g.name:g.index for g in m.vertex_groups}
legnames=set(limb_bones)|{'support_'+n for n in limb_bones}
legidx={gidx[n] for n in legnames if n in gidx}
# Retained torso vertices cannot be pulled into the new limb by distant leg weights.
for v in bm.verts:
 w=v[dv];removed=sum(value for g,value in w.items() if g in legidx)
 if removed:
  for g in list(w.keys()):
   if g in legidx:del w[g]
  target=gidx['chest' if v.co.y<0 else 'pelvis'];w[target]=w.get(target,0)+removed
  blend=min(1,max(0,(.065-v.co.z)/.03))*min(1,removed/.55)
  if blend>0:
   upper=('upperarm_' if v.co.y<0 else 'thigh_')+('L' if v.co.x>0 else 'R')
   for g in list(w.keys()):w[g]*=1-blend
   w[gidx[upper]]=w.get(gidx[upper],0)+blend
def weights(v,values):
 for g in list(v[dv].keys()):del v[dv][g]
 for n,w in values.items():
  if w>1e-6:v[dv][gidx[n]]=w
def vert(co,ws):
 v=bm.verts.new(co)
 for layer in shape_layers:v[layer]=co
 weights(v,ws);return v
def face(vs,reg):
 f=bm.faces.new(vs);f.material_index=0;f.smooth=False;f[region]=reg
 for l in f.loops:l[uv].uv=(l.vert.co.x*9+.5,l.vert.co.y*7+l.vert.co.z*4+.5)
 return f
records={}
for ri,(key,boundary) in enumerate(loops.items(),1):
 limbtype,side=key.split('_');sign=1 if side=='L' else -1;cx=.026*sign;cy=-.036 if limbtype=='F' else .038;torso='chest' if limbtype=='F' else 'pelvis'
 # Keep the boundary's topology and order, then use a zipper connector to regular rings.
 angles=[math.atan2(v.co.y-cy,v.co.x-cx) for v in boundary]
 area=sum((boundary[i].co.x-cx)*(boundary[(i+1)%len(boundary)].co.y-cy)-(boundary[(i+1)%len(boundary)].co.x-cx)*(boundary[i].co.y-cy) for i in range(len(boundary)))
 if area<0:boundary=list(reversed(boundary))
 start=min(range(len(boundary)),key=lambda i:abs(math.atan2(boundary[i].co.y-cy,boundary[i].co.x-cx)+math.pi))
 boundary=boundary[start:]+boundary[:start]
 for v in boundary:weights(v,{('upperarm_' if limbtype=='F' else 'thigh_')+side:1.})
 if limbtype=='F':
  specs=[(.0305,.0100,.0117,{'upperarm_'+side:1}),(.028,.0098,.0115,{'upperarm_'+side:.75,'support_forearm_'+side:.25}),(.025,.0095,.0110,{'support_forearm_'+side:1}),(.022,.0095,.0110,{'support_forearm_'+side:.4,'forearm_'+side:.6}),(.019,.0095,.0110,{'forearm_'+side:1}),(.017,.0095,.0108,{'forearm_'+side:1}),(.013,.0098,.0110,{'forearm_'+side:.65,'support_paw_F_'+side:.35}),(.011,.0100,.0117,{'support_paw_F_'+side:1}),(.008,.0105,.0128,{'paw_F_'+side:1}),(.003,.0114,.0128,{'paw_F_'+side:1}),(-.0009,.0108,.0122,{'paw_F_'+side:1})]
 else:
  specs=[(.0305,.0100,.0117,{'thigh_'+side:1}),(.027,.0098,.0114,{'support_shin_'+side:1}),(.024,.0095,.0110,{'shin_'+side:1}),(.022,.0095,.0110,{'shin_'+side:.7,'support_hock_'+side:.3}),(.019,.0095,.0110,{'support_hock_'+side:1}),(.017,.0095,.0108,{'hock_'+side:1}),(.013,.0098,.0110,{'hock_'+side:.65,'support_paw_H_'+side:.35}),(.011,.0100,.0117,{'support_paw_H_'+side:1}),(.008,.0105,.0128,{'paw_H_'+side:1}),(.003,.0114,.0128,{'paw_H_'+side:1}),(-.0009,.0108,.0122,{'paw_H_'+side:1})]
 rings=[];N=12
 for z,rx,ry,ws in specs:
  row=[];yc=cy-(.002 if z<=.011 else 0)
  for j in range(N):
   theta=-math.pi+math.tau*j/N
   # Rounded square cross-section preserves the blocky paw, without a dense bevel mesh.
   ex=math.copysign(abs(math.cos(theta))**.65,math.cos(theta));ey=math.copysign(abs(math.sin(theta))**.65,math.sin(theta))
   row.append(vert(Vector((cx+rx*ex,yc+ry*ey,z)),ws))
  rings.append(row)
 # Connect unequal loops by perimeter fractions. Connector stays above the main joint.
 lengths=[(boundary[(i+1)%len(boundary)].co-boundary[i].co).length for i in range(len(boundary))];total=sum(lengths);fra=[0.]
 for length in lengths:fra.append(fra[-1]+length/total)
 i=j=0;B=len(boundary)
 while i<B or j<N:
  if i<B and (j==N or fra[i+1] <= (j+1)/N):face([boundary[i%B],boundary[(i+1)%B],rings[0][j%N]],ri);i+=1
  else:face([boundary[i%B],rings[0][(j+1)%N],rings[0][j%N]],ri);j+=1
 for k in range(len(rings)-1):
  for j in range(N):face([rings[k][j],rings[k][(j+1)%N],rings[k+1][(j+1)%N],rings[k+1][j]],ri)
 center=vert(Vector((cx,cy-.002,-.0009)),{('paw_F_' if limbtype=='F' else 'paw_H_')+side:1.})
 for j in range(N):face([rings[-1][j],rings[-1][(j+1)%N],center],ri)
 records[key]={'boundary_vertices':B,'ring_count':len(rings),'vertices_per_ring':N,'joint_weights':'adjacent segment or midpoint only'}
retained_error=max((v.co-Vector(c)).length for v,c in kept_before.items() if v.is_valid)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
# Remove inherited custom split normals; keep flat polygon shading throughout the repaired limbs.
if m.data.has_custom_normals:
 bpy.context.view_layer.objects.active=m
 with bpy.context.temp_override(object=m,active_object=m,selected_objects=[m],selected_editable_objects=[m]):bpy.ops.mesh.customdata_custom_splitnormals_clear()
a['joint_repair_version']=3;a['joint_repair_note']='Leg bind positions and weights revised. Original game assets untouched. Legacy clips require visual revalidation.'
# Restore an explicit neutral authoring pose, not a production animation with changed bind data.
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_JointRepair_V3.blend'))
r={'removed_faces':removed_faces,'retained_body_face_coordinate_error_m':retained_error,'legs':records,'triangles':sum(len(p.vertices)-2 for p in m.data.polygons),'vertices':len(m.data.vertices),'old_limb_bind':{n:old_rest[n] for n in limb_bones},'new_limb_bind':{n:{'head':list(a.data.bones[n].head_local),'tail':list(a.data.bones[n].tail_local)} for n in limb_bones}}
(O/'QA/rebuild.json').write_text(json.dumps(r,indent=2));print('JOINT_REBUILD_DONE',len(m.data.vertices),r['triangles'])
