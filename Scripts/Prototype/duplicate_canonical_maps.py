"""Only duplicate/save missing worlds; never LoadLevel in this remote call.

Run with ue_remote.py --isolated. Root must first back up and vacate canonical
destinations with the editor stopped. Existing saved destinations resume safely.
"""
import unreal,json
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def duplicate_one(stage):
    destination=root/('Content/Maps/'+stage+'.umap')
    if destination.exists():return {'stage':stage,'resumed_saved_destination':True}
    source=unreal.load_asset('/Game/Maps/SoundTest_'+stage)
    assert source,stage
    duplicate=unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(stage,'/Game/Maps',source)
    assert duplicate,stage
    assert unreal.EditorAssetLibrary.save_loaded_asset(duplicate,False)
    return {'stage':stage,'saved':True,'size':destination.stat().st_size}
result=[duplicate_one(stage) for stage in ['Tutorial','Stage1','Stage2']]
(root/'Saved/Prototype20261104/CanonicalMaps/duplication.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('CANONICAL_DUPLICATES_SAVED',json.dumps(result))
