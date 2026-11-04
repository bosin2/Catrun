"""Task4c focused presentation authoring; run inside the editor, PIE stopped.
Native AI/transform/session ownership is unchanged. Task-local backups are immutable.
"""
import unreal,json,math,hashlib,shutil,datetime
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint as compile_checked
ROOT=Path(unreal.Paths.project_dir()).resolve(); OUT=ROOT/'Saved/Prototype20261104/Task4c';OUT.mkdir(exist_ok=True)
AS=unreal.EditorAssetLibrary;AT=unreal.AssetToolsHelpers.get_asset_tools()
ARM='/Game/Characters/LivingArmor';CAT='/Game/Characters/BlackCat'
ARM_BP=ARM+'/Blueprints/BP_LivingArmor';ARM_ABP=ARM+'/Final/Animations/ABP_ArmorPresentation'
CAT_CLIP=CAT+'/Final/Animations/AN_BlackCat_CaughtHeld';PICKUP_MT=ARM+'/Final/Animations/AM_ArmorPickupPresentation'
CTX=ARM+'/Blueprints/BP_CapturePlayback'
manifest_path=OUT/'manifest.json'
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existing':[],'new':[]}
def write_manifest():manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
def back_up(path):
 if any(x['asset']==path for x in manifest['existing']):return
 asset=AS.load_asset(path);rel='Content/'+path.removeprefix('/Game/')+'.uasset';dest=OUT/'Backups'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
 dirty=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
 row={'asset':path,'file':rel,'before_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'was_dirty':asset.get_outermost().get_name() in dirty}
 if row['was_dirty']:
  assert AS.save_loaded_asset(asset,False);dd=dest.with_suffix('.preexisting-dirty.uasset');shutil.copy2(ROOT/rel,dd);row['dirty_snapshot']=str(dd)
 manifest['existing'].append(row);write_manifest()
def new(path,cls,factory):
 if AS.does_asset_exist(path):
  assert path in manifest['new'], 'Refuse to overwrite unowned asset '+path
  return AS.load_asset(path)
 o=AT.create_asset(path.rsplit('/',1)[1],path.rsplit('/',1)[0],cls,factory);assert o
 manifest['new'].append(path);write_manifest();return o
def strict(bp):
 compile_checked(bp,True);assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
 assert AS.save_loaded_asset(bp,False)
def graph(bp,name='EventGraph'):return BP.get_graph(bp,name)
def ed(g):return unreal.BlueprintGraphEditor.get_graph_editor(g)
def inp(n,p):
 q=n.find_input_pin(p);assert q, (n,p);return q
def outp(n,p):
 q=n.find_output_pin(p);assert q,(n,p);return q
def connect(a,ap,b,bp):assert outp(a,ap).try_create_connection(inp(b,bp)),(a,ap,b,bp)
def value(n,p,v):assert inp(n,p).set_pin_value(str(v)),(n,p,v)
def function(g,name):
 n=ed(g).add_call_function_node(name);assert n,name;return n
def node(g,suffix,cls=None):
 choices=list(dict.fromkeys(str(x) for x in ed(g).list_available_nodes([]) if str(x).endswith('|'+suffix)))
 assert len(choices)==1,(suffix,choices)
 n=BP.create_node(g,choices[0],unreal.IntPoint(0,0),cls);assert n;return n
def get(g,name,cls=''):return ed(g).add_get_member_variable_node(name,cls)
def setv(g,name,cls=''):return ed(g).add_set_member_variable_node(name,cls)
def dump(bp):
 return {'asset':bp.get_path_name(),'status':str(bp.get_editor_property('status')),'graphs':[{ 'name':g.get_name(),'nodes':[{'name':i.node.get_name(),'class':i.node.get_class().get_name(),'type':i.type_id,'input':[{'name':p.name,'value':str(p.value),'links':str(p.connected_pins)} for p in i.input_pins],'output':[{'name':p.name,'links':str(p.connected_pins)} for p in i.output_pins]} for i in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]}
def pose_options(mesh):
 o=unreal.AnimPoseEvaluationOptions();o.evaluation_type=unreal.AnimDataEvalType.SOURCE;o.should_retarget=False;o.extract_root_motion=False;o.incorporate_root_motion_into_pose=False;o.optional_skeletal_mesh=mesh;return o

def foundation():
 assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
 back_up(ARM_BP)
 before=OUT/'armor-before.json'
 if not before.exists():before.write_text(json.dumps(dump(AS.load_asset(ARM_BP)),indent=2),encoding='utf8')
 # Final skeleton held pose. Duplicate preserves face/helper tracks and exact original local P/S.
 if not AS.does_asset_exist(CAT_CLIP):
  seq=AS.duplicate_asset(CAT+'/Final/Animations/AN_BlackCat_Idle',CAT_CLIP);assert seq
  manifest['new'].append(CAT_CLIP);write_manifest()
 else:
  assert CAT_CLIP in manifest['new'],'Refuse to overwrite unowned asset '+CAT_CLIP
 seq=AS.load_asset(CAT_CLIP);source=AS.load_asset(CAT+'/Final/Animations/AN_BlackCat_Idle')
 assert seq.get_editor_property('skeleton')==source.get_editor_property('skeleton')
 model=seq.get_editor_property('data_model_interface');controller=seq.get_editor_property('controller');assert controller
 opts=pose_options(AS.load_asset(CAT+'/Final/Meshes/SK_BlackCat_Final'));N=model.get_number_of_keys();fps=model.get_frame_rate().numerator/model.get_frame_rate().denominator
 # Local X is bend axis on spine/limbs; positions inspected from source pose.
 offsets={'lumbar':(-10,0,0),'spine':(-8,0,0),'chest':(7,0,0),'neck':(8,0,0),'head':(6,0,0),'upperarm_l':(14,0,-6),'upperarm_r':(14,0,6),'forearm_l':(-24,0,0),'forearm_r':(-24,0,0),'paw_f_l':(14,0,0),'paw_f_r':(14,0,0),'thigh_l':(-12,0,-4),'thigh_r':(-12,0,4),'shin_l':(20,0,0),'shin_r':(20,0,0),'hock_l':(-12,0,0),'hock_r':(-12,0,0),'tail_01':(12,0,0),'tail_02':(6,0,0),'tail_03':(4,0,0)}
 data={bone:([],[],[]) for bone in offsets}
 for frame in range(N):
  t=frame/fps;pose=unreal.AnimPoseExtensions.get_anim_pose_at_frame(source,frame,opts)
  # Hands reach the cat around 2.3 seconds; the pose eases through that lift and remains held.
  u=max(0,min(1,(t-1.65)/1.0));alpha=u*u*(3-2*u)
  for bone,(rx,ry,rz) in offsets.items():
   tr=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL)
   sway=math.sin((t-2.65)*2.2)*1.8*alpha if t>2.65 else 0
   if bone.startswith('tail'):rz+=sway*1.6
   elif bone in ('head','neck'):rz+=sway*.45
   elif bone.startswith('paw_f'):rx+=sway
   # Quaternion local postrotation, no actor/root trajectory or rig modification.
   qx=unreal.Quat(math.sin(math.radians(rx*alpha)/2),0,0,math.cos(math.radians(rx*alpha)/2))
   qz=unreal.Quat(0,0,math.sin(math.radians(rz*alpha)/2),math.cos(math.radians(rz*alpha)/2))
   q=tr.rotation*qx*qz;q.normalize()
   data[bone][0].append(tr.translation);data[bone][1].append(q);data[bone][2].append(tr.scale3d)
 controller.open_bracket('Author restrained caught and held pose')
 try:
  for bone,(p,q,s) in data.items():assert controller.set_bone_track_keys(bone,p,q,s),bone
 finally:controller.close_bracket()
 seq.set_editor_property('enable_root_motion',False);assert AS.save_loaded_asset(seq,False)
 (OUT/'cat-authoring.json').write_text(json.dumps({'asset':CAT_CLIP,'skeleton':seq.get_editor_property('skeleton').get_path_name(),'length':seq.get_editor_property('sequence_length'),'keys':N,'fps':fps,'rotation_offsets_degrees':offsets,'preserved':'all local translations/scales, root, facial and unselected tracks','ease_seconds':[1.65,2.65]},indent=2),encoding='utf8')
 # One idle source plus DefaultSlot: no dynamic-pin reconstruction or locomotion state framework.
 fac=unreal.AnimBlueprintFactory();fac.set_editor_property('parent_class',unreal.AnimInstance);fac.set_editor_property('target_skeleton',AS.load_asset(ARM+'/Final/Skeletons/SKEL_LivingArmor_Final'));fac.set_editor_property('preview_skeletal_mesh',AS.load_asset(ARM+'/Final/Meshes/SK_LivingArmor_Final'))
 abp=new(ARM_ABP,unreal.AnimBlueprint,fac);g=graph(abp,'AnimGraph')
 if len(BP.find_nodes(g))==1:
  root=BP.find_nodes(g)[0]
  player=node(g,"'AN_LivingArmor_Idle'재생");slot=node(g,"Slot'DefaultSlot'")
  connect(player,'Pose',slot,'Source');connect(slot,'Pose',root,'Result')
  BP.arrange_nodes(BP.find_nodes(g))
 strict(abp)
 fac=unreal.AnimMontageFactory();fac.set_editor_property('target_skeleton',AS.load_asset(ARM+'/Final/Skeletons/SKEL_LivingArmor_Final'));fac.set_editor_property('source_animation',AS.load_asset(ARM+'/Final/Animations/AN_LivingArmor_Pickup'))
 montage=new(PICKUP_MT,unreal.AnimMontage,fac)
 for field in ['blend_in','blend_out']:
  blend=montage.get_editor_property(field);blend.set_editor_property('blend_time',0.0);montage.set_editor_property(field,blend)
 montage.set_editor_property('enable_auto_blend_out',False)
 # Dedicated montage notifies leave the original sequence untouched.
 unreal.AnimationLibrary.remove_all_animation_notify_tracks(montage)
 unreal.AnimationLibrary.add_animation_notify_track(montage,'Capture')
 for at,name in [(2.3,'CaptureGrab'),(6.85,'CaptureFinished')]:
  notify=unreal.AnimationLibrary.add_animation_notify_event(montage,'Capture',at,unreal.AnimNotify_PlayMontageNotify);notify.set_editor_property('notify_name',name)
 assert AS.save_loaded_asset(montage,False)
 print('TASK4C_FOUNDATION_DONE',CAT_CLIP,ARM_ABP,PICKUP_MT)

if __name__=='__catrun_remote_script__':foundation()


