"""Root-only GPU candidate. Original saved D1/D2 presentation is not modified."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('s3_d2_rotation_entry', Path(__file__).with_name('d2_rotation_candidate.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_ROTATION_PASS', 'D2RotationCandidate01')).start()
