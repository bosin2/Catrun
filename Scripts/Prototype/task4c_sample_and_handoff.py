import sys,unreal,math,json
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
result={'armor':{},'cat':{},'unchanged_cat_tracks':True}
for folder,meshpath,bones in [(ARM+'/Final/Animations',ARM+'/Final/Meshes/SK_LivingArmor_Final',['root','pelvis','chest','hand_l','hand_r']),(CAT+'/Final/Animations',CAT+'/Final/Meshes/SK_BlackCat_Final',['root','pelvis','chest','head','paw_f_l','paw_h_l','tail_07'])]:
 mesh=AS.load_asset(meshpath);opts=pose_options(mesh)
 for path in AS.list_assets(folder,False,False):
  seq=AS.load_asset(path)
  if not isinstance(seq,unreal.AnimSequence):continue
  if folder.startswith(CAT) and seq.get_name() not in ['AN_BlackCat_Idle','AN_BlackCat_CaughtHeld','AN_BlackCat_BasketEnter']:continue
  length=seq.get_editor_property('sequence_length');samples=[]
  for i in range(math.ceil(length*10)+1):
   t=min(length,i/10);pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(seq,t,opts)
   samples.append({'time':t,'bones':{bone:{'translation':[tr.translation.x,tr.translation.y,tr.translation.z],'rotation':[tr.rotation.x,tr.rotation.y,tr.rotation.z,tr.rotation.w]} for bone in bones for tr in [unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)]}})
  result['armor' if folder.startswith(ARM) else 'cat'][seq.get_path_name()]={'length':length,'skeleton':seq.get_editor_property('skeleton').get_path_name(),'root_motion':seq.get_editor_property('enable_root_motion'),'samples':samples}
# Verify every untouched local track at every authored key, including original root/face.
source=AS.load_asset(CAT+'/Final/Animations/AN_BlackCat_Idle');target=AS.load_asset(CAT_CLIP);model=source.get_editor_property('data_model_interface');changed=set(json.loads((OUT/'cat-authoring.json').read_text())['rotation_offsets_degrees']);opts=pose_options(AS.load_asset(CAT+'/Final/Meshes/SK_BlackCat_Final'));maxdiff=0
for i in range(model.get_number_of_keys()):
 a=unreal.AnimPoseExtensions.get_anim_pose_at_frame(source,i,opts);b=unreal.AnimPoseExtensions.get_anim_pose_at_frame(target,i,opts)
 for name in model.get_bone_track_names():
  ta=unreal.AnimPoseExtensions.get_bone_pose(a,name,unreal.AnimPoseSpaces.LOCAL);tb=unreal.AnimPoseExtensions.get_bone_pose(b,name,unreal.AnimPoseSpaces.LOCAL)
  assert max(abs(getattr(ta.translation,k)-getattr(tb.translation,k)) for k in ['x','y','z'])<.00001 and max(abs(getattr(ta.scale3d,k)-getattr(tb.scale3d,k)) for k in ['x','y','z'])<.00001,str(name)
  if str(name) not in changed:assert max(abs(getattr(ta.rotation,k)-getattr(tb.rotation,k)) for k in ['x','y','z','w'])<.00001,str(name)
result['preservation']={'all_keys':model.get_number_of_keys(),'all_local_translations_scales':True,'untouched_rotations_including_root_face':True,'changed_tracks':len(changed)}
(OUT/'full-clip-samples.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('FULL_CLIPS_SAMPLED',len(result['armor']),len(result['cat']),result['preservation'])
# Only intended task packages are saved; maps and original cat ABP/intro are not touched.
for path in manifest['new']+[x['asset'] for x in manifest['existing']]:assert AS.save_loaded_asset(AS.load_asset(path),False)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/MainMenu')
dirty=[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
(OUT/'prebuild-handoff.json').write_text(json.dumps({'world':unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name(),'no_pie':not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'dirty':dirty},indent=2),encoding='utf8')
print('PREBUILD_HANDOFF',dirty)
