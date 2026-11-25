import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector,Matrix
HERE=Path(__file__).parent
source=HERE.parent/'PortalSeated20261125'/'create_revision.py'
# Reuse the accepted acting sequence, then retarget its proportions. The
# previous long-limbed delivery remains untouched in its own directory.
exec(compile(source.read_text(encoding='utf8').split('cam=preview_setup()')[0],str(source),'exec'))
long_evaluate=evaluate
LONG_PORTAL_Y=PORTAL_Y
LIMB_RATIO=.70
head_names={'head'}
for b in a.data.bones:
 p=b
 while p.parent:
  if p.parent.name=='head':head_names.add(b.name);break
  p=p.parent
head_names.update(['collar','bell'])
tail_names=[f'tail_{i:02d}' for i in range(1,8)]
def mapped(p):return Vector((p.x*1.03,p.y*.90,.012+.70*(p.z-.012)))
def compact_maps(src,kind,f,pins=None):
 dst={n:v.copy() for n,v in src.items()}
 for n in original_names:dst[n].translation=mapped(src[n].translation)
 # The face keeps its approved size and angular planes. Only its position
 # follows the shorter neck; the head itself is never squashed.
 delta=dst['neck'].translation-src['neck'].translation+Vector((0,.024,0))
 if kind=='touch':delta.y+=.006*ramp(f,43,53)*(1-ramp(f,67,79))
 for n in head_names:
  if n in dst:dst[n].translation=src[n].translation+delta
 collar=Matrix.Translation(dst['head'].translation+Vector((0,.007,-.014)))@(Matrix.Rotation(math.radians(-30),3,'X')@rest['collar'].to_3x3()).to_4x4()
 bell=collar@src['collar'].inverted()@src['bell'];bell=Matrix.Translation(bell.translation)@rest['bell'].to_3x3().to_4x4()
 dst['collar']=collar;dst['bell']=bell
 for key in ['F_L','F_R','H_L','H_R']:
  front=key.startswith('F');side=key[-1];torso='chest' if front else 'pelvis';T=src[torso].translation;C=dst[torso].translation
  chain=[('upperarm_' if front else 'thigh_')+side,('forearm_' if front else 'shin_')+side]
  if not front:chain+=['hock_'+side]
  paw='paw_'+key;chain+=[paw,'toes_'+key]
  for n in chain:
   if n in dst:dst[n].translation=C+LIMB_RATIO*(src[n].translation-T)
  if not front:
   for n in chain:
    if n in dst:dst[n].translation.z-=.0003
  if pins and key in pins:
   correction=pins[key]-dst[paw].translation
   for j,n in enumerate(chain):
    if n in dst:dst[n].translation+=correction*min(1.,j/(len(chain)-2))
 return dst
long_evaluate('touch',91);temp={n:a.pose.bones[n].matrix.copy() for n in original_names};temp=compact_maps(temp,'touch',91)
front_pins={k:temp['paw_'+k].translation.copy() for k in ['F_L','F_R']}
long_evaluate('prepare',14);temp={n:a.pose.bones[n].matrix.copy() for n in original_names};temp=compact_maps(temp,'prepare',14)
rear_pins={k:temp['paw_'+k].translation.copy() for k in ['H_L','H_R']}
long_evaluate('touch',57);temp={n:a.pose.bones[n].matrix.copy() for n in original_names};temp=compact_maps(temp,'touch',57)
PORTAL_Y=temp['paw_F_L'].translation.y-.012
CONTACT_CENTER=Vector((temp['paw_F_L'].translation.x,PORTAL_Y,temp['paw_F_L'].translation.z+.003))
def evaluate(kind,f):
 global PORTAL_Y
 # Sharper contact spacing, a brief bottom hold, then a quick whole-body
 # launch create energy without stretching the short limbs.
 sf=f
 if kind=='touch' and 43<=f<=79:
  sf=curve(f,[(43,(43,0,0)),(49,(49,0,0)),(52,(51,0,0)),(55,(57,0,0)),(60,(64,0,0)),(65,(74,0,0)),(72,(79,0,0)),(79,(79,0,0))]).x
 if kind=='prepare' and f>=41:
  sf=41+12*ramp(f,44,50)
 if kind=='launch':sf=curve(f,[(1,(1,0,0)),(2,(3,0,0)),(7,(11,0,0)),(10,(13,0,0)),(13,(13,0,0))]).x
 compact_portal=PORTAL_Y;PORTAL_Y=LONG_PORTAL_Y
 long_evaluate(kind,sf)
 PORTAL_Y=compact_portal
 src={n:a.pose.bones[n].matrix.copy() for n in original_names}
 pins={}
 if kind=='prepare':
  pins.update(front_pins)
  if f>=14:pins.update(rear_pins)
 if kind=='launch' and sf<=9:pins.update(rear_pins)
 if kind=='launch' and f==1:pins.update(front_pins)
 dst=compact_maps(src,kind,sf,pins)
 # A rising diagonal body, not elongated forearms, carries the takeoff.
 pitch=0.
 if kind=='launch':pitch=-math.radians(16)*ramp(f,1,10)
 elif kind=='flight':pitch=-math.radians(16-9*ramp(f,6,19))
 if pitch:
  pivot=dst['pelvis'].translation.copy();R=Matrix.Rotation(pitch,4,'X')
  for n in original_names:
   if n=='root' or n.startswith(('thigh_','shin_','hock_','paw_H_','toes_H_')):continue
   dst[n]=Matrix.Translation(pivot)@R@Matrix.Translation(-pivot)@dst[n]
 a.animation_data.action=None
 for n in original_names:a.pose.bones[n].matrix=dst[n];update()
 # Rebuild the retained tail as a broad curve at its new lower attachment.
 points=[]
 for n in ['tail_03','tail_05','tail_07']:
  p=mapped(src[n].translation);p.z=max(.010,p.z);points.append(p)
 B.floor_tail(points)
 surface.update(a)
 # A rotated rigid paw keeps its full thickness. Vertical retargeting of
 # the joint alone is insufficient, so correct the actual sole surface.
 ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
 sole_offsets={k:max(0.,-min(me.vertices[i].co.z for i in ids)) for k,ids in skin['vertex_groups'].items()};ev.to_mesh_clear()
 changed=False
 for key,offset in sole_offsets.items():
  if offset<1e-7:continue
  changed=True
  for n,weight in [('paw_'+key,1.),('toes_'+key,1.),(('forearm_' if key.startswith('F') else 'hock_')+key[-1],.5)]:
   p=a.pose.bones[n];mat=p.matrix.copy();mat.translation.z+=offset*weight;p.matrix=mat;update()
 if changed:surface.update(a)
 return sf
_old_preview_setup=preview_setup
def preview_setup():
 cam=_old_preview_setup();cam.data.ortho_scale=.48
 return cam
# BEGIN_PREVIEW
if __name__=='__main__':
 cam=preview_setup()
 for kind,f in [('walk',1),('touch',32),('touch',57),('prepare',20),('prepare',53),('launch',7),('flight',1)]:
  evaluate(kind,f)
  for label,loc in [('side',(.50,.03,.15)),('threequarter',(.38,-.42,.17)),('rear',(.40,.33,.17))]:
   cam.location=loc;cam.rotation_euler=(Vector((0,-.015,.12))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Previews'/f'{kind}_{f}_{label}.png');bpy.ops.render.render(write_still=True)
 print('COMPACT_PREVIEW',skin['triangles'],PORTAL_Y,list(CONTACT_CENTER),flush=True)
