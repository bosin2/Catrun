"""Root launch entry; importing reset_replay.py alone remains inert."""
import importlib.util
import os
from pathlib import Path

path = Path(__file__).resolve().with_name('reset_replay.py')
spec = importlib.util.spec_from_file_location('stage3_gate_reset_replay', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_RESET_PASS', 'ResetReplay01'),
                        capture=os.environ.get('CATRUN_GATE_FX_RESET_CAPTURE', '1') == '1').start()
