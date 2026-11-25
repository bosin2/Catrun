"""B1's three proposed openings: native armor two-round-trip tests only.

Reuses the unsaved B1 six-wall/E3 fixture. Every independent case has one
capsule-checked initial armor staging; thereafter only authored patrol targets
drive native A*/CharacterMovement. Warm-up ends at the opposite endpoint.
Four measured legs must physically cross the intended opening center plane
with the entire capsule inside its width. Other NPCs are disabled; cat stays
at its distant saved spawn. No package is saved; the map hash is checked.
"""
import importlib.util
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
SOURCE = ROOT / 'Scripts/Stage3/ApprovalAudit20261125/traversal_proposal_b.py'
PASS = os.environ.get('CATRUN_TRAVERSAL_PORTALS_PASS', 'TraversalProposalPortalsB1_01')
assert PASS.replace('_', '').isalnum()
source = SOURCE.read_text(encoding='utf8')
marker = "\nassert '-SaveToUserDir' in audit.SL.get_command_line()"
assert source.count(marker) == 1, 'Review changed B1 bootstrap before reuse'
spec = importlib.util.spec_from_file_location('b1_portal_fixture', SOURCE)
fixture = importlib.util.module_from_spec(spec)
old_pass = os.environ.get('CATRUN_TRAVERSAL_PROPOSAL_B_PASS')
os.environ['CATRUN_TRAVERSAL_PROPOSAL_B_PASS'] = PASS
try:
    exec(compile(source.split(marker, 1)[0], str(SOURCE), 'exec'), fixture.__dict__)
finally:
    if old_pass is None:
        os.environ.pop('CATRUN_TRAVERSAL_PROPOSAL_B_PASS', None)
    else:
        os.environ['CATRUN_TRAVERSAL_PROPOSAL_B_PASS'] = old_pass
audit = fixture.audit
audit.S['scope'] = __doc__
audit.S['portal_cases'] = []
audit.S['armor_initial_stagings'] = []

CASES = [
    {'name': 'Left125', 'points': [(45., -2312.5), (215., -2312.5)],
     'axis': 0, 'plane': 125., 'wall_span': [110., 140.], 'opening': [-2375., -2250.]},
    {'name': 'Right125', 'points': [(535., -2312.5), (715., -2312.5)],
     'axis': 0, 'plane': 625., 'wall_span': [610., 640.], 'opening': [-2375., -2250.]},
    {'name': 'LowerCenter230', 'points': [(375., -2025.), (375., -2200.)],
     'axis': 1, 'plane': -2115., 'wall_span': [-2130., -2100.], 'opening': [260., 490.]},
]
LIVE = {}


def configure_targets(armor, lookup, case):
    points = list(armor.get_editor_property('PatrolPoints'))
    assert len(points) == 4
    a, b = case['points']
    for actor, xy in zip(points, (a, b, a, b)):
        pos = actor.get_actor_location()
        actor.set_actor_location(u.Vector(xy[0], xy[1], pos.z), False, True)
    armor.set_editor_property('bPatrolLoop', True)


def setup(world, cat):
    lookup = {a.get_actor_label(): a for a in audit.GS.get_all_actors_of_class(world, u.Actor)}
    armor = lookup['S3_Armor_ControlPatrol']
    LIVE.update(actors=lookup, armor=armor, cat=cat)
    audit.LIVE['actors'] = lookup
    audit.LIVE['pawns'] = list(audit.GS.get_all_actors_of_class(world, u.Pawn))
    grid = lookup['S3_SoundGrid']
    audit.LIVE['floor_z'] = grid.get_floor_z()
    audit.LIVE['armor_shape'] = audit.capsule_info(armor)
    audit.S['armor'] = audit.LIVE['armor_shape']
    audit.S['cat_unchanged_spawn'] = audit.v(cat.get_actor_location())
    audit.check('Native armor has live capsule and CharacterMovement',
                isinstance(armor, u.Character) and bool(armor.get_component_by_class(u.CharacterMovementComponent)))
    audit.check('B1 fixture sound grid exists', grid.has_grid())
    settings = grid.get_editor_property('Settings')
    audit.S['pathfinding'] = {'system': 'Native SoundGrid four-way A*',
                              'clearance_cm': settings.get_editor_property('ArmorClearance'),
                              'turn_penalty': settings.get_editor_property('ArmorTurnPenalty')}
    for cls in (u.CatrunArmor, u.CatrunCandle):
        for actor in audit.GS.get_all_actors_of_class(world, cls):
            if actor != armor:
                actor.set_actor_tick_enabled(False)
                actor.set_actor_enable_collision(False)
    u.CatrunUserSettings.set_no_armor_capture_enabled(True)
    LIVE['case_index'] = 0
    begin_case(world)


