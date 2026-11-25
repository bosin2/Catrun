"""First Stage3 release -> native CommitRelease sound -> two live lobby armors.

No direct EmitSound, OnSoundHeard or armor movement calls. TryRelease starts the
normal alignment/muzzle-animation/commit path. One clearance-checked cat staging
is a fixture; capture is disabled so sound investigation can be observed. Enemy
tick/collision and authored patrols remain enabled. This is not difficulty QA.
Candidate mode changes settings only in this isolated process and restores them.
MODE=baseline|candidate|saved via CATRUN_SOUND_TEST_MODE; budget default1800cm.
Opt-in CATRUN_SOUND_OBSTACLE_FIX=lobby_two tags only the two implicated static
lobby props and rebakes in this isolated PIE. Default none leaves geometry alone.
"""
import hashlib
import json
import math
import os
import re
import time
import traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
MODE = os.environ.get('CATRUN_SOUND_TEST_MODE', 'candidate')
assert MODE in ('baseline', 'candidate', 'saved')
OBSTACLE_FIX = os.environ.get('CATRUN_SOUND_OBSTACLE_FIX', 'none')
assert OBSTACLE_FIX in ('none', 'lobby_two')
BUDGET = float(os.environ.get('CATRUN_DEVICE_SOUND_BUDGET', '1800'))
assert math.isfinite(BUDGET) and 500 <= BUDGET <= 5000
PASS = os.environ.get('CATRUN_SOUND_TEST_PASS', MODE + '01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3SoundReactionRevision20261125' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'report.json').exists()
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS, SL = u.GameplayStatics, u.SystemLibrary
S = {'scope': __doc__, 'mode': MODE, 'phase': 'startup', 'started': time.monotonic(),
     'changed': time.monotonic(), 'checks': [], 'samples': [], 'targets': {},
     'command_line': SL.get_command_line(), 'direct_emit_calls': 0, 'direct_hearing_calls': 0}
LIVE = {}


def v(p): return [p.x, p.y, p.z]


def persist():
    (OUT / 'report.json').write_text(json.dumps({k: val for k, val in S.items() if k != 'handle'}, indent=2), encoding='utf8')


def check(name, passed, detail=None):
    S['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
    persist()
    return bool(passed)


def phase(name, world):
    S['phase'] = name
    S['changed'] = time.monotonic()
    S['phase_game_start'] = GS.get_time_seconds(world)
    persist()


def artifact_hashes():
    paths = [ROOT / ('Content/Maps/' + name + '.umap') for name in ('Stage1', 'Stage2', 'Stage3')]
    if 'settings_path' in LIVE:
        paths.append(LIVE['settings_path'])
    shared = ROOT / 'Content/Systems/Sound/DA_SoundSettings.uasset'
    paths.append(shared)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}


def collect_native_log():
    match = re.search(r'-abslog=(?:"([^"]+)"|(\S+))', S['command_line'], re.I)
    if not match:
        return []
    path = Path(match.group(1) or match.group(2))
    S['log_path'] = str(path)
    if not path.exists():
        return []
    names = {a.get_name() for a in LIVE.get('armors', {}).values()}
    return [line for line in path.read_text(encoding='utf8', errors='replace').splitlines()
            if any(name in line for name in names) and any(token in line for token in
                ('heard a sound', 'found no path', 'is stuck', 'leg ', 'reached patrol point'))]


def finish(error=None):
    if LIVE.get('original_obstacle_tags'):
        for actor, tags in LIVE['original_obstacle_tags']:
            actor.set_editor_property('tags', tags)
        S['temporary_obstacle_tags_restored'] = True
    if MODE == 'candidate' and 'settings' in LIVE:
        LIVE['settings'].set_editor_property('LargeBudget', S['original']['LargeBudget'])
        LIVE['grid'].set_editor_property('PlayerBellBudgetOverride', S['original']['PlayerBellBudgetOverride'])
    S['hashes_after'] = artifact_hashes()
    if 'hashes_before' in S:
        check('Stage1 Stage2 Stage3 and shared settings bytes preserved', S['hashes_after'] == S['hashes_before'])
    S['native_log'] = collect_native_log()
    if S.get('commit_game') is not None:
        for label, actor in LIVE['armors'].items():
            heard = [line for line in S['native_log'] if actor.get_name() in line and 'heard a sound' in line]
            S['targets'][label]['native_heard_log'] = heard
            check(label + ' native heard log confirms actual notification', bool(heard), heard)
    S['execution_complete'] = error is None
    S['success'] = error is None and all(c['passed'] for c in S['checks'])
    S['error'] = error
    S['phase'] = 'shutdown'
    S['changed'] = time.monotonic()
    persist()
    if ED.get_game_world():
        LE.editor_request_end_play()


