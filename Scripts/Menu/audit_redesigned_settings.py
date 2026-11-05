"""Fresh root-owned commandlet entrypoint; does not save any package."""
from pathlib import Path
import sys
import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'Scripts/Menu'))
from redesign_settings import reload_audit

reload_audit()
