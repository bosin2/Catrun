"""Only run this in the separate revision-3 candidate project."""
import runpy
from pathlib import Path
import unreal as u

root=Path(u.Paths.project_dir()).resolve()
assert 'ElevatorRevision3_20261125_01a21074' in str(root), 'Use the isolated candidate project'
base=root/'Scripts/ElevatorTransition'
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage2')
runpy.run_path(str(base/'probe_peek_pose.py'),run_name='__main__')
runpy.run_path(str(base/'refine_departure_shots.py'),run_name='__main__')
runpy.run_path(str(base/'verify_runtime.py'),run_name='__main__')
