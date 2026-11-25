"""Complete registry audit only. No map or asset writes."""
import importlib.util
import json
import traceback
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
out = root / 'Saved/Stage3ApprovalAudit20261125'
status = {'success': False, 'packages_saved': False}
try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
    spec = importlib.util.spec_from_file_location('approval_asset_scan', root / 'Scripts/Stage3/ApprovalAudit20261125/asset_probe.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.main()
    assert result['success'], result['errors']
    status['success'] = True
except Exception:
    status['error'] = traceback.format_exc()
finally:
    (out / 'asset_probe02_status.json').write_text(json.dumps(status, indent=2), encoding='utf8')
    print('STAGE3_APPROVAL_ASSETS02', status)
    u.SystemLibrary.execute_console_command(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world(), 'QUIT_EDITOR')
