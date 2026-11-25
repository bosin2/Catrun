"""Isolated, unsaved native propagation probe. Direct emissions are diagnostic,
not proof that a real release interaction causes AI reaction. Run native_test.py
for that separate contract. Shared settings are restored before PIE shutdown.
"""
import hashlib
import json
import time
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3SoundReactionRevision20261125/PropagationProbe01'
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'report.json').exists()
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS, SL = u.GameplayStatics, u.SystemLibrary
S = {'scope': __doc__, 'phase': 'startup', 'started': time.monotonic(), 'cases': []}


def v(p): return [p.x, p.y, p.z]


def emit(grid, director, location, kind=u.CatrunSoundKind.DEVICE):
    e = u.CatrunSoundEvent()
    e.source = u.CatrunSoundSource.DEVICE if kind == u.CatrunSoundKind.DEVICE else u.CatrunSoundSource.CAT
    e.kind = kind
    e.size = u.CatrunSoundSize.LARGE
    e.target = u.CatrunSoundTarget.MINION
    e.location = location
    e.instigator = director
    assert grid.emit_sound(e)


def run(world):
    named = {a.get_actor_label(): a for a in GS.get_all_actors_of_class(world, u.Actor)}
    grid, director, door = (named[n] for n in ('S3_SoundGrid', 'S3_Objectives', 'S3_D0'))
    settings = grid.get_editor_property('Settings')
    old_large = settings.get_editor_property('LargeBudget')
    old_bell = grid.get_editor_property('PlayerBellBudgetOverride')
    old_door = door.is_open()
    settings_file = ROOT / 'Content' / (settings.get_path_name().split('.')[0].removeprefix('/Game/') + '.uasset')
    S['settings_asset'] = settings.get_path_name()
    S['shared_sha_before'] = hashlib.sha256(settings_file.read_bytes()).hexdigest()
    S['original'] = {p: settings.get_editor_property(p) for p in
                     ('LargeBudget', 'MediumBudget', 'SmallBudget', 'SoundSpeed', 'ArmorRunSpeedNoise')}
    S['original']['PlayerBellBudgetOverride'] = old_bell
    targets = {name: actor.get_actor_location() for name, actor in named.items() if isinstance(actor, u.CatrunArmor)}
    targets.update({'LobbyPatrolFarEndpoint': u.Vector(620, -650, 100),
                    'H1Near': u.Vector(250, -450, 26), 'H1Far': u.Vector(250, -550, 26),
                    'D0Center': u.Vector(150, -650, 100)})
    S['targets'] = {name: v(pos) for name, pos in targets.items()}
    try:
        grid.set_editor_property('PlayerBellBudgetOverride', old_bell if old_bell > 0 else old_large)
        for budget in sorted(set([old_large, 1000., 1400., 1800., 2200.])):
            settings.set_editor_property('LargeBudget', budget)
            for opened in (False, True):
                door.set_open(opened)
                for index, device in enumerate(director.get_editor_property('Devices')):
                    origin = device.get_editor_property('Ring').get_actor_location()
                    emit(grid, director, origin)
                    remaining = {name: grid.get_remaining_budget_at(pos) for name, pos in targets.items()}
                    S['cases'].append({'device': index + 1, 'budget': budget, 'd0_open': opened,
                                       'origin': v(origin), 'remaining': remaining,
                                       'native_weighted_path_cm': {n: budget - r if r >= 0 else None for n, r in remaining.items()}})
        settings.set_editor_property('LargeBudget', 1800.)
        door.set_open(False)
        emit(grid, director, u.Vector(250, -450, 26))
        S['cat_hole_control'] = {'source': [250, -450, 26], 'target': [250, -550, 26],
                                 'remaining': grid.get_remaining_budget_at(u.Vector(250, -550, 26)),
                                 'meaning': 'Sound crosses the cat hole; armor width restriction is separate.'}
        S['door_control'] = []
        for opened in (False, True):
            door.set_open(opened)
            emit(grid, director, u.Vector(70, -650, 100))
            remain = grid.get_remaining_budget_at(u.Vector(230, -650, 100))
            S['door_control'].append({'open': opened, 'source': [70, -650], 'target': [230, -650],
                                      'remaining': remain, 'path_cm': 1800. - remain if remain >= 0 else None,
                                      'door_center_remaining': grid.get_remaining_budget_at(u.Vector(150, -650, 100))})
        origin = director.get_editor_property('Devices')[0].get_editor_property('Ring').get_actor_location()
        emit(grid, director, origin, u.CatrunSoundKind.BELL)
        S['preserved_bell_remaining'] = {n: grid.get_remaining_budget_at(p) for n, p in targets.items()}
        S['success'] = True
    finally:
        settings.set_editor_property('LargeBudget', old_large)
        grid.set_editor_property('PlayerBellBudgetOverride', old_bell)
        door.set_open(old_door)
        S['shared_sha_after'] = hashlib.sha256(settings_file.read_bytes()).hexdigest()
        assert S['shared_sha_before'] == S['shared_sha_after']


def tick(_dt):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world():
                u.unregister_slate_post_tick_callback(S['handle'])
                SL.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - S['started'] < 120
        world = ED.get_game_world()
        if not world or GS.get_time_seconds(world) < .2:
            return
        run(world)
    except Exception:
        S['success'] = False
        S['error'] = traceback.format_exc()
    else:
        if S.get('success') is None:
            return
    S['phase'] = 'shutdown'
    (OUT / 'report.json').write_text(json.dumps({k: val for k, val in S.items() if k != 'handle'}, indent=2), encoding='utf8')
    LE.editor_request_end_play()


assert '-SaveToUserDir' in SL.get_command_line()
S['handle'] = u.register_slate_post_tick_callback(tick)
assert LE.load_level('/Game/Maps/Stage3')
LE.editor_request_begin_play()
