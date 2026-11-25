import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector,Matrix
HERE=Path(__file__).parent
old=HERE.parent/'PortalEntry20261125'/'build_portal.py'
exec(compile(old.read_text(encoding='utf8').split('clips=[];samples={}')[0],str(old),'exec'))
O=HERE;(O/'Previews').mkdir(exist_ok=True);(O/'QA').mkdir(exist_ok=True)
sys.path.insert(0,str(HERE.parent/'RigV2'/'Scripts'));import build_sit_sleep as B
sys.path.insert(0,str(HERE));import body_surface as surface
original_names=[p.name for p in a.pose.bones];walk=[]
for f in range(1,122):walk.append(sample('AN_BlackCat_Walk',f)[0])
apply(base)
for n in feet:feet[n].z=.012 if '_F_' in n else .011
legs(feet);base={n:snapshot()[n] for n in original_names};world={p.name:p.matrix.copy() for p in a.pose.bones}
B.sit()
for side in ['L','R']:
 n='paw_H_'+side;P=a.pose.bones[n].head.copy();P.z=.011;oldH=a.pose.bones['hock_'+side].head.copy();direction=(a.pose.bones[n].head-oldH).normalized();A=P-direction*length['hock_'+side];H=a.pose.bones['thigh_'+side].head.copy();pole=a.pose.bones['shin_'+side].head-H;two_bone('thigh_'+side,'shin_'+side,H,A,pole);aim('hock_'+side,A,P-A);place(n,P,world[n].to_3x3())
neck=a.pose.bones['neck'];mat=neck.matrix.copy();mat.translation.y+=.010;neck.matrix=mat;update()
seated=snapshot();seated={n:seated[n] for n in original_names}
sitworld={p.name:p.matrix.copy() for p in a.pose.bones};sitfeet={n:sitworld[n].translation.copy() for n in feet}
# Finish the final walking step directly into the sit instead of snapping
# the moving paws back to an unrelated idle pose at the clip boundary.
apply(walk[119])
for n in feet:
 p=a.pose.bones[n];mat=p.matrix.copy();mat.translation.z-=.001433;p.matrix=mat;update()
approach={n:snapshot()[n] for n in original_names};approachfeet={n:a.pose.bones[n].head.copy() for n in feet}
# Original rig rest and face are retained; supporting skin is a separate revision.
a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
update();skin=surface.initialize(a,m);body=skin['body']
import retained_mesh_cleanup
retained_cleanup=retained_mesh_cleanup.cleanup(m,a)
(O/'QA'/'retained_cleanup_applied.json').write_text(json.dumps(retained_cleanup,indent=2),encoding='utf8')
PORTAL_Y=-.105
def pose_mix(A,B,t):return {n:A[n].lerp(B[n],t) for n in original_names}
def apply_original(pose):
 a.animation_data.action=None
 for n in original_names:a.pose.bones[n].matrix_basis=pose[n]
 update()
def fore(side,target,pawrot=None):
 n='upperarm_'+side;S=a.pose.bones[n].head.copy();limit=length[n]+length['forearm_'+side]-.0003;d=(target-S).length
 if d>limit:
  scap=a.pose.bones['scapula_'+side];mat=scap.matrix.copy();mat.translation+=(target-S).normalized()*(d-limit);scap.matrix=mat;update();S=a.pose.bones[n].head.copy()
 two_bone(n,'forearm_'+side,S,target,((1 if side=='L' else -1)*.12,1,-.65));place('paw_F_'+side,target,pawrot or world['paw_F_'+side].to_3x3())

def airborne_paw(side,target,lift=1.,contact=0.):
 # Keep the free paw in line with its forearm; only turn the palm out for
 # the final approach to the vertical portal. A grounded palm in flight
 # would fold the skin through 180 degrees at the wrist.
 fore(side,target)
 n='paw_F_'+side;E=a.pose.bones['forearm_'+side].head.copy()
 direction=target-E
 # This gesture reaches in the Y/Z plane. Removing lateral roll also avoids
 # an unstable wrist twist as a raised paw passes through a near-vertical arm.
 direction.x=0
 D=Vector((0,0,-1)).rotation_difference(direction.normalized())
 Q=(D.to_matrix()@rest[n].to_3x3()).to_quaternion()
 Q=world[n].to_quaternion().slerp(Q,lift)
 touchQ=(Matrix.Rotation(-math.pi/2,3,'X')@rest[n].to_3x3()).to_quaternion()
 place(n,target,Q.slerp(touchQ,contact).to_matrix())
