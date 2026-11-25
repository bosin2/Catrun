"""Root-only reviewed Rugs04 import and Stage3 placement."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import rug_import
result=rug_import.main()
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
placement=rug_import.place(result)
u.CatrunAuthoringLibrary.finish_asset_compilation()
assert le.save_current_level()
placement['map_saved']=True
(ROOT/'Saved/Stage3GothicRevision20261125/rug_placement_report.json').write_text(json.dumps(placement,indent=2),encoding='utf8')
print('GOTHIC_RUG_IMPORTED_PLACED_SAVED')
