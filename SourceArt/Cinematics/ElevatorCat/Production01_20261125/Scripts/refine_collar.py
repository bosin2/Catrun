import bpy,pathlib,math,json
from mathutils import Matrix,Quaternion,Vector
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];p=arm.pose.bones['collar'];master=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];arm.animation_data.action=master
def s(t):t=max(0,min(1,t));return t*t*(3-2*t)
data=[]
for f in range(1,103):
 sc.frame_set(f);w=s((f-7)/17)*(1-s((f-55)/18));m=p.matrix.copy();p.matrix=Matrix.LocRotScale(m.translation+Vector((0,.01*w,0)),Quaternion((1,0,0),math.radians(50*w))@m.to_quaternion(),m.to_scale());bpy.context.view_layer.update()
 data.append((p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()))
 for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
for name,start,end in [('JumpGrab',1,25),('HangPull',25,55),('ReleaseLand',55,102)]:
 arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_'+name]
 for f,mf in enumerate(range(start,end+1),1):
  p.location,p.rotation_quaternion,p.scale=data[mf-1]
  for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
arm.animation_data.action=master;sc.frame_set(1);sc.frame_end=102;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SK_BlackCat_Elevator.blend'))
print('COLLAR_REFINED_ARM_CLEARANCE')
