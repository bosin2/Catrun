import bpy,math,json
import numpy as np
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
O=Path(__file__).resolve().parents[1]/'SitSleep';(O/'Previews').mkdir(parents=True,exist_ok=True);sc=bpy.context.scene
a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH' and o.vertex_groups);rest={b.name:b.matrix_local.copy() for b in a.data.bones};length={b.name:b.length for b in a.data.bones}
def repair_body_weights():
 # Keep bind matrices and geometry; remove distant head/opposite-limb influence
 # from the body and use short, normalized anatomical transitions.
 def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
 def mix(A,B,t):
  w={n:v*(1-t) for n,v in A.items()}
  for n,v in B.items():w[n]=w.get(n,0)+v*t
  return {n:v for n,v in w.items() if v>1e-6}
 def chain(z,keys):
  if z<=keys[0][0]:return {keys[0][1]:1}
  for (p,n),(q,o) in zip(keys,keys[1:]):
   if z<=q:return {n:1-smooth((z-p)/(q-p)),o:smooth((z-p)/(q-p))}
  return {keys[-1][1]:1}
 fur=set(i for p in m.data.polygons if p.material_index==0 for i in p.vertices);changed=0
 for v in m.data.vertices:
  x,y,z=v.co
  if v.index not in fur or z>.108 or y>.066:continue
  # Existing head and eye parts remain untouched.
  if y<-.060 or (z>.092 and y<-.045):continue
  torso=chain(y,[(-.040,'chest'),(-.016,'spine'),(.012,'lumbar'),(.037,'pelvis')])
  front=y<0;side='L' if x>0 else 'R';cy=-.036 if front else .038
  if abs(x)>.009 and abs(y-cy)<.026 and z<.078:
   if front:limb=chain(z,[(.010,'paw_F_'+side),(.017,'forearm_'+side),(.034,'forearm_'+side),(.045,'upperarm_'+side),(.063,'upperarm_'+side)])
   else:limb=chain(z,[(.009,'paw_H_'+side),(.015,'hock_'+side),(.025,'shin_'+side),(.041,'shin_'+side),(.052,'thigh_'+side),(.065,'thigh_'+side)])
   t=smooth((.077-z)/.019)*smooth((abs(x)-.009)/.012)*smooth((.028-abs(y-cy))/.010)
   if z<.034:t=1.
   w=mix(torso,limb,t)
  else:w=torso
  if z>.086 and y<-.022:w=mix(w,{'neck':1},smooth((z-.086)/.020)*smooth((-.022-y)/.028))
  w=dict(sorted(w.items(),key=lambda kv:kv[1],reverse=True)[:4]);s=sum(w.values());w={n:v/s for n,v in w.items()}
  for g in [g.group for g in v.groups]:m.vertex_groups[g].remove([v.index])
  for n,value in w.items():m.vertex_groups[n].add([v.index],value,'REPLACE')
  changed+=1
 print('WEIGHT_REPAIR',changed,flush=True)
a['sit_corrective']=0.
def update():a.update_tag();bpy.context.view_layer.update()
def reset():
 a.animation_data.action=None
 for p in a.pose.bones:p.matrix_basis.identity();p.rotation_mode='QUATERNION'
 update()
def place(n,pos,rot):a.pose.bones[n].matrix=Matrix.Translation(Vector(pos))@rot.to_4x4();update()
def aim(n,pos,direction):
 original=rest[n].col[1].to_3d().normalized();q=original.rotation_difference(Vector(direction).normalized());place(n,pos,q.to_matrix()@rest[n].to_3x3())
def floor_tail(points,tap=0):
 names=[f'tail_{i:02d}' for i in range(1,8)];base=a.pose.bones[names[0]].head.copy();P=[base]+[Vector(p) for p in points]
 ts=[i/500 for i in range(501)];curve=[(1-t)**3*P[0]+3*(1-t)**2*t*P[1]+3*(1-t)*t*t*P[2]+t**3*P[3] for t in ts]
 arc=[0.]
 for i in range(1,len(curve)):arc.append(arc[-1]+(curve[i]-curve[i-1]).length)
 # Continue along the endpoint tangent if the desired arc is shorter than the
 # real tail. Never fold the last bones backward toward a clamped endpoint.
 tangent=(curve[-1]-curve[-2]).normalized()
 while arc[-1]<sum(length[n] for n in names)+.025:curve.append(curve[-1]+tangent*.001);arc.append(arc[-1]+.001)
 pos=base.copy();s=0
 for i,n in enumerate(names):
  s+=length[n];idx=int(np.searchsorted(arc,min(s,arc[-1])));idx=min(len(curve)-1,idx);target=curve[idx].copy();target.z+=tap*(i/6)**2
  direction=(target-pos).normalized();z=Vector((0,0,1));z=(z-direction*z.dot(direction)).normalized();x=direction.cross(z).normalized();rot=Matrix(((x.x,direction.x,z.x),(x.y,direction.y,z.y),(x.z,direction.z,z.z)))
  place(n,pos,rot);pos=a.pose.bones[n].tail.copy()
 return pos
