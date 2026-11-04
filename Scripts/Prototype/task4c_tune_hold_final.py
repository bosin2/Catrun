import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import back_up
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
back_up('/Game/Systems/Sound/DA_SoundSettings')
a=unreal.load_asset('/Game/Systems/Sound/DA_SoundSettings');a.set_editor_property('CatchHoldOffset',unreal.Vector(8,0,15));assert unreal.EditorAssetLibrary.save_loaded_asset(a,False)
print('HOLD_FORWARD',a.get_editor_property('CatchHoldOffset'))
