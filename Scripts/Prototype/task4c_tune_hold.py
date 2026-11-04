import sys,unreal,json
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4c_assets import *
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
p='/Game/Systems/Sound/DA_SoundSettings';back_up(p);a=AS.load_asset(p)
before={k:str(a.get_editor_property(k)) for k in ['CatchHoldOffset','CatchGrabLatestTime','CatchGrabBlendTime','CatchCameraBlendTime','CatchFadeOutTime','CatchBlackHoldTime']}
(OUT/'capture-settings-before.json').write_text(json.dumps(before,indent=2),encoding='utf8')
a.set_editor_property('CatchHoldOffset',unreal.Vector(0,0,15));assert AS.save_loaded_asset(a,False)
print('HOLD_OFFSET_TUNED',before,str(a.get_editor_property('CatchHoldOffset')))
