"""Repeatable Task4d authoring entrypoint, current dirty-checkout ownership required.
Run via ue_remote.py --isolated, no PIE, exclusive editor/asset writer lease.
Finished graphs are checked/reused, never cleared or reconstructed on a rerun.
"""
import unreal,sys
from pathlib import Path
root=Path(unreal.Paths.project_dir());sys.path.insert(0,str(root/'Scripts/Prototype'))
import task4d_assets as T
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
snapshot=T.OUT/'presentation-after.json'
if snapshot.exists():
 steps=['task4d_verify_saved.py']
else:
 steps=['task4d_foundation.py','task4d_materials.py','task4d_graphs.py','task4d_camera_blur.py','task4d_maps.py','task4d_verify_saved.py']
for name in steps:
 p=root/'Scripts/Prototype'/name;exec(compile(p.read_text(encoding='utf8'),str(p),'exec'),{'__name__':'__catrun_remote_script__'})
print('TASK4D_SETUP_VERIFIED')
