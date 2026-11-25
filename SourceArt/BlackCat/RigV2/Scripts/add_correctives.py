"""Bake localized delta-mush joint corrections to portable morph targets."""
import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Quaternion
O=Path(__file__).resolve().parents[1];a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
a.animation_data.action=None;a['controls_enabled']=0.
for p in a.pose.bones:p.matrix_basis.identity()
a.update_tag();bpy.context.view_layer.update()
rest=np.array([v.co[:] for v in m.data.shape_keys.key_blocks['Basis'].data]);N=len(rest)
names=[g.name for g in m.vertex_groups];W=np.zeros((N,len(names)))
for v in m.data.vertices:
 for g in v.groups:W[v.index,g.group]=g.weight
edges=np.array([e.vertices[:] for e in m.data.edges]);ii=np.r_[edges[:,0],edges[:,1]];jj=np.r_[edges[:,1],edges[:,0]];degree=np.bincount(ii,minlength=N);degree=np.maximum(1,degree)
def smooth(co):
 out=co.copy()
 for _ in range(10):
  avg=np.stack([np.bincount(ii,weights=out[jj,k],minlength=N)/degree for k in range(3)],1)
  out=.55*out+.45*avg
 return out
rest_smooth=smooth(rest);rest_detail=rest-rest_smooth
def update():a.update_tag();bpy.context.view_layer.update()
def coords():
 e=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();r=np.array([v.co[:] for v in me.vertices]);e.to_mesh_clear();return r
report=[];created=[]
for child in ['forearm_L','forearm_R','shin_L','shin_R','hock_L','hock_R','neck']:
 joint=np.array(a.data.bones[child].head_local);parent=a.data.bones[child].parent.name
 weights=W[:,names.index(child)]+W[:,names.index(parent)]+W[:,names.index('support_'+child)]
 dist=np.linalg.norm(rest-joint,axis=1);mask=np.clip((.028-dist)/.014,0,1)*np.clip((weights-.25)/.45,0,1)
 for sign,tag in [(1,'Pos'),(-1,'Neg')]:
  for p in a.pose.bones:p.matrix_basis.identity()
  a.pose.bones[child].rotation_quaternion=Quaternion((1,0,0),sign*1.3);update();posed=coords()
  mats=np.array([np.array((a.pose.bones[n].matrix@a.data.bones[n].matrix_local.inverted()).to_3x3()) for n in names]);skin=np.einsum('vg,gij->vij',W,mats)
  u,ss,vt=np.linalg.svd(skin);rot=u@vt
  desired=smooth(posed)+np.einsum('vij,vj->vi',rot,rest_detail)
  delta=np.einsum('vij,vj->vi',np.linalg.pinv(skin),desired-posed)*mask[:,None]
  # Keep corrections local and conservative: never expand more than 2.5 mm in source units.
  length=np.linalg.norm(delta,axis=1);delta*=np.minimum(1,.0025/np.maximum(length,1e-10))[:,None]
  key=m.shape_key_add(name='Corrective_'+child+'_'+tag,from_mix=False)
  arr=(rest+delta).astype(np.float32).ravel();key.data.foreach_set('co',arr);created.append((key,child,sign))
  report.append({'name':key.name,'affected_vertices':int((length>1e-6).sum()),'max_delta_m':float(np.linalg.norm(delta,axis=1).max())})
  # Leave new keys disabled during subsequent calibration poses.
  key.value=0
for p in a.pose.bones:p.matrix_basis.identity()
for key,child,sign in created:
 d=key.driver_add('value').driver;d.type='SCRIPTED';d.expression=f'min(1,max(0,{sign}*angle/1.3))'
 v=d.variables.new();v.name='angle';v.type='TRANSFORMS';v.targets[0].id=a;v.targets[0].bone_target=child;v.targets[0].transform_type='ROT_X';v.targets[0].transform_space='LOCAL_SPACE';v.targets[0].rotation_mode='XYZ'
a['controls_enabled']=0.;a.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];sc.frame_set(1);update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_RigV2.blend'))
(O/'QA/correctives.json').write_text(json.dumps(report,indent=2));print('CORRECTIVES_ADDED',len(report))
