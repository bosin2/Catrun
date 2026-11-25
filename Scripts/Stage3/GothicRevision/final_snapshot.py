"""Read-only cold reload and final invariant comparison."""
import sys,json,os
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import verify
pass_name=os.environ.get('CATRUN_GOTHIC_QA_PASS')
if pass_name:
    assert pass_name.replace('_','').isalnum()
    verify.OUT=ROOT/'Saved/Stage3GothicRevision20261125/QA'/pass_name
    baseline=verify.OUT/'before/snapshot.json'
    baseline.parent.mkdir(parents=True,exist_ok=True)
    assert not baseline.exists()
    baseline.write_bytes((ROOT/'Saved/Stage3GothicRevision20261125/QA/before/snapshot.json').read_bytes())
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
verify.snapshot('after')
result=verify.compare()
print('GOTHIC_FINAL_INVARIANTS',json.dumps(result,ensure_ascii=False))
import verify_interactive
verify_interactive.main()
