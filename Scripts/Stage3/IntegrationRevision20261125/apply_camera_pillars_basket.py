"""Root save: Stage2 camera pacing, original pillar tops and Annex clearance."""
import hashlib
import importlib.util
import json
import os
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_STAGE3_EFFECTS_PASS', 'Comfort01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3IntegrationRevision20261125' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'result.json').exists()
MAP = ROOT / 'Content/Maps/Stage3.umap'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
R = {'success': False, 'level_saved': False, 'phase': 'preflight'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'Scripts/Stage3' / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def persist():
    (OUT / 'result.json').write_text(json.dumps(R, indent=2, ensure_ascii=False), encoding='utf8')


try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert not ED.get_game_world() and ED.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    R['before_sha'] = sha(MAP)
    shutil.copy2(MAP, OUT / 'Stage3_before.umap')
    protected = [ROOT/'Content/Maps'/(n+'.umap') for n in ('Stage1','Stage2','SoundTest_Stage2')]
    protected += list((ROOT/'Content/Environment/Stage3/GateFX_20261125').rglob('*.uasset'))
    R['protected_before'] = {str(p): sha(p) for p in protected}
    os.environ['CATRUN_STAGE3_BASKET_HEIGHT_PASS'] = PASS
    R['basket_before_probe'] = module('s3_comfort_basket_probe','BasketHeightRevision20261125/probe.py').main()
    assert R['basket_before_probe']['success']
    R['phase'] = 'camera_pacing'; persist()
    R['camera'] = module('s3_comfort_camera','CameraPacingRevision20261125/prepare.py').prepare()
    assert R['camera']['success']
    R['phase'] = 'pillar_height'; persist()
    pillars = module('s3_comfort_pillars','PillarHeightRevision20261125/prepare.py')
    R['pillars'] = pillars.apply(expected_map_sha=R['before_sha'])
    assert R['pillars']['success']
    R['phase'] = 'basket_clearance'; persist()
    os.environ['CATRUN_STAGE3_BASKET_HEIGHT_FIX_PASS'] = PASS
    R['basket'] = module('s3_comfort_basket','BasketHeightRevision20261125/prepare.py').apply()
    assert R['basket']['success'], R['basket'].get('error')
    grid, = [a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
             if a.get_actor_label() == 'S3_SoundGrid']
    before_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
    grid.build_grid()
    assert grid.has_grid()
    after_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
    R['grid_changes'] = {key: sum(a != b for a,b in zip(before_grid[key], after_grid[key]))
                         for key in ('Walkable','EdgeMask','WallDistance')}
    R['grid_dimensions'] = [after_grid['Width'], after_grid['Height']]
    assert R['grid_changes']['Walkable'] == 0 and R['grid_changes']['EdgeMask'] == 0
    assert pillars.readback()['success']
    assert sha(MAP) == R['before_sha'], 'External Stage3 save during integration'
    assert R['protected_before'] == {str(p): sha(p) for p in protected}
    assert LE.save_current_level()
    R['level_saved'] = True
    R['after_sha'] = sha(MAP)
    R['protected_after'] = {str(p): sha(p) for p in protected}
    assert R['protected_before'] == R['protected_after']
    R.update(success=True, phase='saved_pending_native_and_visual_verification')
except Exception:
    R['error'] = traceback.format_exc()
finally:
    persist()
    print('STAGE3_COMFORT_RESULT', json.dumps({k:R.get(k) for k in ('success','level_saved','phase','error')}))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
