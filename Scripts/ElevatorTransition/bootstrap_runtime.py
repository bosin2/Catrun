import runpy,gc,traceback
from pathlib import Path
import unreal as u
base=Path(u.Paths.project_dir()).resolve()/'Scripts/ElevatorTransition'
try:
    runpy.run_path(str(base/'import_audio.py'),run_name='__main__')
    runpy.run_path(str(base/'polish_cameras.py'),run_name='__main__')
except Exception:
    (base.parents[1]/'Saved/ElevatorTransition/bootstrap_save_error.txt').write_text(traceback.format_exc(),encoding='utf8')
    # Another editor can hold a package read handle. Continue read-only PIE;
    # the coordinator reapplies pending bindings after the other run releases it.
gc.collect()
runpy.run_path(str(base/'verify_runtime.py'),run_name='__main__')
