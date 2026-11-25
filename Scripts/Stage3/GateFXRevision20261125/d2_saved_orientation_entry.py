"""Root isolated GPU launcher: observes saved card rotations, never applies them."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('s3_saved_orientation_entry', Path(__file__).with_name('d2_saved_orientation.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_SAVED_PASS', 'D2SavedOrientation01')).start()
