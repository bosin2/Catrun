"""Root-only isolated diagnostic fixture, never an ordinary-play approval run."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('s3_d2_visibility_compare', Path(__file__).with_name('d2_visibility_compare.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_COMPARE_PASS', 'D2VisibilityCompare01')).start()
