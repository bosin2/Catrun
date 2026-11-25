"""Seven actual possessed-camera views of the integrated Stage3 revision.

Visual pose fixture only. NPCs freeze after initialization; no package saves.
The separate runtime suites prove travel and native enemy behavior.
"""
import importlib.util
import os
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_STAGE3_AFTER_CAPTURE_PASS', 'After01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3IntegrationRevision20261125' / PASS
assert not (OUT / 'report.json').exists(), 'Preserve previous capture evidence'
os.environ['CATRUN_GOTHIC_CAPTURE'] = 'after'
os.environ['CATRUN_GOTHIC_LIT_ONLY'] = '1'
os.environ.pop('CATRUN_GOTHIC_VIEWS', None)
os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC', None)
spec = importlib.util.spec_from_file_location('s3_integrated_capture', ROOT / 'Scripts/Stage3/GothicRevision/capture.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.OUT = OUT
c.OUT.mkdir(parents=True, exist_ok=True)
c.VIEWS = [
    ('GateMiddle', (-250, -3400, 26.2)),
    ('GateExtended', (-870, -4420, 26.2)),
    ('GateExtreme', (-945, -4545, 26.2)),
    ('Altar', (375, -2025, 26.2)),
    ('Exhibition', (-780, -1980, 26.2)),
    ('Warehouse', (605, -1215, 26.2)),
    ('Lobby', (50, -360, 26.2)),
]
