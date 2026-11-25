"""Native Unreal screenshot, unchanged pixels, from the visible corrected overview."""
from pathlib import Path
import unreal as u
OUT=Path(u.Paths.project_dir()).resolve()/'Saved/Stage3OrientationFix20261125'
assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
print(u.AutomationLibrary.take_high_res_screenshot.__doc__)
task=u.AutomationLibrary.take_high_res_screenshot(1280,1064,str(OUT/'overview.png'))
print('EDITOR_SCREENSHOT_REQUESTED',str(task))
