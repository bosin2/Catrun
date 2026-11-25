import runpy
from pathlib import Path
import unreal as u
base=Path(u.Paths.project_dir()).resolve()/'Scripts/ElevatorTransition'
# Keep sequence authoring separate from map GC. An already verified clip is reused.
assert u.EditorAssetLibrary.does_asset_exist('/Game/Cinematics/ElevatorTransition/Animations/AN_BlackCat_Elevator_ArrivalLookAround'), 'Run author_arrival_look.py in a separate commandlet first'
runpy.run_path(str(base/'refine_arrival_scene.py'),run_name='__main__')
