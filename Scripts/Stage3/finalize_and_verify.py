import runpy
from pathlib import Path
import unreal as u
root=Path(u.Paths.project_dir()).resolve()/'Scripts/Stage3'
for name in ['finalize_map.py','verify_map.py','capture_map.py']:
 runpy.run_path(str(root/name),run_name='__main__')