def sit(t=0,ear=False,tail=False):
 reset();hip=Vector((0,.035,.029));rot=Matrix.Rotation(math.radians(-36),3,'X');place('pelvis',hip,rot@rest['pelvis'].to_3x3())
 neckpos=a.pose.bones['neck'].head.copy();place('neck',neckpos,rest['neck'].to_3x3())
 collar=a.pose.bones['collar'];place('collar',collar.head.copy(),Matrix.Rotation(math.radians(-39),3,'X')@collar.matrix.to_3x3())
 place('bell',a.pose.bones['bell'].head.copy(),rest['bell'].to_3x3())
 for side,sign in [('L',1),('R',-1)]:
  scap=a.pose.bones['scapula_'+side];mat=scap.matrix.copy();mat.translation.z-=.007;scap.matrix=mat;update()
  upper='upperarm_'+side;fore='forearm_'+side;S=a.pose.bones[upper].head.copy();T=Vector((sign*.019,-.024,.012));D=T-S;d=D.length;direction=D.normalized();l1=length[upper];l2=length[fore]
  if d>l1+l2-.0002:
   shift=Vector((0,0,-(d-l1-l2+.0004)));mat=scap.matrix.copy();mat.translation+=shift;scap.matrix=mat;update();S=a.pose.bones[upper].head.copy();D=T-S;d=D.length;direction=D.normalized()
  proj=(l1*l1-l2*l2+d*d)/(2*d);h=math.sqrt(max(0,l1*l1-proj*proj));pole=Vector((0,1,0));pole=(pole-direction*pole.dot(direction)).normalized();E=S+direction*proj+pole*h
  aim(upper,S,E-S);aim(fore,E,T-E);place('paw_F_'+side,T,rest['paw_F_'+side].to_3x3())
  n='thigh_'+side;H=a.pose.bones[n].head.copy();K=H+Vector((sign*.010,-.030,.008)).normalized()*length[n];aim(n,H,K-H)
  n='shin_'+side;A=K+Vector((0,.032,-.023)).normalized()*length[n];aim(n,K,A-K)
  n='hock_'+side;P=A+Vector((-sign*.004,-.022,-.001)).normalized()*length[n];aim(n,A,P-A);place('paw_H_'+side,P,rest['paw_H_'+side].to_3x3())
 if ear:
  # A soft one-sided listening response, with a held head tilt and quiet return.
  def ease(x):x=max(0,min(1,x));return x*x*(3-2*x)
  g=ease((t-.15)/.65)*(1-ease((t-2.10)/.9));h=ease((t-.35)/.85)*(1-ease((t-2.2)/1.0))
  p=a.pose.bones['head'];mat=p.matrix.copy();pos=mat.translation.copy();place('head',pos,Matrix.Rotation(math.radians(8)*h,3,'Y')@mat.to_3x3())
  for side,degrees in [('L',-18),('R',8)]:
   p=a.pose.bones['ear_'+side];mat=p.matrix.copy();place(p.name,mat.translation,Matrix.Rotation(math.radians(degrees)*g,3,'Z')@mat.to_3x3())
 pulse=0
 if tail:
  for center in [1.0,1.55]:
   u=(t-center)/.40
   if 0<u<1:pulse+=.011*math.sin(math.pi*u)**2
 tip=floor_tail([(0,.083,.010),(-.085,.091,.008),(-.124,.027,.008)],pulse)
 return tip
def sleep_tail(t):
 base=a.pose.bones['tail_01'].head.copy();tip=floor_tail([(base.x+.026,base.y+.023,.012),(.073,.035,.009),(.045,-.034,.008)],.00035*math.sin(math.tau*t/8))
 return tip
def key(f,names=None):
 for p in a.pose.bones:
  if names and p.name not in names:continue
  for channel in ['location','rotation_quaternion','scale']:p.keyframe_insert(channel,frame=f,group=p.name)
