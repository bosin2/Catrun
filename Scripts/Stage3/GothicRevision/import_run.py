import sys
from pathlib import Path
import unreal as u
root=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(root/'Scripts/Stage3/GothicRevision'))
import import_mechanisms
report=import_mechanisms.main()
print('GOTHIC_IMPORT_OK',report['mesh_count'])
