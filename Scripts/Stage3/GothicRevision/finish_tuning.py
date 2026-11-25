"""Selective final light tuning and cosmetic Blueprint comment repair."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import tune_lights,fix_comments
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
result={'comments':fix_comments.fix(save=True),'lighting':tune_lights.apply()}
assert le.save_current_level()
result['lighting']['map_saved']=True
(ROOT/'Saved/Stage3GothicRevision20261125/final_tuning.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_TUNING_SAVED')