def linear(action):
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
def add_sit_corrective():
 # A pose-specific correction; original rest mesh, weights, and sleeping body
 # remain untouched. Smooth only the sitting body's compressed skin.
 update();ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();posed=np.array([v.co[:] for v in me.vertices]);ev.to_mesh_clear();base=np.array([v.co[:] for v in m.data.vertices]);edges=np.array([e.vertices[:] for e in m.data.edges]);fur={i for p in m.data.polygons if p.material_index==0 for i in p.vertices}
 mask=np.array([1. if i in fur and co[2]<.100 and co[1]<.065 and co[1]>-.060 and co[2]>.013 else 0. for i,co in enumerate(base)])
 mask*=np.clip((.103-base[:,2])/.015,0,1)*np.clip((base[:,2]-.013)/.012,0,1)
 target=posed.copy();degree=np.bincount(edges.ravel(),minlength=len(base));degree=np.maximum(1,degree)
 for it in range(32):
  for rate in [.47,-.48]:
   sums=np.zeros_like(target);np.add.at(sums,edges[:,0],target[edges[:,1]]);np.add.at(sums,edges[:,1],target[edges[:,0]]);target+=(sums/degree[:,None]-target)*(rate*mask[:,None])
 def ramp(x):x=max(0,min(1,float(x)));return x*x*(3-2*x)
 # Sculpt the compressed limb skin into broad facets for this sitting pose.
 # The shoulders remain above planted front paws; folded haunches stay behind.
 for i,co in enumerate(base):
  if mask[i]<=0:continue
  x,y,z=co;sign=1 if x>0 else -1;cx=.026*sign;front=y<0;cy=-.036 if front else .038
  dy=y-cy;dx=x-cx
  if abs(x)<.010 or abs(dy)>.027 or z>.072:continue
  angle=math.atan2(dy,dx);octagon=math.cos(math.pi/8)/math.cos((angle+math.pi/8)%(math.pi/4)-math.pi/8)
  blend=ramp((z-.013)/.012)*ramp((.072-z)/.017)*ramp((.027-abs(dy))/.011)*ramp((abs(x)-.010)/.009)
  if front:
   t=max(0,min(1,(z-.012)/.055));center=Vector((sign*(.014+.010*t),-.024+.007*t,.012+.065*t));rx=.0105;ry=.0115
   desired=np.array([center.x+rx*octagon*math.cos(angle),center.y+ry*octagon*math.sin(angle),center.z])
  else:
   t=max(0,min(1,(z-.013)/.054));profile=float(np.interp(z,[.013,.032,.050,.067],[.38,1.,.88,.52]));center=Vector((sign*.030,.026+.004*t,.011+.049*t))
   desired=np.array([center.x+.023*profile*octagon*math.cos(angle),center.y+.027*profile*octagon*math.sin(angle),center.z])
  target[i]=target[i]*(1-blend)+desired*blend
 transforms={b.name:np.array(a.pose.bones[b.name].matrix@b.matrix_local.inverted()) for b in a.data.bones}
 if not m.data.shape_keys:m.shape_key_add(name='Basis')
 key=m.shape_key_add(name='Sit_SurfaceCorrection');errors=[]
 for v in m.data.vertices:
  if mask[v.index]<=0:continue
  mat=sum((transforms[m.vertex_groups[g.group].name]*g.weight for g in v.groups if m.vertex_groups[g.group].name in transforms),np.zeros((4,4)))
  predicted=(mat@np.r_[base[v.index],1])[:3];errors.append(float(np.linalg.norm(predicted-posed[v.index])))
  delta=np.linalg.pinv(mat[:3,:3])@(target[v.index]-posed[v.index]);key.data[v.index].co=Vector(base[v.index]+delta)
 d=key.driver_add('value').driver;d.type='SCRIPTED';d.expression='s';v=d.variables.new();v.name='s';v.type='SINGLE_PROP';v.targets[0].id=a;v.targets[0].data_path='["sit_corrective"]';a['sit_corrective']=1.;update()
 print('CORRECTIVE',json.dumps({'max_skin_prediction_error':max(errors),'max_pose_offset':float(np.linalg.norm(target-posed,axis=1).max())}),flush=True)
def make_preview():
 sit();add_sit_corrective();cam=bpy.data.objects.new('SitPreview',bpy.data.cameras.new('SitPreview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.31
 sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD'
 if not sc.world:sc.world=bpy.data.worlds.new('ReviewWorld')
 sc.world.color=(.24,.24,.24)
 for label,loc in [('front',(0,-.5,.14)),('side',(.5,0,.14)),('threequarter',(.32,-.45,.20))]:
  cam.location=loc;cam.rotation_euler=(Vector((0,.015,.105))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Previews'/f'sit_{label}.png');bpy.ops.render.render(write_still=True)
 print('SIT_POSE',json.dumps({n:list(a.pose.bones[n].head) for n in ['pelvis','head','paw_F_L','paw_H_L','tail_01']}))
if __name__=='__main__':make_preview()