def seated_touch(f):
 if f<19:
  apply_original(pose_mix(approach,seated,ramp(f,1,19)))
  # One front paw at a time settles inward, rather than skating on the floor.
  for side,lo,hi in [('L',3,10),('R',10,17)]:
   u=ramp(f,lo,hi);T=approachfeet['paw_F_'+side].lerp(sitfeet['paw_F_'+side],u);T.z+=.006*math.sin(math.pi*u);fore(side,T)
  for side,lo,hi in [('L',3,11),('R',10,18)]:
   n='paw_H_'+side;u=ramp(f,lo,hi);P=approachfeet[n].lerp(sitfeet[n],u);P.z+=.005*math.sin(math.pi*u);H=a.pose.bones['thigh_'+side].head.copy();oldA=a.pose.bones['hock_'+side].head.copy();hv=(a.pose.bones[n].head-oldA).normalized();A=P-hv*length['hock_'+side];pole=a.pose.bones['shin_'+side].head-H;two_bone('thigh_'+side,'shin_'+side,H,A,pole);aim('hock_'+side,A,P-A);place(n,P,world[n].to_3x3())
 else:
  apply_original(seated)
  listen=ramp(f,20,27);tilt=ramp(f,24,32)*(1-ramp(f,43,51));head_ears(tilt=8*tilt,ear=listen*(1-ramp(f,68,77)))
  if f>=43:
   shift=ramp(f,43,50)*(1-ramp(f,69,80))
   for n in ['pelvis','chest']:
    p=a.pose.bones[n];mat=p.matrix.copy();mat.translation.x-=.003*shift
    if n=='chest':mat.translation.y-=.004*shift
    p.matrix=mat;update()
   head_ears(look=3*shift)
   fore('R',sitfeet['paw_F_R'])
   P=sitfeet['paw_F_L'];contact=Vector((.042,PORTAL_Y+.012,.065))
   T=curve(f,[(43,P),(46,P),(51,Vector((.036,-.068,.050))),(57,contact),(64,contact),(70,Vector((.039,-.068,.050))),(79,P)])
   scap=a.pose.bones['scapula_L'];mat=scap.matrix.copy();mat.translation.y-=.012*ramp(f,51,57)*(1-ramp(f,64,71));scap.matrix=mat;update()
   lift=ramp(f,46,51)*(1-ramp(f,73,79));contact_turn=ramp(f,54,57)*(1-ramp(f,64,67));airborne_paw('L',T,lift,contact_turn)
 # The tail rests beside the seated body; retain the original mesh and chain.
 if f>=19:B.floor_tail([(0,.084,.012),(-.085,.091,.010),(-.124,.027,.010)])
 if f==1:apply_original(approach)
 return snapshot()
seated_touch(91);touch_end={n:snapshot()[n] for n in original_names}
rear_targets={n:p.copy() for n,p in sitfeet.items()}
for n in ['paw_H_L','paw_H_R']:rear_targets[n]=Vector((.028 if n.endswith('L') else -.028,.053,.011))
def stretched(f):
 # This pose visibly separates low shoulders from the rearward, higher pelvis.
 sway=0.
 if 14<f<38:
  u=(f-14)/24;sway=.009*math.sin(4*math.pi*u)*ease(u/.08)*(1-ease((u-.92)/.08))
 comp=ramp(f,41,53);H=Vector((sway,.064-.013*comp,.071-.028*comp));C=Vector((0,-.026,.057-.013*comp))
 apply_original(base)
 for n,t in [('pelvis',0),('lumbar',.28),('spine',.60),('chest',1)]:
  pos=H.lerp(C,t);aim(n,pos,C-H)
 # Keep the face directed toward the opening while the torso stretches back.
 neckpos=C+Vector((0,-.005,.012));headpos=Vector((0,-.043,.098-.015*comp));aim('neck',neckpos,headpos-neckpos);place('head',headpos,world['head'].to_3x3())
 place('collar',headpos+Vector((0,.007,-.014)),Matrix.Rotation(math.radians(-30),3,'X')@rest['collar'].to_3x3());place('bell',a.pose.bones['bell'].head.copy(),rest['bell'].to_3x3())
 targets={n:p.copy() for n,p in rear_targets.items()};legs(targets,compression=.35+.65*comp)
 # Low, loose tail counterbalance instead of the stiff upright rod.
 p=a.pose.bones['tail_01'];P=p.head.copy();B.floor_tail([(P.x,P.y+.045,P.z-.016),(P.x-.008,P.y+.09,.036),(P.x-.025,P.y+.135,.025)])
 return {n:snapshot()[n] for n in original_names}
