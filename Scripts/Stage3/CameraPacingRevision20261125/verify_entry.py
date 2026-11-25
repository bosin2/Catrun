"""Root isolated execution only; verify.py is inert on import."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('s3_pacing_verify', Path(__file__).with_name('verify.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_CAMERA_PACING_PASS','Regression01')).start()
