"""Apply the user's new concept-image lighting to Stage3 only."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import reference_lighting,camera
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
result=reference_lighting.apply()
result['camera']=camera.apply()
assert le.save_current_level()
result['map_saved']=True
(ROOT/'Saved/Stage3GothicRevision20261125/reference_lighting.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_REFERENCE_LIGHTING_SAVED')
