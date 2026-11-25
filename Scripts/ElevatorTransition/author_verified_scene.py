import os,runpy,gc
from pathlib import Path
import unreal as u
base=Path(u.Paths.project_dir()).resolve()/'Scripts/ElevatorTransition'
os.environ['CATRUN_ELEVATOR_COLD_AUDIT']='1'
runpy.run_path(str(base/'import_assets.py'),run_name='__main__')
gc.collect()
runpy.run_path(str(base/'author_scene.py'),run_name='__main__')
