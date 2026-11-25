import bpy,json,hashlib,math
from mathutils import Matrix
from pathlib import Path
HERE=Path(__file__).parent;OUT=HERE/'FBX';OUT.mkdir(exist_ok=True)
sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE')
names=['AN_CompactPortal_SeatedListenTouch','AN_CompactPortal_HipsBackWiggle','AN_CompactPortal_SeatedTakeoff','AN_CompactPortal_AirReach','AN_CompactPortal_WalkReview']
meshes=[o for o in sc.objects if o.type=='MESH' and not o.hide_render]
contract={'unit_system':sc.unit_settings.system,'scale_length':sc.unit_settings.scale_length,'armature':a.name,'armature_scale':list(a.scale),'bones':len(a.data.bones),'bind':{b.name:{'parent':b.parent.name if b.parent else None,'use_connect':b.use_connect,'matrix':[list(r) for r in b.matrix_local]} for b in a.data.bones},'meshes':{o.name:{'vertices':len(o.data.vertices),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons)} for o in meshes},'clips':[]}
opts=dict(use_selection=True,global_scale=1.,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',use_space_transform=True,bake_space_transform=False,add_leaf_bones=False,use_armature_deform_only=False,armature_nodetype='NULL',bake_anim_use_all_bones=True,bake_anim_use_nla_strips=False,bake_anim_use_all_actions=False,bake_anim_force_startend_keying=True,bake_anim_step=1.,bake_anim_simplify_factor=0.,path_mode='AUTO',mesh_smooth_type='FACE',use_triangles=True)
bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a
from io_scene_fbx import export_fbx_bin,fbx_utils
original_writer=export_fbx_bin.fbx_data_object_elements
def rest_model_writer(root,ob,scene_data):
 original_tx=fbx_utils.ObjectWrapper.fbx_object_tx
 if ob.is_bone:
  def rest_tx(self,sd,rest=False,rot_euler_compat=None):return original_tx(self,sd,rest=True,rot_euler_compat=rot_euler_compat)
  fbx_utils.ObjectWrapper.fbx_object_tx=rest_tx
 try:return original_writer(root,ob,scene_data)
 finally:fbx_utils.ObjectWrapper.fbx_object_tx=original_tx
export_fbx_bin.fbx_data_object_elements=rest_model_writer
samples={}
for name in names:
 act=bpy.data.actions[name];a.animation_data.action=act;sc.frame_start=int(act.frame_range[0]);sc.frame_end=int(act.frame_range[1]);sc.frame_set(sc.frame_start);a.location=(0,0,0)
 samples[name]=[]
 for f in range(sc.frame_start,sc.frame_end+1):
  sc.frame_set(f);bpy.context.view_layer.update();samples[name].append({p.name:p.matrix.copy() for p in a.pose.bones})
 sc.frame_set(sc.frame_start)
 path=OUT/(name+'.fbx');bpy.ops.export_scene.fbx(filepath=str(path),object_types={'ARMATURE'},bake_anim=True,**opts)
 contract['clips'].append({'action':name,'fbx':str(path.resolve()),'start':sc.frame_start,'end':sc.frame_end,'fps':30,'duration_seconds':(sc.frame_end-sc.frame_start)/30,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
a.animation_data.action=None
export_fbx_bin.fbx_data_object_elements=original_writer
for p in a.pose.bones:p.matrix_basis.identity()
a.location=(0,0,0);bpy.context.view_layer.update()
contract['rest_dimensions']={o.name:list(o.dimensions) for o in meshes}
for o in meshes:o.select_set(True)
meshpath=OUT/'SK_BlackCat_CompactPortal.fbx'
bpy.ops.export_scene.fbx(filepath=str(meshpath),object_types={'ARMATURE','MESH'},bake_anim=False,**opts)
contract['mesh_fbx']=str(meshpath.resolve());contract['export_axes']={'forward':'-Y','up':'Z'}
(HERE/'QA'/'export_contract.json').write_text(json.dumps(contract,indent=2),encoding='utf8')
# Fresh-scene re-import: the animation-only clips must preserve all support
# bones and bind sizes as well as the expected duration.
checks=[]
for path in [meshpath]+[Path(c['fbx']) for c in contract['clips']]:
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=30;bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True,automatic_bone_orientation=False,anim_offset=0.)
 rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];r=rigs[0]
 bone_errors=[];maxbind=0.;bindpos=0.;bindrot=0.;bindscale=0.
 for n,v in contract['bind'].items():
  if n not in r.data.bones:bone_errors.append({'missing':n});continue
  b=r.data.bones[n];err=max(abs(b.matrix_local[i][j]-v['matrix'][i][j]) for i in range(4) for j in range(4))
  maxbind=max(maxbind,err)
  ref=Matrix(v['matrix']);pos=(b.matrix_local.translation-ref.translation).length;ang=math.degrees(b.matrix_local.to_quaternion().rotation_difference(ref.to_quaternion()).angle);ang=min(ang,abs(360-ang));se=max(abs(x-y) for x,y in zip(b.matrix_local.to_scale(),ref.to_scale()));bindpos=max(bindpos,pos);bindrot=max(bindrot,ang);bindscale=max(bindscale,se)
  if pos>1e-5 or ang>.01 or se>1e-4:bone_errors.append({'bone':n,'position_m':pos,'rotation_degrees':ang,'scale_error':se})
 dims={o.name:list(o.dimensions) for o in bpy.context.scene.objects if o.type=='MESH'}
 acts=[{'name':x.name,'range':list(x.frame_range)} for x in bpy.data.actions]
 posecheck=None
 if path.stem in samples:
  bpy.context.view_layer.objects.active=r;r.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
  for n,v in contract['bind'].items():r.data.edit_bones[n].use_connect=v['use_connect']
  bpy.ops.object.mode_set(mode='OBJECT');poserr=0.;roterr=0.;scaleerr=0.
  for i,expected in enumerate(samples[path.stem]):
   bpy.context.scene.frame_set(i+1);bpy.context.view_layer.update()
   for n,ref in expected.items():
    actual=r.pose.bones[n].matrix;poserr=max(poserr,(actual.translation-ref.translation).length);ang=math.degrees(actual.to_quaternion().rotation_difference(ref.to_quaternion()).angle);roterr=max(roterr,min(ang,abs(360-ang)));scaleerr=max(scaleerr,max(abs(x-y) for x,y in zip(actual.to_scale(),ref.to_scale())))
  posecheck={'max_position_error_m':poserr,'max_rotation_error_degrees':roterr,'max_scale_error':scaleerr,'sampled_frames':len(samples[path.stem]),'pass':poserr<1e-5 and roterr<.01 and scaleerr<1e-4}
 checks.append({'file':str(path),'bones':len(r.data.bones),'armature_scale':list(r.scale),'max_bind_matrix_difference':maxbind,'bind_position_error_m':bindpos,'bind_rotation_error_degrees':bindrot,'bind_scale_error':bindscale,'bind_errors':bone_errors,'mesh_dimensions':dims,'actions':acts,'pose_roundtrip':posecheck})
(HERE/'QA'/'fbx_roundtrip.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
print('FBX_REVISION_EXPORTED',len(checks),'files',flush=True)

