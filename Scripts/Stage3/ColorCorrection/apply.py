"""Root-coordinated Stage3 materials then lighting; save map only on success."""
import json
import sys
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(root / 'Scripts/Stage3/ColorCorrection'))
import materials
import lighting

assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
result = {'materials': materials.main(save_map=False)}
result['lighting'] = lighting.apply(allow_write=True, save=False)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
result['map_saved'] = True
out = root / 'Saved/Stage3MaterialCorrection20261125/application.json'
out.write_text(json.dumps(result, indent=2), encoding='utf8')
print('STAGE3_COLOR_CORRECTION_SAVED')
