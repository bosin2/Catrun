"""Cold graph and real GPU verification after the visibility-only repairs."""
import sys
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import verify_interactive,gpu_verify
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
verify_interactive.main()
gpu_verify.OUT=ROOT/'Saved/Stage3GothicRevision20261125/GPU_Visibility2'
gpu_verify.main()
print('GOTHIC_VISIBILITY_QA_PASSED')
