"""Coordinated writer entry point; root alone schedules this commandlet."""
import sys
from pathlib import Path
import unreal as u

root=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(root/'Scripts/Stage3/ColorCorrection'))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
import materials
materials.main(save_map=True)
