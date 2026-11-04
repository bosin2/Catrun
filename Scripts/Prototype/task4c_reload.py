import unreal,json
from pathlib import Path
from toolset_registry.helpers import compile_blueprint
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
paths=['/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor','/Game/Characters/LivingArmor/Blueprints/BP_CapturePlayback','/Game/Characters/LivingArmor/Final/Animations/ABP_ArmorPresentation','/Game/Characters/LivingArmor/Final/Animations/AM_ArmorPickupPresentation','/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_CaughtHeld','/Game/Systems/Sound/DA_SoundSettings']
for p in paths:assert unreal.EditorAssetLibrary.save_loaded_asset(unreal.load_asset(p),False)
packages=[unreal.load_asset(p).get_outermost() for p in paths]
result=unreal.EditorLoadingAndSavingUtils.reload_packages(packages,unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
print('RELOAD',result)
assert result[0],result
statuses={}
for p in paths[:3]:
 b=unreal.load_asset(p);compile_blueprint(b,True);assert b.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
 statuses[p]=str(b.get_editor_property('status'));assert unreal.EditorAssetLibrary.save_loaded_asset(b,False)
 print('RELOADED_STRICT',p,str(b.get_editor_property('status')))
(Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/reload-result.json').write_text(json.dumps({'reload':str(result),'warnings_as_errors':True,'statuses':statuses,'packages':paths},indent=2),encoding='utf8')