def setup(world, cat):
    actors = {a.get_actor_label(): a for a in GS.get_all_actors_of_class(world, u.Actor)}
    grid, director = actors['S3_SoundGrid'], actors['S3_Objectives']
    settings = grid.get_editor_property('Settings')
    LIVE.update(grid=grid, director=director, settings=settings, cat=cat,
                armors={name: actors[name] for name in ('S3_Armor_LobbyPost', 'S3_Armor_LobbyPatrol')},
                door=actors['S3_D0'])
    LIVE['settings_path'] = ROOT / 'Content' / (settings.get_path_name().split('.')[0].removeprefix('/Game/') + '.uasset')
    S['hashes_before'] = artifact_hashes()
    S['original'] = {key: settings.get_editor_property(key) for key in
                     ('LargeBudget', 'MediumBudget', 'SmallBudget', 'SoundSpeed', 'ArmorRunSpeedNoise')}
    S['original']['PlayerBellBudgetOverride'] = grid.get_editor_property('PlayerBellBudgetOverride')
    S['settings_asset'] = settings.get_path_name()
    fingerprints = [ROOT / 'Binaries/Win64/UnrealEditor-Catrun.dll',
                    ROOT / 'Source/Catrun/Monster/CatrunArmor.cpp',
                    ROOT / 'Source/Catrun/Monster/CatrunArmor.h',
                    ROOT / 'Source/Catrun/Grid/CatrunGridData.cpp']
    S['runtime_disk_build_fingerprints'] = {
        str(p.relative_to(ROOT)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                                   'modified_epoch': p.stat().st_mtime}
        for p in fingerprints if p.exists()}
    S['build_fingerprint_limit'] = 'Disk DLL at setup, not proof of the already-loaded module image; root launches cold.'
    S['obstacle_fix'] = {'mode': OBSTACLE_FIX, 'applied': [], 'production_saved': False}
    if OBSTACLE_FIX == 'lobby_two':
        assert MODE == 'candidate', 'Transient cause-isolation fixture requires candidate mode'
        tag = settings.get_editor_property('ObstacleTag')
        S['obstacle_fix']['configured_tag'] = str(tag)
        assert str(tag) and str(tag) != str(settings.get_editor_property('WallTag'))
        LIVE['original_obstacle_tags'] = []
        saved_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
        (OUT / 'grid_saved_before_fresh_bake.json').write_text(json.dumps(saved_grid), encoding='utf8')
        # A serialized bake can predate later map edits. First rebake the current
        # unmodified scene; compare tag-only effects against this fresh baseline,
        # never against differently sized/stale serialized geometry. These two
        # bakes run synchronously in one setup callback with no intervening tick.
        grid.build_grid()
        assert grid.has_grid()
        before_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
        S['obstacle_fix']['baseline'] = 'Fresh BuildGrid on the same current scene before any tag changes'
        S['obstacle_fix']['serialized_bake_stale'] = saved_grid != before_grid
        S['obstacle_fix']['saved_to_fresh_changed_fields'] = [key for key in before_grid
                                                              if saved_grid.get(key) != before_grid[key]]
        S['obstacle_fix']['saved_grid_shape'] = {key: saved_grid[key] for key in ('Origin', 'CellSize', 'Width', 'Height')}
        S['obstacle_fix']['fresh_grid_shape'] = {key: before_grid[key] for key in ('Origin', 'CellSize', 'Width', 'Height')}
        (OUT / 'grid_before_obstacle_tags.json').write_text(json.dumps(before_grid), encoding='utf8')
        for label in ('S3_Gothic_LobbyBench', 'S3_Gothic_LobbyCabinet'):
            actor = actors[label]
            assert isinstance(actor, u.StaticMeshActor)
            component = actor.static_mesh_component
            assert component.get_collision_object_type() == u.CollisionChannel.ECC_WORLD_STATIC
            assert component.get_collision_enabled() != u.CollisionEnabled.NO_COLLISION
            assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN) == u.CollisionResponseType.ECR_BLOCK
            original_tags = list(actor.tags)
            LIVE['original_obstacle_tags'].append((actor, original_tags))
            actor.set_editor_property('tags', original_tags if tag in original_tags else original_tags + [tag])
            center, extent = actor.get_actor_bounds(True, False)
            S['obstacle_fix']['applied'].append({'label': label, 'tags_before': list(map(str, original_tags)),
                'tags_after': list(map(str, actor.tags)), 'bounds_min': v(center - extent), 'bounds_max': v(center + extent)})
        grid.build_grid()
        assert grid.has_grid()
        after_grid = json.loads(grid.call_method('ExportBakedGridSnapshot'))
        (OUT / 'grid_after_obstacle_tags.json').write_text(json.dumps(after_grid), encoding='utf8')
        # Sound must retain exactly its geometry and costs: ObstacleTag affects
        # armor clearance only. Do not hide a sound-rule change in this fix.
        keys = ('Origin', 'CellSize', 'Width', 'Height', 'Walkable', 'EdgeMask', 'CostMultiplier')
        assert check('Furniture-only obstacle fix preserves sound grid connectivity and costs',
                     all(before_grid[k] == after_grid[k] for k in keys),
                     {'comparison': 'fresh untagged scene vs same scene with only two furniture tags',
                      'changed_sound_fields': [key for key in keys if before_grid[key] != after_grid[key]]})
        assert check('Furniture obstacle tags change armor wall-distance field',
                     before_grid['WallDistance'] != after_grid['WallDistance'])
    if MODE == 'candidate':
        settings.set_editor_property('LargeBudget', BUDGET)
        bell = S['original']['PlayerBellBudgetOverride']
        grid.set_editor_property('PlayerBellBudgetOverride', bell if bell > 0 else S['original']['LargeBudget'])
    S['effective_device_budget'] = settings.get_editor_property('LargeBudget')
    S['effective_bell_budget'] = grid.get_editor_property('PlayerBellBudgetOverride') or settings.get_editor_property('LargeBudget')
    expected_bell = S['original']['PlayerBellBudgetOverride'] or S['original']['LargeBudget']
    check('Player bell effective budget preserved', S['effective_bell_budget'] == expected_bell,
          {'before': expected_bell, 'after': S['effective_bell_budget']})
    if MODE == 'saved':
        check('Saved Stage3 settings are isolated from shared source', '/Stage3/' in S['settings_asset'])
    u.CatrunUserSettings.set_no_armor_capture_enabled(True)
    device = director.get_editor_property('Devices')[0]
    housing = device.get_editor_property('Housing')
    front = housing.get_actor_location() + housing.get_actor_forward_vector() * 10 + housing.get_actor_right_vector() * 70
    cap = cat.get_component_by_class(u.CapsuleComponent)
    front.z = cap.get_scaled_capsule_half_height() + 2.2
    hit = SL.capsule_trace_single_by_profile(world, front, front + u.Vector(0, 0, .1),
           cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(), 'Pawn', False,
           [cat], u.DrawDebugTrace.NONE, False)
    assert check('First device front cat staging physically clear', not hit,
                 {k: str(val) for k, val in hit.to_dict().items()} if hit else v(front))
    cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    cat.set_actor_location(front, False, True)
    S['cat_staging'] = v(front)
    S['d0_initially_open'] = LIVE['door'].is_open()
    for label, actor in LIVE['armors'].items():
        S['targets'][label] = {'native_name': actor.get_name(), 'start': v(actor.get_actor_location()),
                              'first_response_game': None, 'max_speed_cm_s': 0.,
                              'initial_has_destination': actor.has_destination(),
                              'walk_speed': actor.get_editor_property('WalkSpeed')}
        check(label + ' retains native tick and collision', actor.is_actor_tick_enabled() and actor.get_actor_enable_collision())
    phase('activate', world)


