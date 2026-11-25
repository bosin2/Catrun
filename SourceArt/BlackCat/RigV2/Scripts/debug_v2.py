import bpy,json,numpy as np
a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
a['controls_enabled']=1.
for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
a.update_tag();bpy.context.view_layer.update()
diff={p.name:round(float(np.max(np.abs(np.array(p.matrix)-np.array(p.bone.matrix_local)))),6) for p in a.pose.bones if p.bone.use_deform}
print('REST_DIFF',json.dumps({k:v for k,v in diff.items() if v>.001}))
base=np.array([v.co[:] for v in m.data.shape_keys.key_blocks[0].data])
print('KEYS',json.dumps({k.name:{'value':k.value,'relative':k.relative_key.name,'delta':float(np.max(np.abs(np.array([v.co[:] for v in k.data])-base)))} for k in m.data.shape_keys.key_blocks}))
for blink in [0,.5,1.]:
 a.pose.bones['CTRL_face']['blink_L']=blink;a.pose.bones['CTRL_face']['blink_R']=blink;a.update_tag();bpy.context.view_layer.update()
 print('VALUES',blink,[(k.name,k.value) for k in m.data.shape_keys.key_blocks])
for p in ['jaw','CTRL_jaw','paw_F_L','CTRL_IK_F_L','toes_F_L','CTRL_toes_F_L']:
 print('BONE',p,'ROT',list(a.pose.bones[p].rotation_quaternion),'MATRIX',[list(r) for r in a.pose.bones[p].matrix])
