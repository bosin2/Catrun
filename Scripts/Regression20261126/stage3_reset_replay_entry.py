"""reset_replay.py 를 원본 그대로 읽어, 복귀 2.6초(이전 0.6초)에 맞게 정착 대기만 1.1 -> 3.4초로 바꿔 실행한다."""
import os
import types
from pathlib import Path

import unreal as u

path = Path(u.Paths.project_dir()) / 'Scripts/Stage3/GateFXRevision20261125/reset_replay.py'
src = path.read_text(encoding='utf-8')
assert src.count('if elapsed < 1.1:') == 1
src = src.replace('if elapsed < 1.1:', 'if elapsed < 3.4:')
module = types.ModuleType('stage3_gate_reset_replay')
module.__file__ = str(path)
exec(compile(src, str(path), 'exec'), module.__dict__)
HARNESS = module.Harness(os.environ.get('CATRUN_GATE_FX_RESET_PASS', 'ResetReplay01'),
                         capture=os.environ.get('CATRUN_GATE_FX_RESET_CAPTURE', '1') == '1').start()
