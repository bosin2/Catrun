"""Root entry: preserve evidence and quit the disposable editor even on failure."""
import importlib.util
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
try:
    spec = importlib.util.spec_from_file_location('stage3_gate_pillar_gpu', root / 'Scripts/Stage3/GateHallRevision20261125/gpu_occlusion.py')
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    qa.main()
finally:
    u.SystemLibrary.execute_console_command(ed.get_editor_world(), 'QUIT_EDITOR')
