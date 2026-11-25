import runpy
from pathlib import Path
import unreal as u
base=Path(u.Paths.project_dir()).resolve()/'Scripts/ElevatorTransition'
runpy.run_path(str(base/'polish_cameras.py'),run_name='__main__')
runpy.run_path(str(base/'import_audio.py'),run_name='__main__')
