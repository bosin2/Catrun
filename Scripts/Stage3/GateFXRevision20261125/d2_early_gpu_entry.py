"""Root-only isolated GPU launcher; d2_early_gpu module itself is inert."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('stage3_d2_early_gpu', Path(__file__).with_name('d2_early_gpu.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_D2_PASS', 'D2EarlyGPU03')).start()