def begin_case(world):
    if LIVE['case_index'] >= len(CASES):
        audit.finish()
        return
    case = CASES[LIVE['case_index']]
    armor = LIVE['armor']
    start, end = case['points']
    row = dict(case)
    row.update(samples=[], visits=[], legs=[], crossing_events=[],
               start_game=audit.GS.get_time_seconds(world), warmup_complete=False)
    audit.S['portal_cases'].append(row)
    shape = audit.LIVE['armor_shape']
    hit = audit.sweep(world, start, start, shape)
    clear = audit.check(case['name'] + ' safe initial capsule staging', not hit, audit.hit_data(hit))
    direct = audit.sweep(world, start, end, shape)
    margin = audit.sweep(world, start, end, shape, 5.)
    audit.check(case['name'] + ' actual capsule geometric passage', not direct, audit.hit_data(direct))
    audit.check(case['name'] + ' capsule plus5cm geometric passage', not margin, audit.hit_data(margin))
    if not clear:
        row['outcome'] = 'unsafe staging; case not started'
        LIVE['case_index'] += 1
        begin_case(world)
        return
    configure_targets(armor, LIVE['actors'], case)
    armor.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    armor.consume_movement_input_vector()
    pos = armor.get_actor_location()
    z = audit.LIVE['floor_z'] + shape['half_height'] + 2.4
    armor.set_actor_location(u.Vector(start[0], start[1], z), False, True)
    armor.set_actor_tick_enabled(True)
    armor.set_actor_enable_collision(True)
    audit.S['armor_initial_stagings'].append({'case': case['name'], 'before': audit.v(pos),
                                             'after': [*start, z], 'once_per_case': True})
    LIVE['previous'] = None
    row['warmup_scope'] = 'Native in-flight path cache may finish its prior leg. No measured visits until opposite endpoint is reached.'
    audit.phase('portal_native_patrol', world)


def finish_case(world, passed, reason):
    row = audit.S['portal_cases'][-1]
    audit.check(row['name'] + ' native two round trips through intended opening', passed,
                {'visits': row['visits'], 'legs': row['legs'], 'reason': reason,
                 'seconds': audit.GS.get_time_seconds(world) - row['start_game']})
    row['outcome'] = reason
    LIVE['armor'].get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    LIVE['case_index'] += 1
    begin_case(world)


