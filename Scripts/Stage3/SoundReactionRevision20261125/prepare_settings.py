"""Root-only editor preparation: isolate Stage3's loud-device settings.

Creates/reuses one owned Stage3 settings copy and changes the Stage3 grid's
reference. It never saves a map or package; root reviews and performs saves.
Shared settings and Stage1/2 are not modified. Run only after native evidence.
"""
import hashlib
import json
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3SoundReactionRevision20261125'
DEST = '/Game/Environment/Stage3/SoundReaction_20261125/DA_Stage3DeviceSoundSettings'
OWNER = 'Stage3DeviceSoundRevision20261125'


def prepare(budget=1800.):
    assert 500. <= budget <= 5000.
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Root must stop PIE before preparation'
    world = ed.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    grid, = [a for a in u.GameplayStatics.get_all_actors_of_class(world, u.SoundGridManager)
             if a.get_actor_label() == 'S3_SoundGrid']
    ea = u.EditorAssetLibrary
    current = grid.get_editor_property('Settings')
    current_large = current.get_editor_property('LargeBudget')
    current_bell = grid.get_editor_property('PlayerBellBudgetOverride')
    bell = current_bell if current_bell > 0 else current_large
    source = current
    if ea.get_metadata_tag(current, 'Stage3SoundOwner') == OWNER:
        source = ea.load_asset(ea.get_metadata_tag(current, 'Stage3SoundOriginalSource'))
        assert source
    path = ROOT / 'Content' / (source.get_path_name().split('.')[0].removeprefix('/Game/') + '.uasset')
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if ea.does_asset_exist(DEST):
        target = ea.load_asset(DEST)
        assert ea.get_metadata_tag(target, 'Stage3SoundOwner') == OWNER, 'Do not replace an unowned asset'
        assert ea.get_metadata_tag(target, 'Stage3SoundOriginalSource') == source.get_path_name()
    else:
        target = ea.duplicate_asset(source.get_path_name(), DEST)
        assert target
        ea.set_metadata_tag(target, 'Stage3SoundOwner', OWNER)
        ea.set_metadata_tag(target, 'Stage3SoundOriginalSource', source.get_path_name())
    target.set_editor_property('LargeBudget', float(budget))
    grid.set_editor_property('Settings', target)
    grid.set_editor_property('PlayerBellBudgetOverride', float(bell))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source_hash
    report = {'stage3_grid': grid.get_path_name(), 'source': source.get_path_name(),
              'source_sha256': source_hash, 'prepared_settings': target.get_path_name(),
              'large_before': current_large, 'device_budget_after_cm': float(budget),
              'player_bell_effective_preserved_cm': float(bell),
              'small_preserved': target.get_editor_property('SmallBudget'),
              'medium_preserved': target.get_editor_property('MediumBudget'),
              'sound_speed_preserved': target.get_editor_property('SoundSpeed'),
              'source_large_unchanged': source.get_editor_property('LargeBudget'),
              'save_performed_by_script': False,
              'root_save_list_after_review': [target.get_path_name(), '/Game/Maps/Stage3'],
              'limits': 'Stage3 loud Device grade increases; player Bell override preserves its range. Native sound barriers/perception rules untouched.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'prepared_settings.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print('STAGE3_SOUND_SETTINGS_PREPARED', json.dumps(report))
    return report
