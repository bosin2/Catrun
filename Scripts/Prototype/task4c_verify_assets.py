import unreal,json
from pathlib import Path
from toolset_registry.helpers import compile_blueprint
paths=['/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor','/Game/Characters/LivingArmor/Blueprints/BP_CapturePlayback','/Game/Characters/LivingArmor/Final/Animations/ABP_ArmorPresentation']
print('RELOAD_DOC',getattr(getattr(unreal.EditorLoadingAndSavingUtils,'reload_packages',None),'__doc__',None))
print('ASSET_DOC',getattr(getattr(unreal.EditorAssetLibrary,'reload_asset',None),'__doc__',None))
for p in paths:
 b=unreal.load_asset(p);compile_blueprint(b,True);assert b.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
b=unreal.load_asset(paths[0]);d=unreal.get_default_object(b.generated_class());m=d.get_editor_property('Mesh');c=d.get_editor_property('CapturePresentation')
print('ARMOR',str(m.get_editor_property('anim_class')),str(m.get_editor_property('animation_mode')),d.get_editor_property('bUseBlueprintAnimation'),c.get_editor_property('bUseBlueprintPresentation'))
