"""Approval preparation only: inspect saved Stage3 without saving any package."""
import importlib.util
import json
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3ApprovalAudit20261125'
OUT.mkdir(parents=True, exist_ok=True)

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

result = {'success': False, 'packages_saved': False}
try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
    qa = module('approval_snapshot', 'Scripts/Stage3/GothicRevision/verify.py')
    qa.OUT = OUT / 'QA'
    qa.snapshot('before')
    module('approval_assets', 'Scripts/Stage3/ApprovalAudit20261125/asset_probe.py').main()
    result['success'] = True
except Exception:
    result['error'] = traceback.format_exc()
finally:
    (OUT / 'probe_status.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print('STAGE3_APPROVAL_PROBE', result)
    u.SystemLibrary.execute_console_command(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world(), 'QUIT_EDITOR')
