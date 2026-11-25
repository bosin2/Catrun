"""Read-only saved-map QA entrypoint for a separate editor commandlet."""
import importlib.util,os
from pathlib import Path
import unreal as u
root=Path(u.Paths.project_dir()).resolve()
phase=os.environ.get('CATRUN_STAGE3_QA_PHASE','before')
assert phase in ('before','after')
spec=importlib.util.spec_from_file_location('stage3_color_qa',root/'Scripts/Stage3/ColorCorrection/verify.py')
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
qa.snapshot(phase)
if phase == 'after':
    result = qa.loaded_materials()
    assert result['success'], 'Saved material graph or slot verification failed'
print('STAGE3_COLOR_QA_SNAPSHOT_OK',phase)
