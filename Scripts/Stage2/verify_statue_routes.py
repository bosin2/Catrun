"""Current Stage2 statue route check entrypoint.

The old editor-world positive gate_rise>270 and inferred-axis assertions are
retired. Saved/Stage2 evidence remains historical, not current proof.
Run via Scripts/Prototype/ue_remote.py --isolated with foreground PIE stopped.
The replacement is an API-driven native motion/collision test; physical input
is verified separately by the integration controller.
"""
from pathlib import Path
import unreal
path=Path(unreal.Paths.project_dir())/'Scripts/Prototype/verify_task4d_routes.py'
exec(compile(path.read_text(encoding='utf8'),str(path),'exec'),{'__name__':'__catrun_remote_script__'})
