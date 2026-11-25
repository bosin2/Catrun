"""Distribute the final part of a deep FK knee fold over the hock."""
import bpy,math
a=bpy.data.objects['ARM_BlackCat_RigV2']
def vars(driver,side,angle=False):
 for name,path in [('on','["controls_enabled"]'),('ik',f'pose.bones["CTRL_IK_H_{side}"]["ik"]')]:
  v=driver.variables.new();v.name=name;v.type='SINGLE_PROP';v.targets[0].id=a;v.targets[0].data_path=path
 if angle:
  v=driver.variables.new();v.name='r';v.type='TRANSFORMS';v.targets[0].id=a;v.targets[0].bone_target='CTRL_shin_'+side;v.targets[0].transform_type='ROT_X';v.targets[0].transform_space='LOCAL_SPACE'
for side in ['L','R']:
 p=a.pose.bones['shin_'+side];c=p.constraints.new('LIMIT_ROTATION');c.name='Deep FK fold distribution';c.owner_space='LOCAL';c.use_limit_x=True;c.min_x=-math.pi;c.max_x=math.radians(100);d=c.driver_add('influence').driver;d.type='SCRIPTED';d.expression='on*(1-ik)';vars(d,side)
 p=a.pose.bones['hock_'+side];c=p.constraints.new('COPY_ROTATION');c.name='Deep FK hock continuation';c.target=a;c.subtarget='CTRL_shin_'+side;c.owner_space='LOCAL';c.target_space='LOCAL';c.use_x=True;c.use_y=False;c.use_z=False;c.mix_mode='ADD';d=c.driver_add('influence').driver;d.type='SCRIPTED';d.expression='on*(1-ik)*max(0,r-1.745329)/max(0.001,abs(r))';vars(d,side,True)
a['deep_fold_note']='In FK, knee control rotation above 100 degrees continues through the hock. IK is unaffected. Bake deform bones for export.'
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
