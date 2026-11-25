"""Connected torso and limb quad flow; preserve the existing face and accessories."""
from pathlib import Path
source=Path(__file__).with_name('rebuild_leg_topology.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('bm=bmesh.new();')[0],str(__file__),'exec'))
O=Path(__file__).resolve().parents[1]/'UniformJointRepair'
bm=bmesh.new();bm.from_mesh(m.data);dv=bm.verts.layers.deform.verify();uv=bm.loops.layers.uv.active;shapes=list(bm.verts.layers.shape.values());region=bm.faces.layers.int.new('V3_leg_region');ringid=bm.verts.layers.int.new('uniform_ring_id');surface=bm.faces.layers.int.new('uniform_body_surface')
for v in bm.verts:v[ringid]=0
for f in bm.faces:f[region]=0;f[surface]=0
gi={g.name:g.index for g in m.vertex_groups};head={g.index for g in m.vertex_groups if g.name=='head' or g.name.startswith(('jaw','ear_','lid_','eye_','tongue'))}
# Select only the main connected skin, leaving the separate tail and face parts.
seen=set();components=[]
for v in bm.verts:
 if v in seen:continue
 todo=[v];seen.add(v);comp=set()
 while todo:
  q=todo.pop();comp.add(q)
  for e in q.link_edges:
   w=e.other_vert(q)
   if w not in seen:seen.add(w);todo.append(w)
 components.append(comp)
main=max(components,key=len)
cut={f for f in bm.faces if f.material_index==0 and f.verts[0] in main and sum(sum(w for g,w in v[dv].items() if g in head) for v in f.verts)/len(f.verts)<.4}
bmesh.ops.delete(bm,geom=list(cut),context='FACES_ONLY')
loose=[e for e in bm.edges if not e.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
loose=[v for v in bm.verts if not v.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
def weights(v,ws):
 for g in list(v[dv].keys()):del v[dv][g]
 for n,w in ws.items():v[dv][gi[n]]=w
def vert(co,ws,code=0):
 v=bm.verts.new(co);v[ringid]=code
 for layer in shapes:v[layer]=co
 weights(v,ws);return v
def face(vs,reg=0):
 f=bm.faces.new(vs);f.material_index=0;f.smooth=False;f[region]=reg;f[surface]=1
 for l in f.loops:l[uv].uv=(l.vert.co.x*7+.5,l.vert.co.y*5+l.vert.co.z*3+.5)
 return f
ys=[-.060,-.050,-.036,-.022,0,.022,.036,.050,.060]
rxs=[.022,.034,.041,.048,.050,.048,.043,.033,.018]
rzs=[.022,.031,.036,.039,.040,.038,.034,.027,.018]
zs=[.081,.077,.075,.074,.073,.074,.076,.079,.081]
def bodyweights(y):
 keys=[(-.036,'chest'),(-.009,'abdomen'),(.016,'lumbar'),(.041,'pelvis')]
 if y<=keys[0][0]:return {keys[0][1]:1.}
 if y>=keys[-1][0]:return {keys[-1][1]:1.}
 for (v0,n0),(v1,n1) in zip(keys,keys[1:]):
  if v0<=y<=v1:
   t=(y-v0)/(v1-v0);return {n0:1-t,n1:t}
grid=[]
for y,rx,rz,z in zip(ys,rxs,rzs,zs):
 grid.append([vert(Vector((rx*math.cos(-math.pi/2+j*math.tau/12),y,z+rz*math.sin(-math.pi/2+j*math.tau/12))),bodyweights(y)) for j in range(12)])
patches={'F_L':(1,1),'F_R':(1,9),'H_L':(5,1),'H_R':(5,9),'neck':(1,5)}
holes={(i,j) for ii,jj in patches.values() for i in [ii,ii+1] for j in [jj,jj+1]}
for i in range(len(grid)-1):
 for j in range(12):
  if (i,j) not in holes:face([grid[i][j],grid[i+1][j],grid[i+1][(j+1)%12],grid[i][(j+1)%12]])
for i in [0,8]:
 c=vert(Vector((0,ys[i],zs[i])),bodyweights(ys[i]))
 for j in range(12):face([grid[i][j],grid[i][(j+1)%12],c])
def boundary(ii,jj):
 return [grid[ii][jj],grid[ii+1][jj],grid[ii+2][jj],grid[ii+2][jj+1],grid[ii+2][jj+2],grid[ii+1][jj+2],grid[ii][jj+2],grid[ii][jj+1]]
records={};built={}
for reg,key in enumerate(['F_L','F_R','H_L','H_R'],1):
 front=key.startswith('F');side=key[-1];cx=.026*(1 if side=='L' else -1);cy=-.036 if front else .038;torso='chest' if front else 'pelvis'
 root=boundary(*patches[key]);root.sort(key=lambda v:math.atan2(v.co.y-cy,v.co.x-cx));N=8
 if side=='R':
  source_root=built[key[:-1]+'L'][0]
  root=[min(root,key=lambda v:(v.co-Vector((-source_root[j].co.x,source_root[j].co.y,source_root[j].co.z))).length_squared) for j in reversed(range(8))]
 ws=[{torso:1},{('upperarm_' if front else 'thigh_')+side:1},{('support_forearm_' if front else 'support_shin_')+side:1},{('forearm_' if front else 'support_hock_')+side:1},{('paw_F_' if front else 'paw_H_')+side:1},{('paw_F_' if front else 'paw_H_')+side:1}]
 for v in root:v[ringid]=reg*100+1;weights(v,ws[0])
 rings=[root]
 for k in range(1,6):
  row=[]
  for j,r in enumerate(root):
   theta=-math.pi+j*math.tau/N+(math.pi/8 if k==3 else 0)
   z=[0,.035,.027,.017,.007,-.0009][k];rx=[0,.012,.011,.010,.010,.0105][k];ry=[0,.012,.011,.010,.0115,.0122][k]
   ex=math.copysign(abs(math.cos(theta))**.75,math.cos(theta));ey=math.copysign(abs(math.sin(theta))**.75,math.sin(theta))
   co=Vector((cx+rx*ex,cy-(.002 if k>=4 else 0)+ry*ey,z))
   if k==1:co=(co+r.co)*.5
   if side=='R':
    left=built[key[:-1]+'L'][k][7-j].co;co=Vector((-left.x,left.y,left.z))
   row.append(vert(co,ws[k],reg*100+k+1))
  rings.append(row)
 built[key]=rings
 for k in range(5):
  for j in range(8):face([rings[k][j],rings[k][(j+1)%8],rings[k+1][(j+1)%8],rings[k+1][j]],reg)
 c=vert(Vector((cx,cy-.002,-.0009)),ws[-1],reg*100+6)
 for j in range(8):face([rings[-1][j],rings[-1][(j+1)%8],c],reg)
 records[key]={'rings':6,'vertices_per_ring':8,'integrated_torso_boundary':True}
# Neck top is intentionally inside the preserved head, like the original eyes
# and collar. It is not counted as an exposed body-surface intersection.
neck=boundary(*patches['neck']);neck.sort(key=lambda v:math.atan2(v.co.y+.044,v.co.x));top=[]
for j in range(8):
 t=-math.pi+j*math.tau/8;top.append(vert(Vector((.027*math.cos(t),-.052+.024*math.sin(t),.125)),{'neck':1}))
for j in range(8):face([neck[j],neck[(j+1)%8],top[(j+1)%8],top[j]])
c=vert(Vector((0,-.052,.125)),{'neck':1})
for j in range(8):face([top[j],top[(j+1)%8],c])
# Remove unused centers inside the five branch openings.
loose=[v for v in bm.verts if not v.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if f[surface] or len(f.verts)>4]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m.data);bm.free();m.data.update()
if m.data.has_custom_normals:
 bpy.context.view_layer.objects.active=m
 with bpy.context.temp_override(object=m,active_object=m,selected_objects=[m],selected_editable_objects=[m]):bpy.ops.mesh.customdata_custom_splitnormals_clear()
a.animation_data.action=bpy.data.actions['V2_AUTHORING_TEMPLATE'];a['controls_enabled']=1.;sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
a['uniform_topology_note']='Connected torso and four limb openings with uniform eight-sided limb rings. Original face retained; neck overlap is internal.'
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_UniformJointRepair.blend'))
(O/'QA/rebuild.json').write_text(json.dumps({'method':'connected torso and limb retopology','limbs':records,'vertices':len(m.data.vertices),'triangles':sum(len(p.vertices)-2 for p in m.data.polygons)},indent=2))
