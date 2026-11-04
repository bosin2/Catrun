import unreal
from pathlib import Path
p=Path(unreal.Paths.project_dir())/'Scripts/Prototype/verify_task4d_routes.py'
exec(compile(p.read_text(encoding='utf8'),str(p),'exec'),{'TASK4D_MAP':'SoundTest_Stage2','__name__':'__catrun_remote_script__'})