def observe(world):
    armor = LIVE['armor']
    row = audit.S['portal_cases'][-1]
    game = audit.GS.get_time_seconds(world)
    pos = armor.get_actor_location()
    point = audit.v(pos)
    radius = audit.LIVE['armor_shape']['radius']
    axis = row['axis']
    side_axis = 1 - axis
    distances = [math.hypot(pos.x - xy[0], pos.y - xy[1]) for xy in row['points']]
    near = min(range(2), key=lambda i: distances[i])
    # Endpoint acceptance is <=30cm (25cm grid snapping + native corner stop)
    # AND the whole capsule is beyond the wall slab. A center-plane touch
    # cannot count as a completed traversal.
    endpoint_axis = row['points'][near][axis]
    positive_side = endpoint_axis > row['plane']
    fully_across = (point[axis] - radius >= row['wall_span'][1] - .5 if positive_side
                    else point[axis] + radius <= row['wall_span'][0] + .5)
    reached = distances[near] <= 30. and fully_across
    if not row['warmup_complete'] and near == 1 and reached:
        row['warmup_complete'] = True
        row['measured_start_game'] = game
        row['leg_events'] = []
        row['visits'].append({'endpoint': 1, 'time': game, 'position': point, 'distance_cm': distances[1]})
        audit.persist()
    previous = LIVE['previous']
    if row['warmup_complete'] and previous:
        before = previous[axis] - row['plane']
        after = point[axis] - row['plane']
        if (before < 0. <= after) or (before > 0. >= after):
            alpha = (row['plane'] - previous[axis]) / (point[axis] - previous[axis])
            side = previous[side_axis] + alpha * (point[side_axis] - previous[side_axis])
            valid = row['opening'][0] + radius - .5 <= side <= row['opening'][1] - radius + .5
            event = {'time': game, 'direction': 1 if after > before else -1,
                     'crossing_side_coordinate': side, 'plane_coordinate': row['plane'],
                     'whole_capsule_inside_opening': valid,
                     'surface_clearance_cm': min(side - row['opening'][0], row['opening'][1] - side) - radius}
            row['crossing_events'].append(event)
            row['leg_events'].append(event)
    if row['warmup_complete'] and reached and near != row['visits'][-1]['endpoint']:
        previous_endpoint = row['visits'][-1]['endpoint']
        expected_direction = 1 if row['points'][near][axis] > row['points'][previous_endpoint][axis] else -1
        events = row['leg_events']
        valid = (bool(events) and all(event['whole_capsule_inside_opening'] for event in events)
                 and any(event['direction'] == expected_direction for event in events))
        leg = {'from': previous_endpoint, 'to': near, 'time': game, 'actual_endpoint': point,
               'crossings': events, 'physically_crossed_intended_opening': valid}
        row['legs'].append(leg)
        audit.check(row['name'] + ' measured native leg%d crosses opening' % len(row['legs']), valid, leg)
        row['visits'].append({'endpoint': near, 'time': game, 'position': point, 'distance_cm': distances[near]})
        row['leg_events'] = []
        if len(row['legs']) == 4:
            finish_case(world, all(leg['physically_crossed_intended_opening'] for leg in row['legs']),
                        'four native legs / two round trips completed with crossing-coordinate evidence')
            return
    if not row['samples'] or game - row['samples'][-1]['time'] >= .05:
        row['samples'].append({'time': game, 'position': point, 'velocity': audit.v(armor.get_velocity()),
                               'action': str(armor.get_action()), 'measured': row['warmup_complete']})
    LIVE['previous'] = point
    if game - row['start_game'] > 95.:
        finish_case(world, False, 'native route timeout; no forced path completion')


def tick(_dt):
    try:
        if audit.S['phase'] == 'shutdown':
            if not audit.ED.get_game_world() and time.monotonic() - audit.S['changed'] > .5:
                u.unregister_slate_post_tick_callback(audit.S['handle'])
                audit.SL.execute_console_command(audit.ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - audit.S['started'] < 480., 'Portal test process timeout'
        world = audit.ED.get_game_world()
        if not world:
            return
        cat = audit.GS.get_player_character(world, 0)
        if not cat:
            return
        if audit.S['phase'] == 'startup' and audit.GS.get_time_seconds(world) > .2:
            setup(world, cat)
        elif audit.S['phase'] == 'portal_native_patrol':
            observe(world)
    except Exception:
        audit.finish(traceback.format_exc())


assert '-SaveToUserDir' in audit.SL.get_command_line()
audit.S['handle'] = u.register_slate_post_tick_callback(tick)
try:
    assert audit.LE.load_level('/Game/Maps/Stage3')
    fixture.prepare_proposal()
    audit.LE.editor_request_begin_play()
except Exception:
    audit.finish(traceback.format_exc())
