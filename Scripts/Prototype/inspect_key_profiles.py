import unreal,json
from pathlib import Path
result={}
for p in ['/Game/Input/Contexts/IMC_Default','/Game/Input/Contexts/IMC_CatInteraction']:
    asset=unreal.load_asset(p)
    result[p]={'default_key_mappings':asset.get_editor_property('default_key_mappings').export_text(),'mapping_profile_overrides':str(asset.get_editor_property('mapping_profile_overrides'))}
(Path(unreal.Paths.project_saved_dir())/'Prototype20261104/CanonicalMaps/key-profiles.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result));print(unreal.EnhancedInputLocalPlayerSubsystem.inject_input_vector_for_action.__doc__)
