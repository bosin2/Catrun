import bpy,json,pathlib,math
from mathutils import Quaternion
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final']
(OUT/'Experiments').mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Experiments/SK_BlackCat_Elevator_TailPuff_Unvalidated.blend'),copy=True)
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];sc.frame_set(1)
base={p.name:(p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()) for p in arm.pose.bones if p.name.startswith('tail_')}
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_StartleTail']
for f in range(1,62):
 sc.frame_set(f);a=smooth((f-8)/3)*(1-smooth((f-17)/32))
 for i in range(1,8):
  p=arm.pose.bones['tail_%02d'%i];loc,q,scale=base[p.name];p.location=loc;p.scale=scale;p.rotation_quaternion=q@Quaternion((0,0,1),math.radians(12*a*math.sin(i*.45)))
  for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SK_BlackCat_Elevator.blend'))
m=json.loads((OUT/'manifest.json').read_text());m['tail']='NOT DELIVERED: radial scale puff preserved native centerline but animation-only FBX round-trip moved tail joints by up to 7.48cm. Main C05 includes startle, ear reaction, balance and tail flick only. Experimental blend retained separately, not approved for export. Minimal proposed exception: one TailPuff morph on existing mesh, no added bones; requires separate user authorization.';m['clips'][4]['status']='startle_complete_tail_puff_blocked';m['clips'][4]['missing']='tail radial volume puff';m['events']['C05']['tail_flick_peak']=m['events']['C05'].pop('tail_peak');(OUT/'manifest.json').write_text(json.dumps(m,indent=2))
print('UNPORTABLE_PUFF_REMOVED_FROM_DELIVERY')
