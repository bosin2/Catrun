import bpy
a=bpy.data.objects['ARM_BlackCat_RigV2'];a['joint_fold_compression']=0.
for key in ['F_L','F_R','H_L','H_R']:
 front=key[0]=='F';bone=('forearm_' if front else 'shin_')+key[-1]
 for k,w in [(2,.25),(3,.75),(4,1.),(5,1.),(6,.5)]:
  p=a.pose.bones['skin_'+key+f'_{k:02d}']
  factor='max(0,min(1,(-r-1.22173)/0.34907))+max(0,min(1,(r-1.91986)/0.17453))' if front else 'max(0,min(1,(r-1.22173)/0.87266))'
  for axis in [0,2]:
   d=p.driver_add('scale',axis).driver;d.type='SCRIPTED';d.expression=f'1-g*{w}*({factor})'
   v=d.variables.new();v.name='g';v.type='SINGLE_PROP';v.targets[0].id=a;v.targets[0].data_path='["joint_fold_compression"]'
   v=d.variables.new();v.name='r';v.type='TRANSFORMS';v.targets[0].id=a;v.targets[0].bone_target=bone;v.targets[0].transform_type='ROT_X';v.targets[0].transform_space='LOCAL_SPACE'
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
