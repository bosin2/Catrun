"""Read-only final saved Stage3 checks. Schedule only after writer process exits."""
import importlib.util
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve()
spec = importlib.util.spec_from_file_location('stage3_independent_qa', root / 'Scripts/Stage3/ColorCorrection/verify.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
qa.loaded_materials()
qa.snapshot('after')
qa.compare()
print('STAGE3_FINAL_SNAPSHOT_COMPLETE')
