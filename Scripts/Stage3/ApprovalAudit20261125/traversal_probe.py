"""Current-map traversal evidence; analysis only, never saves map or assets.

Observe ControlPatrol's unmodified native capsule/CharacterMovement and sound-
grid A* for two complete authored cycles. Other NPCs are disabled as fixtures.
Then freeze that armor too and walk the cat through isolated routes using input;
only each route's first, collision-checked staging point is relocated.
Portal sweeps and sampled widths are geometry evidence, not runtime success.
NavMesh is not used by ACatrunArmor. ExportBakedGridSnapshot omits runtime puzzle
clearance, so live puzzle bounds and actual native patrol are recorded separately.
"""
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_TRAVERSAL_PASS', 'TraversalCurrent')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3ApprovalAudit20261125' / PASS
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'report.json').exists(), 'Preserve previous evidence'
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS, SL = u.GameplayStatics, u.SystemLibrary
S = {'scope': __doc__, 'phase': 'startup', 'started': time.monotonic(),
     'changed': time.monotonic(), 'checks': [], 'portal_geometry': [],
     'cat_routes': [], 'armor_samples': [], 'armor_visits': [],
     'stage_relocations': [], 'packages_saved': False, 'margin_cm': 5.,
     'command_line': SL.get_command_line()}
LIVE = {}
PORTALS = [
    ('EntranceLobby', (150, -140), (150, -280), []),
    ('LobbyRightGap', (625, -420), (625, -740), []),
    ('ExhibitionBridge', (-300, -1425), (-600, -1425), []),
    ('WarehouseNorth', (1000, -1320), (1000, -1660), []),
    ('H1', (250, -440), (250, -560), []),
    ('H2', (600, -1740), (600, -1860), []),
    ('H3', (1100, -1740), (1100, -1860), []),
    ('D0Closed', (70, -650), (230, -650), []),
    ('D0FrameOnly', (70, -650), (230, -650), ['S3_D0']),
    ('D1Closed', (100, -1730), (100, -1870), []),
    ('D1FrameOnly', (100, -1730), (100, -1870), ['S3_D1_Bars']),
    ('AltarEntry', (100, -1850), (100, -2025), []),
    ('LeftAnnex', (100, -2025), (-250, -2025), []),
    ('D2Closed', (-250, -2220), (-250, -2380), []),
    ('D2FrameOnly', (-250, -2220), (-250, -2380), ['S3_D2_Bars']),
    ('UpperGateHall', (-250, -2820), (-250, -3000), []),
    ('AltarLWest', (150, -2100), (150, -2380), []),
    ('AltarLNorth', (150, -2380), (520, -2380), []),
    ('AltarLEast', (520, -2380), (520, -2140), []),
    ('AltarLSouth', (520, -2140), (150, -2140), []),
]
CAT_ROUTES = [
    ('AltarLClockwiseAndReturn', [(150, -2100), (150, -2380), (520, -2380),
      (520, -2140), (150, -2140), (150, -2100), (150, -2140), (520, -2140),
      (520, -2380), (150, -2380), (150, -2100)]),
    ('EntranceLobbyRoundTrip', [(150, -140), (150, -280), (150, -140)]),
    ('LobbyRightGapRoundTrip', [(625, -420), (625, -740), (625, -420)]),
    ('ExhibitionBridgeRoundTrip', [(-300, -1425), (-600, -1425), (-300, -1425)]),
    ('WarehouseNorthRoundTrip', [(1000, -1320), (1000, -1660), (1000, -1320)]),
    ('H1RoundTrip', [(250, -440), (250, -560), (250, -440)]),
    ('H2RoundTrip', [(600, -1740), (600, -1860), (600, -1740)]),
    ('H3RoundTrip', [(1100, -1740), (1100, -1860), (1100, -1740)]),
    ('AltarEntryElbowRoundTrip', [(100, -1850), (100, -2025), (-250, -2025),
      (-250, -2220), (-250, -2025), (100, -2025), (100, -1850)]),
    ('UpperGateHallRoundTrip', [(-250, -2820), (-250, -3000), (-250, -2820)]),
]


def v(point):
    return [point.x, point.y, point.z]


def hit_data(hit):
    return {k: str(value) for k, value in hit.to_dict().items()} if hit else None


def persist():
    (OUT / 'report.json').write_text(json.dumps(
        {k: val for k, val in S.items() if k != 'handle'}, ensure_ascii=False, indent=2), encoding='utf8')


