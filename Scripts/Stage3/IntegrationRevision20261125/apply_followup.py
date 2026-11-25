"""Root integration of runtime-discovered Stage3 camera and basket corrections."""
import hashlib
import importlib.util
import json
import os
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_STAGE3_EFFECTS_PASS', 'Followup01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3IntegrationRevision20261125' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'result.json').exists()
MAP = ROOT / 'Content/Maps/Stage3.umap'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
R = {'success': False, 'level_saved': False, 'phase': 'preflight'}


def sha():
    return hashlib.sha256(MAP.read_bytes()).hexdigest()


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def persist():
    (OUT / 'result.json').write_text(json.dumps(R, indent=2), encoding='utf8')


try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert not ED.get_game_world() and ED.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    R['before_sha'] = sha()
    shutil.copy2(MAP, OUT / 'Stage3_before.umap')
    R['phase'] = 'camera_near_plane'
    persist()
    R['near_clip'] = module('s3_near_clip_fix', 'Scripts/Stage3/GateHallRevision20261125/near_clip.py').apply()
    R['phase'] = 'warehouse_basket_clearance'
    persist()
    R['warehouse_basket'] = module('s3_warehouse_basket_fix', 'Scripts/Stage3/PlacementRevision20261125/relocate_warehouse.py').apply()
    assert R['warehouse_basket']['success'], R['warehouse_basket'].get('error')
    grid, = [a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
             if a.get_actor_label() == 'S3_SoundGrid']
    previous_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
    grid.build_grid()
    assert grid.has_grid()
    baked = json.loads(grid.call_method('ExportBakedGridSnapshot'))
    assert baked['Width'] > 0 and baked['Height'] > 0
    R['rebuilt_grid_dimensions'] = [baked['Width'], baked['Height']]
    R['grid_changes'] = {key: sum(a != b for a, b in zip(previous_grid[key], baked[key]))
                         for key in ('Walkable', 'EdgeMask', 'WallDistance')}
    assert sha() == R['before_sha'], 'Stage3 changed on disk during follow-up'
    assert LE.save_current_level()
    R.update(success=True, level_saved=True, after_sha=sha(), phase='saved_pending_runtime_recheck')
except Exception:
    R['error'] = traceback.format_exc()
finally:
    persist()
    print('STAGE3_FOLLOWUP_RESULT', json.dumps({k: R.get(k) for k in ('success','level_saved','phase','error')}))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
