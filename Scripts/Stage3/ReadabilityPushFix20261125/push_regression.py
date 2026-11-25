"""Physical rear access and native-tick statue pushing on the saved Stage3 map.

CATRUN_PUSH_REGRESSION_PHASE=before|after (default after).
CATRUN_PUSH_REGRESSION_PASS selects an unused evidence folder (default phase01).
Each independent case begins at one clearance-checked staging location. All
subsequent approach, push and reset-clearance travel uses AddMovementInput.
There are no TryPushStatue calls, statue teleports, movement-mode overrides or
per-frame cat relocations. NPC tick/collision is disabled for deterministic
geometry tests; this is not a campaign or enemy-difficulty playthrough.
The isolated PIE process ends without saving packages or user settings.
"""
import json
import os
import time
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
EXPECTED_PHASE = os.environ.get('CATRUN_PUSH_REGRESSION_PHASE', 'after').lower()
assert EXPECTED_PHASE in ('before', 'after')
PASS = os.environ.get('CATRUN_PUSH_REGRESSION_PASS', EXPECTED_PHASE + '01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3ReadabilityPushFix20261125/PushRegression' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'report.json').exists(), 'Preserve previous regression evidence'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS, SL = u.GameplayStatics, u.SystemLibrary
PAWN, BLOCK = u.CollisionChannel.ECC_PAWN, u.CollisionResponseType.ECR_BLOCK
OBJECTS = [getattr(u.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
S = {'scope': __doc__, 'expected_phase': EXPECTED_PHASE, 'phase': 'startup',
     'started': time.monotonic(), 'changed': time.monotonic(), 'checks': [],
     'cases': {}, 'staging_relocations': [], 'native_push_api_calls': 0,
     'packages_saved': False, 'command_line': SL.get_command_line()}
RUNTIME = {}


def vec(v):
    return [v.x, v.y, v.z]


def persist():
    (OUT / 'report.json').write_text(json.dumps(
        {k: v for k, v in S.items() if k != 'handle'}, indent=2, ensure_ascii=False), encoding='utf8')


def check(name, passed, detail=None):
    S['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
    persist()
    assert passed, (name, detail)


def phase(name, world=None):
    S['phase'] = name
    S['changed'] = time.monotonic()
    if world:
        S['phase_game_start'] = GS.get_time_seconds(world)
    persist()


def finish(error=None):
    S['success'] = error is None
    S['error'] = error
    phase('shutdown')
    if ED.get_game_world():
        LE.editor_request_end_play()


def named(world):
    return {a.get_actor_label(): a for a in GS.get_all_actors_of_class(world, u.Actor)}


def cap_trace(world, cat, start, end):
    cap = cat.get_component_by_class(u.CapsuleComponent)
    return SL.capsule_trace_single_by_profile(
        world, start, end, cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(),
        'Pawn', False, [cat], u.DrawDebugTrace.NONE, False)


def hit_data(hit):
    return {key: str(value) for key, value in hit.to_dict().items()} if hit else None


def blockers(world, cat, point):
    cap = cat.get_component_by_class(u.CapsuleComponent)
    overlaps = SL.capsule_overlap_components(
        world, point, cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(),
        OBJECTS, u.PrimitiveComponent, [cat]) or []
    return [{'actor': c.get_owner().get_actor_label(), 'component': c.get_path_name()}
            for c in overlaps if c.get_collision_response_to_channel(PAWN) == BLOCK
            and cap.get_collision_response_to_channel(c.get_collision_object_type()) == BLOCK]


def stop(cat):
    cat.consume_movement_input_vector()
    cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()


def initialize_case(world, cat, number):
    actors = named(world)
    puzzle = actors['S3_StatuePuzzles']
    link = puzzle.get_editor_property('Links')[number - 1]
    statue = link.get_editor_property('Statue')
    center, extent = statue.get_actor_bounds(False, False)
    wall = actors['S3_Wall_0012' if number == 1 else 'S3_Wall_0122']
    wall_center, wall_extent = wall.get_actor_bounds(True, False)
    cap = cat.get_component_by_class(u.CapsuleComponent)
    radius = cap.get_scaled_capsule_radius()
    z = cap.get_scaled_capsule_half_height() + 2.2
    rear_surface = center.y + extent.y
    wall_front = wall_center.y - wall_extent.y
    settings = puzzle.get_editor_property('Settings')
    contact = settings.get_editor_property('ContactDistance')
    push_speed = settings.get_editor_property('PushSpeed')
    deceleration = settings.get_editor_property('PushDeceleration')
    rear = u.Vector(center.x, rear_surface + radius + min(5., contact * .5), z)
    legacy = u.Vector(statue.get_actor_location().x, statue.get_actor_location().y + 85., z)
    overlap = blockers(world, cat, legacy)
    fixture_hit = cap_trace(world, cat, legacy, legacy + u.Vector(0, 0, .1))
    start = u.Vector(-300, -1425, z) if number == 1 else u.Vector(100, -2025, z)
    waypoints = ([(-590, -1425), (-590, rear.y), (rear.x, rear.y)] if number == 1
                 else [(600, -2025), (760, -2025), (rear.x, rear.y)])
    row = {'initial_statue': vec(statue.get_actor_location()),
           'initial_transform': statue.get_actor_transform().export_text(),
           'initial_plate': vec(link.get_editor_property('Plate').get_actor_location()),
           'statue_extent': vec(extent), 'wall_label': wall.get_actor_label(),
           'wall_front_y': wall_front, 'statue_rear_y': rear_surface,
           'rear_gap_cm': wall_front - rear_surface, 'capsule_radius_cm': radius,
           'capsule_half_height_cm': cap.get_scaled_capsule_half_height(),
           'legacy_fixture': vec(legacy), 'legacy_fixture_wall_penetration_cm': max(0., legacy.y + radius - wall_front),
           'legacy_fixture_blockers': overlap, 'legacy_fixture_sweep': hit_data(fixture_hit),
           'rear_target': vec(rear), 'staging': vec(start), 'waypoints': waypoints,
           'approach_segments': [], 'approach_samples': [], 'samples': [],
           'contact_distance_cm': contact,
           # Normal Tick may push as soon as the walking cat enters contact.
           # Bound that advance by the contact band plus maximum coast distance.
           'approach_advance_limit_cm': contact + push_speed * push_speed / (2. * max(1., deceleration)) + .1}
    S['cases'][str(number)] = row
    S['case'] = number
    expected_y = (-1430 if EXPECTED_PHASE == 'before' else -1510) if number == 1 else -2140
    expected_gap = (40 if EXPECTED_PHASE == 'before' else 120) if number == 1 else 115
    check('P%d saved statue start matches phase' % number, abs(statue.get_actor_location().y - expected_y) < .05, row['initial_statue'])
    check('P%d measured rear gap' % number, abs(row['rear_gap_cm'] - expected_gap) < .05,
          {'actual_cm': row['rear_gap_cm'], 'expected_cm': expected_gap})
    if number == 1 and EXPECTED_PHASE == 'before':
        check('Before P1 legacy fixture penetrates wall by five cm',
              abs(row['legacy_fixture_wall_penetration_cm'] - 5.) < .05, row['legacy_fixture_wall_penetration_cm'])
        check('Before P1 real capsule overlaps rear wall',
              any(v['actor'] == wall.get_actor_label() for v in overlap), overlap)
        check('Before P1 real capsule sweep rejects legacy fixture', bool(fixture_hit), hit_data(fixture_hit))
    else:
        check('P%d rear fixture has no capsule overlaps' % number, not overlap, overlap)
        check('P%d rear fixture capsule sweep is clear' % number, not fixture_hit, hit_data(fixture_hit))
    staged_overlap = blockers(world, cat, start)
    staged_hit = cap_trace(world, cat, start, start + u.Vector(0, 0, .1))
    check('P%d independent staging is physically clear' % number,
          not staged_overlap and not staged_hit, {'overlaps': staged_overlap, 'sweep': hit_data(staged_hit)})
    stop(cat)
    # This is the only cat relocation in a case. It is remote from contact and
    # checked against real collision above; subsequent travel is input-only.
    cat.set_actor_location(start, False, True)
    S['staging_relocations'].append({'case': number, 'location': vec(start)})
    S['waypoint_index'] = 0
    S['segment_started'] = False
    phase('approach', world)


def walk_to(world, cat, target, timeout):
    pos = cat.get_actor_location()
    delta = u.Vector(target.x - pos.x, target.y - pos.y, 0)
    if delta.length() < 1.5:
        stop(cat)
        return 'arrived'
    if GS.get_time_seconds(world) - S['segment_game_start'] > timeout:
        stop(cat)
        return 'blocked'
    cat.add_movement_input(delta.normal(), min(1., delta.length() / 60.), False)
    return 'walking'


def advance_case(world, cat):
    if S['case'] == 1:
        initialize_case(world, cat, 2)
    else:
        check('Exactly one clear staging relocation per independent case', len(S['staging_relocations']) == 2)
        finish()


def step(world):
    cat = GS.get_player_character(world, 0)
    if not cat:
        return
    if 'actors' not in RUNTIME:
        RUNTIME['actors'] = named(world)
    actors = RUNTIME['actors']
    puzzle = actors['S3_StatuePuzzles']
    game = GS.get_time_seconds(world)
    if S['phase'] == 'startup':
        if game < 2.:
            return
        for cls in (u.CatrunArmor, u.CatrunCandle):
            for actor in GS.get_all_actors_of_class(world, cls):
                actor.set_actor_tick_enabled(False)
                actor.set_actor_enable_collision(False)
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        check('Normal native tick push does not require interact key',
              not puzzle.get_editor_property('Settings').get_editor_property('bRequireInteractKey'))
        check('Puzzle native tick is enabled', puzzle.is_actor_tick_enabled())
        initialize_case(world, cat, 1)
        return
    number = S['case']
    row = S['cases'][str(number)]
    link = puzzle.get_editor_property('Links')[number - 1]
    statue = link.get_editor_property('Statue')
    if S['phase'] == 'approach':
        row['approach_samples'].append({'game_seconds': game, 'statue': vec(statue.get_actor_location()),
                                        'cat': vec(cat.get_actor_location()),
                                        'last_input': vec(cat.get_last_movement_input_vector())})
        point = row['waypoints'][S['waypoint_index']]
        target = u.Vector(point[0], point[1], row['rear_target'][2])
        if not S['segment_started']:
            start = cat.get_actor_location()
            hit = cap_trace(world, cat, start, target)
            row['approach_segments'].append({'from': vec(start), 'to': vec(target), 'sweep': hit_data(hit)})
            if EXPECTED_PHASE == 'after' or number == 2:
                check('P%d approach segment%d capsule sweep clear' % (number, S['waypoint_index']), not hit, hit_data(hit))
            S['segment_started'] = True
            S['segment_game_start'] = game
        result = walk_to(world, cat, target, 8. if number == 1 and EXPECTED_PHASE == 'before' else 15.)
        if result == 'blocked':
            row['actual_approach_end'] = vec(cat.get_actor_location())
            row['approach_failed_at_segment'] = S['waypoint_index']
            # Require the diagnosed rear-wall stop, not any unrelated route
            # obstruction, to count as the expected baseline failure.
            pos = cat.get_actor_location()
            expected = (number == 1 and EXPECTED_PHASE == 'before'
                        and S['waypoint_index'] == 1
                        and abs(pos.x + 590.) < 3.
                        and abs(pos.y - (row['wall_front_y'] - row['capsule_radius_cm'])) < 3.)
            check('P%d physical rear approach has expected outcome' % number, expected,
                  {'expected_blocked': expected, 'target': vec(target), 'actual': row['actual_approach_end']})
            check('Before P1 failed approach did not move statue',
                  (statue.get_actor_location() - u.Vector(*row['initial_statue'])).length() < .05)
            row['outcome'] = 'expected rear access failure; no native push attempted'
            advance_case(world, cat)
        elif result == 'arrived':
            S['waypoint_index'] += 1
            S['segment_started'] = False
            if S['waypoint_index'] == len(row['waypoints']):
                check('P%d physical rear approach succeeds only when expected' % number,
                      not (number == 1 and EXPECTED_PHASE == 'before'), vec(cat.get_actor_location()))
                pos = statue.get_actor_location()
                approach_advance = row['initial_statue'][1] - pos.y
                row['approach_native_advance_cm'] = approach_advance
                row['push_start_statue'] = vec(pos)
                samples = row['approach_samples']
                off_axis = max(max(abs(v['statue'][0] - row['initial_statue'][0]),
                                   abs(v['statue'][2] - row['initial_statue'][2])) for v in samples)
                reverse_steps = [b['statue'][1] - a['statue'][1] for a, b in zip(samples, samples[1:])]
                check('P%d approach native motion stays on authored axis' % number,
                      off_axis < .05, {'max_off_axis_cm': off_axis})
                check('P%d approach native motion only advances toward plate' % number,
                      approach_advance >= -.05 and max(reverse_steps, default=0.) < .05,
                      {'advance_cm': approach_advance, 'largest_reverse_step_cm': max(reverse_steps, default=0.)})
                check('P%d approach native advance stays within contact and coast bound' % number,
                      approach_advance <= row['approach_advance_limit_cm'],
                      {'advance_cm': approach_advance, 'limit_cm': row['approach_advance_limit_cm'],
                       'initial_statue': row['initial_statue'], 'push_phase_start_statue': row['push_start_statue']})
                check('P%d reached contact without capsule overlap' % number,
                      not blockers(world, cat, cat.get_actor_location()))
                check('P%d contact reached in grounded native movement' % number,
                      cat.get_component_by_class(u.CharacterMovementComponent).movement_mode == u.MovementMode.MOVE_WALKING)
                row['push_start_cat'] = vec(cat.get_actor_location())
                phase('push', world)
        return
    if S['phase'] == 'push':
        pos = statue.get_actor_location()
        travelled = row['push_start_statue'][1] - pos.y
        total_travelled = row['initial_statue'][1] - pos.y
        row['samples'].append({'seconds': game - S['phase_game_start'], 'statue': vec(pos),
                              'cat': vec(cat.get_actor_location()), 'last_input': vec(cat.get_last_movement_input_vector()),
                              'distance_from_push_phase_start_cm': travelled,
                              'distance_from_saved_start_cm': total_travelled})
        if travelled >= 60.:
            stop(cat)
            check('P%d native Tick pushes at least sixty cm' % number, travelled >= 60., travelled)
            check('P%d native push stayed on authored axis' % number, abs(pos.x - row['initial_statue'][0]) < .05, vec(pos))
            check('P%d actual last movement input drove the push' % number,
                  any(v['last_input'][1] < -.01 for v in row['samples']))
            check('P%d cat physically followed statue' % number,
                  row['push_start_cat'][1] - cat.get_actor_location().y > 35.,
                  {'start': row['push_start_cat'], 'end': vec(cat.get_actor_location())})
            row['native_push_distance_cm'] = travelled
            row['total_native_advance_from_saved_start_cm'] = total_travelled
            row['outcome'] = 'rear reached by physical movement; native Tick push passed'
            phase('settle', world)
            return
        if game - S['phase_game_start'] > 15.:
            check('P%d native Tick push makes progress' % number, False,
                  {'distance_cm': travelled, 'last_sample': row['samples'][-1]})
        cat.add_movement_input(u.Vector(0, -1, 0), 1., False)
        return
    if S['phase'] == 'settle':
        if game - S['phase_game_start'] < .75:
            return
        pos = cat.get_actor_location()
        side = -590. if number == 1 else 600.
        S['reset_clear_target'] = [side, pos.y, pos.z]
        hit = cap_trace(world, cat, pos, u.Vector(*S['reset_clear_target']))
        check('P%d can walk aside before native reset' % number, not hit, hit_data(hit))
        S['segment_game_start'] = game
        phase('walk_clear_for_reset', world)
        return
    if S['phase'] == 'walk_clear_for_reset':
        result = walk_to(world, cat, u.Vector(*S['reset_clear_target']), 15.)
        if result == 'blocked':
            check('P%d physical reset clearance reachable' % number, False, vec(cat.get_actor_location()))
        if result == 'arrived':
            row['reset_cat_position'] = vec(cat.get_actor_location())
            check('P%d native ResetStatue succeeds after walking clear' % number,
                  puzzle.reset_statue(link.get_editor_property('PuzzleId')))
            phase('verify_reset', world)
        return
    if S['phase'] == 'verify_reset':
        if game - S['phase_game_start'] < .25:
            return
        row['restored_transform'] = statue.get_actor_transform().export_text()
        check('P%d reset restores exact initial statue transform' % number,
              row['restored_transform'] == row['initial_transform'], row['restored_transform'])
        check('P%d reset preserves original plate position' % number,
              (link.get_editor_property('Plate').get_actor_location() - u.Vector(*row['initial_plate'])).length() < .05)
        check('P%d reset clears pressed and completed flags' % number,
              not link.get_editor_property('bPressed') and not link.get_editor_property('bCompleted'))
        advance_case(world, cat)


def tick(_dt):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > .5:
                u.unregister_slate_post_tick_callback(S['handle'])
                SL.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - S['started'] < 240., 'Total runtime timeout'
        assert time.monotonic() - S['changed'] < 90., ('Phase timeout', S['phase'])
        world = ED.get_game_world()
        if world:
            step(world)
    except Exception:
        finish(traceback.format_exc())


assert '-SaveToUserDir' in SL.get_command_line(), 'Use isolated run_pie.ps1 process'
S['handle'] = u.register_slate_post_tick_callback(tick)
try:
    assert LE.load_level('/Game/Maps/Stage3')
    LE.editor_request_begin_play()
except Exception:
    finish(traceback.format_exc())
