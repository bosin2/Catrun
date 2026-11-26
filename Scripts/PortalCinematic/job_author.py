"""One NullRHI commandlet: retime the arrival BP, then rebuild both portal sequences. Markers: PORTALCINE_*."""
import sys
import traceback
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
results = {}
for n in ('author_bp.py', 'author_stage1.py', 'author_stage2.py'):
    try:
        ns = {'__name__': 'job_' + n[:-3], '__file__': str(HERE / n)}
        exec(compile((HERE / n).read_text(encoding='utf-8'), str(HERE / n), 'exec'), ns)
        results[n] = 'ok'
    except Exception:
        results[n] = 'fail'
        print('PORTALCINE_JOB_ERROR', n, traceback.format_exc()[-2500:])
        dirty = [p.get_path_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                             *u.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
        print('PORTALCINE_DIRTY_AFTER_FAIL', dirty)
        break
print('PORTALCINE_JOB_DONE', results)