stretch=stretched(14)
def prepare(f):
 if f<14:
  u=ramp(f,1,14);apply_original(pose_mix(touch_end,stretch,u))
  for side in ['L','R']:fore(side,sitfeet['paw_F_'+side])
  # Rear paws make short separate placement steps as the hips rise and go back.
  for side,lo,hi in [('L',2,8),('R',7,13)]:
   u2=ramp(f,lo,hi);n='paw_H_'+side;P=sitfeet[n].lerp(rear_targets[n],u2);P.z+=.006*math.sin(math.pi*u2);H=a.pose.bones['thigh_'+side].head.copy();hv=(world[n].translation-world['hock_'+side].translation).normalized();A=P-hv*length['hock_'+side];two_bone('thigh_'+side,'shin_'+side,H,A,((1 if side=='L' else -1)*.20,-1,0));aim('hock_'+side,A,P-A);place(n,P,world[n].to_3x3())
 else:stretched(f)
 if f==1:apply_original(touch_end)
prepare(53);crouch={n:snapshot()[n] for n in original_names}
# Author a readable reaching flight silhouette instead of returning to the
# rejected old JumpIn's dangling-legged airborne pose.
apply_original(air);air_targets={n:p.copy() for n,p in feet.items()}
for side,sgn in [('L',1),('R',-1)]:
 air_targets['paw_F_'+side]=Vector((sgn*.035,-.108,.105));air_targets['paw_H_'+side]=Vector((sgn*.030,.075,.040))
legs(air_targets,compression=0)
for side in ['L','R']:airborne_paw(side,air_targets['paw_F_'+side])
headpos=a.pose.bones['head'].head.copy()
place('collar',headpos+Vector((0,.007,-.014)),Matrix.Rotation(math.radians(-30),3,'X')@rest['collar'].to_3x3());place('bell',a.pose.bones['bell'].head.copy(),rest['bell'].to_3x3())
P=a.pose.bones['tail_01'].head.copy();B.floor_tail([(P.x,P.y+.045,P.z+.005),(P.x-.008,P.y+.09,P.z+.01),(P.x-.016,P.y+.14,P.z+.025)])
newair={n:snapshot()[n] for n in original_names}
def launch(f):
 t=ramp(f,1,13);apply_original(pose_mix(crouch,newair,t));targets={n:p.copy() for n,p in rear_targets.items()}
 for side,sgn in [('L',1),('R',-1)]:
  n='paw_F_'+side;targets[n]=curve(f,[(1,sitfeet[n]),(2,Vector((sgn*.030,-.078,.045))),(6,Vector((sgn*.035,-.112,.110))),(13,air_targets[n])])
  n='paw_H_'+side;u=ramp(f,9,13);targets[n]=rear_targets[n].lerp(air_targets[n],u)
 if f<13:
  legs(targets,compression=1-t)
  for side in ['L','R']:airborne_paw(side,targets['paw_F_'+side],ramp(f,1,3))
 if f==1:apply_original(crouch)
 if f==13:apply_original(newair)
def flight(f):
 apply_original(newair)
 p=a.pose.bones['head'];place('head',p.head.copy(),Matrix.Rotation(math.radians(-5)*ramp(f,1,9),3,'X')@p.matrix.to_3x3())
def evaluate(kind,f):
 if kind=='touch':seated_touch(f)
 elif kind=='prepare':prepare(f)
 elif kind=='launch':launch(f)
 elif kind=='flight':flight(f)
 elif kind=='walk':
  apply_original(walk[min(119,int(f)-1)])
  for n in feet:
   p=a.pose.bones[n];mat=p.matrix.copy();mat.translation.z-=.001433; p.matrix=mat;update()
 surface.update(a)
def preview_setup():
 sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=900;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world=bpy.data.worlds.new('RevisionWorld');sc.world.color=(.17,.18,.20)
 cam=bpy.data.objects.new('MotionReviewCamera',bpy.data.cameras.new('MotionReviewCamera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.52
 mat=bpy.data.materials.new('PortalBlueReference');mat.diffuse_color=(.05,.50,1,1)
 bpy.ops.mesh.primitive_torus_add(major_segments=40,minor_segments=6,major_radius=.17,minor_radius=.002,location=(0,PORTAL_Y,.17),rotation=(math.pi/2,0,0));ring=bpy.context.object;ring.name='REFERENCE_PortalContactPlane';ring.data.materials.append(mat)
 floor_mat=bpy.data.materials.new('ReviewFloor');floor_mat.diffuse_color=(.20,.22,.24,1);bpy.ops.mesh.primitive_plane_add(size=1.,location=(0,0,-.001));floor=bpy.context.object;floor.name='REFERENCE_Floor';floor.data.materials.append(floor_mat)
 return cam
cam=preview_setup()
for kind,f in [('walk',1),('touch',32),('touch',60),('prepare',14),('prepare',20),('prepare',53),('launch',8)]:
 evaluate(kind,f)
 for label,loc in [('side',(.50,.03,.17)),('threequarter',(.38,-.45,.18))]:
  cam.location=loc;cam.rotation_euler=(Vector((0,-.015,.15))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Previews'/f'{kind}_{f}_{label}.png');bpy.ops.render.render(write_still=True)
print('POSE_PREVIEW_READY',skin['triangles'],flush=True)
