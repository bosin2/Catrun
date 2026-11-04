"""Assign the existing wake camera on the other consumer of BP_TutorialIntro.
Run only after the controller releases the editor and PIE has stopped.
"""
import unreal,json,hashlib,shutil,datetime
from pathlib import Path
legacy_root=Path(unreal.Paths.project_dir()).resolve()
legacy_out=legacy_root/'Saved/Prototype20261104'
legacy_backup=legacy_out/'IntroFixBackups'
legacy_levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
legacy_editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not legacy_editor.get_game_world(),'Wait for main to release editor and stop PIE'
legacy_bp=unreal.load_asset('/Game/Blueprints/BP_TutorialIntro')
assert legacy_bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE,str(legacy_bp.get_editor_property('status'))
legacy_rel='Content/Maps/Tutorial.umap'
legacy_target=legacy_backup/legacy_rel
legacy_manifest_path=legacy_backup/'manifest.json'
legacy_manifest=json.loads(legacy_manifest_path.read_text(encoding='utf8'))
assert not any(e['relative_path']==legacy_rel for e in legacy_manifest['assets']),'Legacy consumer assignment already backed up; inspect current result before rerun'
legacy_target.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(legacy_root/legacy_rel,legacy_target)
assert legacy_levels.load_level('/Game/Maps/Tutorial')
legacy_world=legacy_editor.get_editor_world()
legacy_dirty=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
legacy_entry={'relative_path':legacy_rel,'package':'/Game/Maps/Tutorial','was_dirty':'/Game/Maps/Tutorial' in legacy_dirty,'disk_before_sha256':hashlib.sha256(legacy_target.read_bytes()).hexdigest(),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reason':'Existing consumer of shared BP_TutorialIntro needs existing WakeCamera reference'}
if legacy_entry['was_dirty']:
    assert legacy_levels.save_current_level()
    legacy_dirty_target=legacy_target.with_name(legacy_target.stem+'.preexisting-dirty'+legacy_target.suffix)
    shutil.copy2(legacy_root/legacy_rel,legacy_dirty_target)
    legacy_entry['preexisting_dirty_snapshot']=str(legacy_dirty_target)
legacy_manifest['assets'].append(legacy_entry)
legacy_manifest_path.write_text(json.dumps(legacy_manifest,indent=2),encoding='utf8')
legacy_actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
legacy_intro=next(a for a in legacy_actors if a.get_class().get_name()=='BP_TutorialIntro_C')
legacy_wake=next(a for a in legacy_actors if a.get_actor_label()=='CINE_Tutorial_MainMenuCatWakeUp')
legacy_before={a.get_path_name():{'class':a.get_class().get_name(),'label':a.get_actor_label(),'transform':a.get_actor_transform().export_text()} for a in legacy_actors}
legacy_previous=legacy_intro.get_editor_property('WakeCamera')
legacy_intro.set_editor_property('WakeCamera',legacy_wake)
assert legacy_intro.get_editor_property('WakeCamera')==legacy_wake
legacy_after={a.get_path_name():{'class':a.get_class().get_name(),'label':a.get_actor_label(),'transform':a.get_actor_transform().export_text()} for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
assert legacy_before==legacy_after,'Unexpected actor/transform change'
assert legacy_levels.save_current_level()
assert legacy_levels.load_level('/Game/Maps/MainMenu')
assert legacy_levels.load_level('/Game/Maps/Tutorial')
legacy_reloaded_actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
legacy_reloaded_intro=next(a for a in legacy_reloaded_actors if a.get_class().get_name()=='BP_TutorialIntro_C')
legacy_reloaded_wake=next(a for a in legacy_reloaded_actors if a.get_actor_label()=='CINE_Tutorial_MainMenuCatWakeUp')
assert legacy_reloaded_intro.get_editor_property('WakeCamera')==legacy_reloaded_wake
legacy_result={'status':'saved_and_reloaded','map':'/Game/Maps/Tutorial','previous_wake_camera':legacy_previous.get_path_name() if legacy_previous else None,'wake_camera':legacy_reloaded_wake.get_path_name(),'intro':legacy_reloaded_intro.get_path_name(),'actor_count':len(legacy_before),'actor_names_classes_labels_transforms_unchanged':legacy_before==legacy_after,'blueprint_status':str(legacy_bp.get_editor_property('status')),'before_sha256':legacy_entry['disk_before_sha256'],'after_sha256':hashlib.sha256((legacy_root/legacy_rel).read_bytes()).hexdigest(),'backup_manifest':str(legacy_manifest_path)}
assert legacy_levels.load_level('/Game/Maps/MainMenu')
legacy_result['editor_world']=legacy_editor.get_editor_world().get_path_name()
legacy_result['pie_active']=bool(legacy_editor.get_game_world())
(legacy_out/'intro-legacy-consumer-verification.json').write_text(json.dumps(legacy_result,indent=2),encoding='utf8')
print('LEGACY_TUTORIAL_INTRO_CAMERA_ASSIGNED',json.dumps(legacy_result))
