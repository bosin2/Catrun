"""Read-only before/after screenshots from the actual Stage3 player camera."""
import importlib.util
import os
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PHASE = os.environ.get('CATRUN_STAGE3_FIX_PHASE', 'before')
assert PHASE in ('before', 'after')
RUN = ROOT / 'Saved/Stage3ReadabilityPushFix20261125'
assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

qa = module('stage3_fix_snapshot', 'Scripts/Stage3/GothicRevision/verify.py')
qa.OUT = RUN / 'QA'
if not (qa.OUT / PHASE / 'snapshot.json').exists():
    qa.snapshot(PHASE)
if PHASE == 'after' and os.environ.get('CATRUN_STAGE3_FIX_GPU', '1') == '1':
    os.environ.pop('CATRUN_STAGE3_GPU_QUIT_EDITOR', None)
    try:
        module('stage3_fix_gpu', 'Scripts/Stage3/ReadabilityPushFix20261125/gpu_occlusion.py').main()
    except Exception:
        u.SystemLibrary.execute_console_command(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world(), 'QUIT_EDITOR')
        raise
os.environ['CATRUN_GOTHIC_CAPTURE'] = PHASE
os.environ['CATRUN_GOTHIC_LIT_ONLY'] = '1'
os.environ.pop('CATRUN_GOTHIC_VIEWS', None)
os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC', None)
c = module('stage3_fix_capture', 'Scripts/Stage3/GothicRevision/capture.py')
c.OUT = RUN / PHASE
c.OUT.mkdir(parents=True, exist_ok=True)
c.VIEWS = [('Entrance', (150, -110, 26.2)),
           ('Weight1Approach', (-500, -1425, 26.2)),
           ('Weight2Approach', (760, -2055, 26.2)),
           ('GateHall', (-250, -3400, 26.2))]