def check(name, passed, detail=None):
    # A baseline audit keeps collecting after a failed route instead of hiding
    # other independent findings. Exceptions still terminate the harness.
    S['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
    persist()
    return bool(passed)


def phase(name, world):
    S['phase'] = name
    S['changed'] = time.monotonic()
    S['phase_game_start'] = GS.get_time_seconds(world)
    persist()


def finish(error=None):
    S['execution_complete'] = error is None
    S['all_runtime_checks_passed'] = error is None and all(c['passed'] for c in S['checks'])
    S['success'] = S['all_runtime_checks_passed']
    S['error'] = error
    S['phase'] = 'shutdown'
    S['changed'] = time.monotonic()
    persist()
    if ED.get_game_world():
        LE.editor_request_end_play()


def capsule_info(actor):
    cap = actor.get_component_by_class(u.CapsuleComponent)
    assert cap, actor.get_actor_label() + ' has no actual capsule'
    movement = actor.get_component_by_class(u.CharacterMovementComponent)
    center, extent = actor.get_actor_bounds(True, False)
    return {'actor': actor.get_actor_label(), 'class': actor.get_class().get_path_name(),
            'capsule': cap.get_path_name(), 'radius': cap.get_scaled_capsule_radius(),
            'half_height': cap.get_scaled_capsule_half_height(),
            'collision_profile': str(cap.get_collision_profile_name()),
            'collision_enabled': str(cap.get_collision_enabled()),
            'movement_class': movement.get_class().get_path_name() if movement else None,
            'colliding_bounds_center': v(center), 'colliding_bounds_extent': v(extent),
            'note': 'Movement capsule, not skeletal-mesh aggregate visual bounds.'}


def ignored_geometry(extra=()):
    return LIVE['pawns'] + [LIVE['actors'][name] for name in extra]


def sweep(world, a, b, shape, margin=0., extra=()):
    radius = shape['radius'] + margin
    half = max(radius, shape['half_height'])
    z = LIVE['floor_z'] + half + 2.2
    return SL.capsule_trace_single_by_profile(
        world, u.Vector(a[0], a[1], z), u.Vector(b[0], b[1], z), radius, half,
        'Pawn', False, ignored_geometry(extra), u.DrawDebugTrace.NONE, False)


def sample_width(world, a, b, shape, extra):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    side = u.Vector(-dy / length, dx / length, 0)
    rows = []
    for alpha in (.25, .5, .75):
        center = u.Vector(a[0] + dx * alpha, a[1] + dy * alpha,
                          LIVE['floor_z'] + shape['half_height'])
        distances = []
        for sign in (-1., 1.):
            end = center + side * (500. * sign)
            hit = SL.line_trace_single_by_profile(world, center, end, 'Pawn', False,
                                                  ignored_geometry(extra), u.DrawDebugTrace.NONE, False)
            distances.append((hit.to_dict()['impact_point'] - center).length() if hit else None)
        rows.append({'fraction': alpha, 'side_distances_cm': distances,
                     'width_cm': sum(distances) if all(d is not None for d in distances) else None})
    measured = [r['width_cm'] for r in rows if r['width_cm'] is not None]
    return {'samples': rows, 'minimum_sampled_width_cm': min(measured) if measured else None,
            'not_continuous_minimum': True, 'missing_hit_means_over_500cm_on_that_side': True}


def grid_cell(point):
    grid = LIVE['grid']
    x = math.floor((point.x - grid['Origin'][0]) / grid['CellSize'])
    y = math.floor((point.y - grid['Origin'][1]) / grid['CellSize'])
    if not (0 <= x < grid['Width'] and 0 <= y < grid['Height']):
        return {'outside_grid': True}
    i = y * grid['Width'] + x
    return {'index': i, 'xy': [x, y], 'walkable': grid['Walkable'][i],
            'wall_distance_cm': grid['WallDistance'][i], 'edge_mask': grid['EdgeMask'][i]}


def puzzle_obstacles():
    result = []
    puzzle = LIVE['actors']['S3_StatuePuzzles']
    for link in puzzle.get_editor_property('Links'):
        for key in ('Statue', 'Gate'):
            actor = link.get_editor_property(key)
            center, extent = actor.get_actor_bounds(False, False)
            result.append({'actor': actor.get_actor_label(), 'kind': key,
                           'min': v(center - extent), 'max': v(center + extent)})
    return result


def obstacle_clearance(point):
    distances = []
    for box in S['puzzle_obstacles']:
        lo, hi = box['min'], box['max']
        if hi[2] <= LIVE['floor_z'] + 4.:
            continue
        dx = max(lo[0] - point.x, 0., point.x - hi[0])
        dy = max(lo[1] - point.y, 0., point.y - hi[1])
        distances.append(math.hypot(dx, dy))
    return min(distances) if distances else None


def setup(world, cat):
    LIVE['actors'] = {a.get_actor_label(): a for a in GS.get_all_actors_of_class(world, u.Actor)}
    LIVE['pawns'] = list(GS.get_all_actors_of_class(world, u.Pawn))
    armor = LIVE['actors']['S3_Armor_ControlPatrol']
    LIVE['armor'] = armor
    LIVE['cat_shape'], LIVE['armor_shape'] = capsule_info(cat), capsule_info(armor)
    S['cat'], S['armor'] = LIVE['cat_shape'], LIVE['armor_shape']
    S['armor']['initial_location'] = v(armor.get_actor_location())
    S['armor']['native_movement_source'] = 'ACatrunArmor::TickWalking -> AddMovementInput -> CharacterMovement; no test movement commands'
    for cls in (u.CatrunArmor, u.CatrunCandle):
        for actor in GS.get_all_actors_of_class(world, cls):
            if actor != armor:
                actor.set_actor_tick_enabled(False)
                actor.set_actor_enable_collision(False)
    u.CatrunUserSettings.set_no_armor_capture_enabled(True)
    grid = LIVE['actors']['S3_SoundGrid']
    check('Saved sound grid exists', grid.has_grid())
    LIVE['grid'] = json.loads(grid.call_method('ExportBakedGridSnapshot'))
    (OUT / 'baked_grid.json').write_text(json.dumps(LIVE['grid']), encoding='utf8')
    LIVE['floor_z'] = grid.get_floor_z()
    settings = grid.get_editor_property('Settings')
    S['pathfinding'] = {'system': 'SoundGrid four-way A*, not Unreal NavMesh',
                        'armor_clearance_cm': settings.get_editor_property('ArmorClearance'),
                        'armor_turn_penalty': settings.get_editor_property('ArmorTurnPenalty'),
                        'grid_cell_cm': LIVE['grid']['CellSize'],
                        'dynamic_puzzle_clearance_exported': False,
                        'dynamic_evidence': 'Live obstacle bounds plus unmodified native patrol traversal'}
    S['puzzle_obstacles'] = puzzle_obstacles()
    points = list(armor.get_editor_property('PatrolPoints'))
    LIVE['patrol_points'] = points
    S['patrol_points'] = [{'actor': a.get_actor_label(), 'position': v(a.get_actor_location()),
                           'grid': grid_cell(a.get_actor_location())} for a in points]
    S['patrol_loop'] = armor.get_editor_property('bPatrolLoop')
    check('Control patrol has four current authored endpoints', len(points) == 4, S['patrol_points'])
    check('Control patrol native tick and collision remain enabled',
          armor.is_actor_tick_enabled() and armor.get_actor_enable_collision())
    for name, a, b, extra in PORTALS:
        row = {'portal': name, 'from': a, 'to': b, 'ignored_closed_leaf_geometry': extra,
               'scope': 'Queries only; a clear sweep is not a completed walk.'}
        for key, shape in [('cat', LIVE['cat_shape']), ('armor', LIVE['armor_shape'])]:
            hit = sweep(world, a, b, shape, 0., extra)
            margin = sweep(world, a, b, shape, S['margin_cm'], extra)
            row[key] = {'capsule_clear': not hit, 'sweep': hit_data(hit),
                        'capsule_plus_margin_clear': not margin, 'margin_sweep': hit_data(margin),
                        'lateral_geometry': sample_width(world, a, b, shape, extra)}
        S['portal_geometry'].append(row)
    S['armor_start_game'] = GS.get_time_seconds(world)
    S['armor_last_sample'] = -1.
    phase('observe_native_armor', world)


def observe_armor(world):
    game = GS.get_time_seconds(world)
    armor = LIVE['armor']
    pos = armor.get_actor_location()
    if game - S['armor_last_sample'] < .05:
        return
    S['armor_last_sample'] = game
    distances = [math.hypot(pos.x - a.get_actor_location().x, pos.y - a.get_actor_location().y)
                 for a in LIVE['patrol_points']]
    closest = min(range(len(distances)), key=lambda i: distances[i])
    if distances[closest] <= 50. and (not S['armor_visits'] or S['armor_visits'][-1]['point'] != closest):
        S['armor_visits'].append({'point': closest, 'time': game, 'distance_cm': distances[closest], 'position': v(pos)})
        persist()
    S['armor_samples'].append({'game_seconds': game, 'position': v(pos),
                               'action': str(armor.get_action()), 'has_destination': armor.has_destination(),
                               'velocity': v(armor.get_velocity()), 'nearest_point': closest,
                               'endpoint_distance_cm': distances[closest], 'baked_grid': grid_cell(pos),
                               'puzzle_bounds_clearance_cm': obstacle_clearance(pos)})
    visits = [r['point'] for r in S['armor_visits']]
    n = len(LIVE['patrol_points'])
    # Current saved map loops. Two full cycles require at least eight correct
    # consecutive transitions, not merely moving some distance near a corner.
    transitions = [(b - a) % n for a, b in zip(visits, visits[1:])]
    cycles = len(transitions) >= 2 * n and all(t == 1 for t in transitions)
    elapsed = game - S['armor_start_game']
    if cycles or elapsed > 100.:
        check('Armor native patrol completes two correctly ordered cycles', cycles,
              {'visits': S['armor_visits'], 'seconds': elapsed})
        positions = [r['position'] for r in S['armor_samples']]
        span_x = max(p[0] for p in positions) - min(p[0] for p in positions)
        span_y = max(p[1] for p in positions) - min(p[1] for p in positions)
        check('Armor native patrol crosses both axes around altar structure', span_x >= 300 and span_y >= 190,
              {'span_x_cm': span_x, 'span_y_cm': span_y})
        check('Armor actually uses walking native action',
              any('WALKING' in r['action'].upper() for r in S['armor_samples']))
        S['armor_observation_seconds'] = elapsed
        S['armor_test_status'] = 'passed native movement' if cycles else 'failed native patrol; inspect samples/log'
        armor.set_actor_tick_enabled(False)
        armor.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
        armor.set_actor_enable_collision(False)
        S['cat_route_index'] = 0
        start_cat_route(world)


def start_cat_route(world):
    if S['cat_route_index'] >= len(CAT_ROUTES):
        finish()
        return
    cat = GS.get_player_character(world, 0)
    cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    cat.consume_movement_input_vector()
    name, points = CAT_ROUTES[S['cat_route_index']]
    row = {'name': name, 'points': points, 'completed_segments': [], 'samples': []}
    S['cat_routes'].append(row)
    hit = sweep(world, points[0], points[0], LIVE['cat_shape'])
    if not check(name + ' safe staging capsule clear', not hit, hit_data(hit)):
        row['outcome'] = 'staging blocked; no relocation performed'
        S['cat_route_index'] += 1
        start_cat_route(world)
        return
    z = LIVE['floor_z'] + LIVE['cat_shape']['half_height'] + 2.2
    cat.set_actor_location(u.Vector(points[0][0], points[0][1], z), False, True)
    S['stage_relocations'].append({'route': name, 'point': [*points[0], z]})
    S['cat_waypoint'] = 1
    S['cat_segment_start'] = GS.get_time_seconds(world)
    phase('walk_cat', world)


def walk_cat(world, cat):
    row = S['cat_routes'][-1]
    game = GS.get_time_seconds(world)
    pos = cat.get_actor_location()
    target = row['points'][S['cat_waypoint']]
    delta = u.Vector(target[0] - pos.x, target[1] - pos.y, 0)
    row['samples'].append({'game_seconds': game, 'position': v(pos), 'waypoint': S['cat_waypoint'],
                           'last_input': v(cat.get_last_movement_input_vector())})
    if delta.length() < 3.:
        cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
        cat.consume_movement_input_vector()
        row['completed_segments'].append({'point': S['cat_waypoint'], 'actual': v(pos),
                                           'seconds': game - S['cat_segment_start']})
        S['cat_waypoint'] += 1
        S['cat_segment_start'] = game
        S['changed'] = time.monotonic()
        if S['cat_waypoint'] == len(row['points']):
            check(row['name'] + ' actual input-driven round trip completes', True, row['completed_segments'])
            row['outcome'] = 'physical round trip completed'
            S['cat_route_index'] += 1
            start_cat_route(world)
        return
    if game - S['cat_segment_start'] > 18.:
        check(row['name'] + ' actual input-driven round trip completes', False,
              {'failed_waypoint': S['cat_waypoint'], 'target': target, 'actual': v(pos),
               'distance_cm': delta.length()})
        row['outcome'] = 'blocked during actual movement'
        S['cat_route_index'] += 1
        start_cat_route(world)
        return
    cat.add_movement_input(delta.normal(), min(1., delta.length() / 60.), False)


def tick(_dt):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > .5:
                u.unregister_slate_post_tick_callback(S['handle'])
                SL.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - S['started'] < 600., 'Audit process timeout'
        world = ED.get_game_world()
        if not world:
            return
        cat = GS.get_player_character(world, 0)
        if not cat:
            return
        if S['phase'] == 'startup' and GS.get_time_seconds(world) > .2:
            setup(world, cat)
        elif S['phase'] == 'observe_native_armor':
            observe_armor(world)
        elif S['phase'] == 'walk_cat':
            walk_cat(world, cat)
    except Exception:
        finish(traceback.format_exc())


assert '-SaveToUserDir' in SL.get_command_line(), 'Run isolated run_pie.ps1 process'
S['handle'] = u.register_slate_post_tick_callback(tick)
try:
    assert LE.load_level('/Game/Maps/Stage3')
    LE.editor_request_begin_play()
except Exception:
    finish(traceback.format_exc())
