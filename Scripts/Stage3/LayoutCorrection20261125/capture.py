"""Actual possessed-camera evidence for the corrected saved map; disposable PIE."""
import importlib.util
import os
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
os.environ['CATRUN_GOTHIC_CAPTURE'] = 'after'
os.environ.pop('CATRUN_GOTHIC_VIEWS', None)
os.environ.pop('CATRUN_GOTHIC_DIAGNOSTIC', None)
spec = importlib.util.spec_from_file_location('layout_camera_capture', ROOT / 'Scripts/Stage3/GothicRevision/capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
capture.OUT = ROOT / 'Saved/Stage3LayoutCorrection20261125/Visual'
capture.OUT.mkdir(parents=True, exist_ok=True)
assert not (capture.OUT / 'report.json').exists(), 'Preserve prior camera evidence'
capture.MODES = ['Lit']
capture.VIEWS = [
    ('LobbyRightGap', (625, 600, 26.2)),
    ('ExhibitionBridge', (-475, 1425, 26.2)),
    ('Exhibition', (-800, 1880, 26.2)),
    ('AltarLeftElbow', (-250, 2025, 26.2)),
    ('UpperCorridor', (-250, 2600, 26.2)),
    ('GateHall', (-250, 3400, 26.2)),
]
