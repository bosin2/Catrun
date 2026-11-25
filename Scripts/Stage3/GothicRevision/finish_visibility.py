"""Coordinated visibility repair, preserving native collision and coordinates."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import occlusion,floor_recess
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
result={'wall_groups':occlusion.apply(),'dock_recess':floor_recess.apply()}
u.CatrunAuthoringLibrary.finish_asset_compilation()
assert le.save_current_level()
(ROOT/'Saved/Stage3GothicRevision20261125/final_visibility.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_VISIBILITY_SAVED')
