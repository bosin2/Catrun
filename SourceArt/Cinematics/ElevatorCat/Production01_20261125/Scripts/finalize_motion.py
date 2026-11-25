import bpy,pathlib,json
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final']
master=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];release=bpy.data.actions['AN_BlackCat_Elevator_ReleaseLand']
arm.animation_data.action=master;sc.frame_set(55)
names=['tail_%02d'%i for i in range(1,8)]
a={n:arm.pose.bones[n].rotation_quaternion.copy() for n in names};sc.frame_set(73);b={n:arm.pose.bones[n].rotation_quaternion.copy() for n in names}
for action,offset in [(master,0),(release,54)]:
 arm.animation_data.action=action
 for mf in range(55,74):
  f=mf-offset;sc.frame_set(f);t=(mf-55)/18;t=t*t*(3-2*t)
  for n in names:
   p=arm.pose.bones[n];p.rotation_quaternion=a[n].slerp(b[n],t);p.keyframe_insert('rotation_quaternion',frame=f,group=n)
# A one-frame startled eye opening avoids intersections of the existing spherical
# lid segments at interpolated partial closure. No facial geometry is altered.
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];sc.frame_set(1)
lid_names=[p.name for p in arm.pose.bones if p.name.startswith('Lid_')]
open_lids={n:(arm.pose.bones[n].location.copy(),arm.pose.bones[n].rotation_quaternion.copy(),arm.pose.bones[n].scale.copy()) for n in lid_names}
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Sleep'];sc.frame_set(37)
closed_lids={n:(arm.pose.bones[n].location.copy(),arm.pose.bones[n].rotation_quaternion.copy(),arm.pose.bones[n].scale.copy()) for n in lid_names}
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_LoafStartleRise']
for f in range(38,83):
 sc.frame_set(f)
 for n in lid_names:
  p=arm.pose.bones[n];p.location,p.rotation_quaternion,p.scale=(closed_lids if f==38 else open_lids)[n]
  for channel in ['location','rotation_quaternion','scale']:p.keyframe_insert(channel,frame=f,group=n)
mf=json.loads((OUT/'manifest.json').read_text());mf['events']['C09']['eyes_open']=39;(OUT/'manifest.json').write_text(json.dumps(mf,indent=2))
arm.animation_data.action=master;sc.frame_start=1;sc.frame_end=102;sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SK_BlackCat_Elevator.blend'))
print('FINAL_TAIL_RELEASE_CONTINUITY_BAKED')
