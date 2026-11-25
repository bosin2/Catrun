"""Save only the Stage3 camera instance correction."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import camera
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
result=camera.apply()
assert le.save_current_level()
(ROOT/'Saved/Stage3GothicRevision20261125/camera_report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_CAMERA_SAVED')