def step(world):
    cat = GS.get_player_character(world, 0)
    if not cat:
        return
    game = GS.get_time_seconds(world)
    if S['phase'] == 'startup':
        if game > .3:
            setup(world, cat)
        return
    director = LIVE['director']
    if S['phase'] == 'activate':
        if game - S['phase_game_start'] < .25:
            return
        assert check('First real release is reachable', director.can_release(0, cat))
        assert check('Native TryRelease begins physical interaction', director.try_release(0, cat))
        check('Starting interaction has not yet committed', not director.get_editor_property('Devices')[0].get_editor_property('bReleased'))
        S['activation_game'] = game
        phase('observe', world)
        return
    if S['phase'] != 'observe':
        return
    device = director.get_editor_property('Devices')[0]
    released = device.get_editor_property('bReleased')
    mesh = cat.get_component_by_class(u.SkeletalMeshComponent)
    clip_time = mesh.get_position() if isinstance(mesh.get_anim_instance(), u.AnimSingleNodeInstance) else None
    if released and 'commit_game' not in S:
        S['commit_game'] = game
        S['commit_animation_seconds'] = clip_time
        S['event_origin'] = v(device.get_editor_property('Ring').get_actor_location())
        S['event_origin_observation'] = 'Ring position on the first observed bReleased frame; native CommitRelease emits the ring position at frame44. Not a direct delegate payload capture.'
        check('Commit occurs during native pull clip after frame44', clip_time is not None and clip_time >= 44. / 30., clip_time)
        for label, actor in LIVE['armors'].items():
            remaining = LIVE['grid'].get_remaining_budget_at(actor.get_actor_location())
            row = S['targets'][label]
            row['at_commit'] = v(actor.get_actor_location())
            row['remaining_budget_at_commit'] = remaining
            row['weighted_path_cm'] = S['effective_device_budget'] - remaining if remaining > 0 else None
            row['expected_sound_travel_seconds'] = row['weighted_path_cm'] / S['original']['SoundSpeed'] if remaining > 0 else None
            check(label + ' is reached by actual committed native sound', remaining > 0, row)
        persist()
    sample = {'game': game, 'released': released, 'clip_seconds': clip_time,
              'active_device': director.get_editor_property('ActiveDevice'), 'd0_open': LIVE['door'].is_open(),
              'cat': v(cat.get_actor_location()), 'armors': {}}
    for label, actor in LIVE['armors'].items():
        row = S['targets'][label]
        speed = actor.get_velocity().length()
        row['max_speed_cm_s'] = max(row['max_speed_cm_s'], speed)
        state = {'location': v(actor.get_actor_location()), 'action': str(actor.get_action()),
                 'has_destination': actor.has_destination(), 'seeing_cat': actor.is_seeing_cat(), 'speed': speed}
        sample['armors'][label] = state
        if released and actor.has_destination() and not actor.is_seeing_cat() and row['first_response_game'] is None:
            row['first_response_game'] = game
            row['first_response_state'] = state
    S['samples'].append(sample)
    if not released and game - S['activation_game'] > 12.:
        check('Native interaction commits within twelve game seconds', False)
        finish()
        return
    if released and game - S['commit_game'] > 25.:
        origin = u.Vector(*S['event_origin'])
        for label, actor in LIVE['armors'].items():
            row = S['targets'][label]
            samples = [s['armors'][label] for s in S['samples'] if s['released']]
            closest = min(math.hypot(s['location'][0] - origin.x, s['location'][1] - origin.y) for s in samples)
            moved = max((u.Vector(*s['location']) - u.Vector(*row['at_commit'])).length() for s in samples)
            row.update(closest_to_sound_cm=closest, max_displacement_from_commit_cm=moved)
            check(label + ' enters native sound response', row['first_response_game'] is not None, row.get('first_response_state'))
            check(label + ' runs faster than its patrol walk', row['max_speed_cm_s'] > row['walk_speed'] + 10., row['max_speed_cm_s'])
            check(label + ' physically moves at least150cm', moved >= 150., moved)
            check(label + ' approaches committed source within200cm', closest <= 200., closest)
        responses = [r['first_response_game'] for r in S['targets'].values()]
        check('Both armors respond within three seconds of each other',
              all(t is not None for t in responses) and max(responses) - min(responses) <= 3., responses)
        check('Both armors concurrently investigate the same single device event',
              any(all(state['has_destination'] and not state['seeing_cat'] for state in s['armors'].values())
                  for s in S['samples'] if s['released']))
        check('Physical release finishes and restores player actions', director.get_editor_property('ActiveDevice') == -1
              and not cat.get_component_by_class(u.CatrunBasketInteractionComponent).get_editor_property('Busy'))
        S['target_position_visibility_limit'] = 'Native private Destination is not reflected in current Python API. Single committed event origin, native heard logs, response state and actual approach prove routing; exact internal Destination getter not claimed.'
        finish()


def tick(_dt):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > .5:
                u.unregister_slate_post_tick_callback(S['handle'])
                SL.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - S['started'] < 240., 'Sound reaction test timeout'
        world = ED.get_game_world()
        if world:
            step(world)
    except Exception:
        finish(traceback.format_exc())


assert '-SaveToUserDir' in SL.get_command_line()
S['handle'] = u.register_slate_post_tick_callback(tick)
assert LE.load_level('/Game/Maps/Stage3')
LE.editor_request_begin_play()
