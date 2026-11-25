"""Root-only Stage3 dust style match from the completed Stage2 material."""
import hashlib
import importlib.util
import json
import os
import shutil
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_STAGE3_EFFECTS_PASS', 'Stage2DustMatch01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3IntegrationRevision20261125' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'result.json').exists(), 'Preserve previous evidence'
MAP = ROOT / 'Content/Maps/Stage3.umap'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
EA = u.EditorAssetLibrary
R = {'success': False, 'level_saved': False, 'scope': 'Sixteen Stage3 dust material bindings only'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'Scripts/Stage3/GateFXRevision20261125' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


try:
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
    assert not ED.get_game_world()
    world = ED.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    R['before_sha'] = sha(MAP)
    shutil.copy2(MAP, OUT / 'Stage3_before.umap')
    protected = [ROOT / 'Content/Maps' / (name + '.umap') for name in ('Stage1', 'Stage2', 'SoundTest_Stage2')]
    protected += list((ROOT / 'Content/Environment/Stage3/GateFX_20261125/Run04').rglob('*.uasset'))
    protected += list((ROOT / 'Content/Environment/Stage2/GameplayPolish_20261125/Presentation/Build_03').rglob('*.uasset'))
    R['protected_before'] = {str(p): sha(p) for p in protected}
    guard = module('s3_dust_match_guard', 'author.py')
    before = guard.preserved_state(world)
    director, = [a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
                 if a.get_actor_label() == 'S3_StatuePuzzles']
    reveal = director.get_editor_property('Reveal')
    tuning = guard.reveal_tuning(reveal)
    R['match'] = module('s3_dust_match_apply', 'stage2_dust_match.py').prepare()
    assert R['match']['success'] and len(R['match']['records']) == 16
    after = guard.preserved_state(world)
    R['non_effect_actor_difference'] = guard.preservation_diff(before, after)
    assert before == after, R['non_effect_actor_difference']
    assert tuning == guard.reveal_tuning(reveal)
    R['native_reveal_tuning'] = tuning
    assert sha(MAP) == R['before_sha'], 'External Stage3 edit during preparation'
    assert R['protected_before'] == {str(p): sha(p) for p in protected}
    for path in R['match']['asset_save_paths']:
        assert path.startswith('/Game/Environment/Stage3/GateFX_20261125/Stage2DustMatch01/')
        assert EA.save_loaded_asset(EA.load_asset(path))
    assert LE.save_current_level()
    R['level_saved'] = True
    R['after_sha'] = sha(MAP)
    R['protected_after'] = {str(p): sha(p) for p in protected}
    assert R['protected_before'] == R['protected_after']
    R['success'] = True
except Exception:
    R['error'] = traceback.format_exc()
finally:
    (OUT / 'result.json').write_text(json.dumps(R, indent=2), encoding='utf8')
    print('STAGE3_DUST_STYLE_MATCH', json.dumps({k: R.get(k) for k in ('success', 'level_saved', 'error')}))
    u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
