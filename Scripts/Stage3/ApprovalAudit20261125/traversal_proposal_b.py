"""Unsaved proposal B1 fixture over the actual saved Stage3 map.

Six temporary 30cm walls replace the old central L only in this editor process.
The lower brackets are the proposed interpretation of the 1.5m structures, not
an approved map change. E3's local assembly moves 50cm toward canonical +Y;
the gate LockBolt stays fixed. Native E3 interaction regression is deferred to
the implementation after approval; this fixture tests geometry and traversal.
An initial armor placement seeds each independent route. All observed armor
movement remains native. No map, asset or settings package is ever saved.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
SOURCE = ROOT / 'Scripts/Stage3/ApprovalAudit20261125/traversal_probe.py'
MAP = ROOT / 'Content/Maps/Stage3.umap'
BEFORE_HASH = hashlib.sha256(MAP.read_bytes()).hexdigest()
PASS = os.environ.get('CATRUN_TRAVERSAL_PROPOSAL_B_PASS', 'TraversalProposalB1_01')
assert PASS.replace('_', '').isalnum()

# Reuse the baseline's definitions without its bootstrap, so editor fixtures
# are prepared after load and before the one PIE launch. No baseline file edits.
source = SOURCE.read_text(encoding='utf8')
marker = "\nassert '-SaveToUserDir' in SL.get_command_line()"
assert source.count(marker) == 1, 'Baseline bootstrap changed; review wrapper'
definitions = source.split(marker, 1)[0]
spec = importlib.util.spec_from_file_location('proposal_b_traversal', SOURCE)
audit = importlib.util.module_from_spec(spec)
old_pass = os.environ.get('CATRUN_TRAVERSAL_PASS')
os.environ['CATRUN_TRAVERSAL_PASS'] = PASS
try:
    exec(compile(definitions, str(SOURCE), 'exec'), audit.__dict__)
finally:
    if old_pass is None:
        os.environ.pop('CATRUN_TRAVERSAL_PASS', None)
    else:
        os.environ['CATRUN_TRAVERSAL_PASS'] = old_pass

audit.S['scope'] = __doc__
audit.S['fixture'] = {'proposal': 'B1; unapproved lower-bracket interpretation',
                     'saved_map_sha256_before': BEFORE_HASH,
                     'wall_thickness_cm': 30., 'wall_height_cm': 300.,
                     'old_structure_disabled': [], 'new_walls': [],
                     'e3_modified': True,
                     'e3_scope': 'Local Housing/Ring/Pin/Pulley/short chains/visual children move worldY-50. Gate-side LockBolt fixed. Native pull interaction not tested.'}

BOXES = [
    ('UpperLeft', (110, 2375, 140, 2550)),
    ('UpperRight', (610, 2375, 640, 2550)),
    ('LowerLeftVertical', (110, 2100, 140, 2250)),
    ('LowerLeftHorizontal', (110, 2100, 260, 2130)),
    ('LowerRightVertical', (610, 2100, 640, 2250)),
    ('LowerRightHorizontal', (490, 2100, 640, 2130)),
]
PATROL = [(550, 2190), (550, 2380), (200, 2380), (200, 2190)]

# Replace only the old central-L query routes. The other baseline portals keep
# their actual saved geometry. Ignored gate leaves remain explicitly labelled.
audit.PORTALS = [p for p in audit.PORTALS if not p[0].startswith('AltarL')]
audit.PORTALS += [
    ('BLeftSide125', (40, -2312.5), (220, -2312.5), []),
    ('BRightSide125', (550, -2312.5), (730, -2312.5), []),
    ('BLowerCenter230', (375, -2030), (375, -2160), []),
    ('BLeftOuterActual', (45, -2010), (45, -2290), []),
    ('BLowerFrontActual', (40, -2025), (800, -2025), []),
    ('BP2Left60', (670, -2050), (670, -2300), []),
    ('BP2Right100', (870, -2050), (870, -2300), []),
    ('BPatrolBottomE3', (200, -2190), (550, -2190), []),
    ('BPatrolRight', (550, -2190), (550, -2380), []),
    ('BPatrolTop', (550, -2380), (200, -2380), []),
    ('BPatrolLeft', (200, -2380), (200, -2190), []),
]
audit.CAT_ROUTES = [r for r in audit.CAT_ROUTES if r[0] != 'AltarLClockwiseAndReturn']
audit.CAT_ROUTES = [
    ('BInteriorClockwiseAndReturn', [(200, -2190), (550, -2190), (550, -2380),
      (200, -2380), (200, -2190), (200, -2380), (550, -2380), (550, -2190), (200, -2190)]),
    ('BLeftSide125RoundTrip', [(40, -2312.5), (220, -2312.5), (40, -2312.5)]),
    ('BRightSide125RoundTrip', [(550, -2312.5), (730, -2312.5), (550, -2312.5)]),
    ('BLowerCenter230RoundTrip', [(375, -2030), (375, -2160), (375, -2030)]),
    ('BLeftOuterRoundTrip', [(45, -2010), (45, -2290), (45, -2010)]),
    ('BP2Left60CatRoundTrip', [(670, -2050), (670, -2300), (670, -2050)]),
    ('BP2Right100CatRoundTrip', [(870, -2050), (870, -2300), (870, -2050)]),
] + audit.CAT_ROUTES


def prepare_proposal():
    """Editor-memory fixture only; never invokes a save or edits source assets."""
    assert not audit.ED.get_game_world()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    lookup = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
    report_path = ROOT / 'Saved/Stage3GothicRevision20261125/occlusion_report.json'
    groups = json.loads(report_path.read_text(encoding='utf8'))['groups']
    old = set()
    for name in ('S3_Wall_0126', 'S3_Wall_0127'):
        assert name in groups and name in lookup
        old.add(name)
        old.update(groups[name]['members'])
    for label in sorted(old):
        actor = lookup[label]
        actor.set_actor_enable_collision(False)
        actor.set_actor_hidden_in_game(True)
        for component in actor.get_components_by_class(u.PrimitiveComponent):
            component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            component.set_visibility(False, True)
        audit.S['fixture']['old_structure_disabled'].append(label)
    cube = u.load_asset('/Engine/BasicShapes/Cube')
    assert cube
    for suffix, rect in BOXES:
        x0, y0, x1, y1 = rect
        label = 'S3_ApprovalProposalB_' + suffix
        assert label not in lookup
        location = u.Vector((x0 + x1) * .5, -(y0 + y1) * .5, 150.)
        actor = actors.spawn_actor_from_class(u.StaticMeshActor, location, u.Rotator())
        assert actor
        actor.set_actor_label(label)
        component = actor.static_mesh_component
        component.set_static_mesh(cube)
        component.set_collision_profile_name('BlockAll')
        component.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS)
        actor.set_actor_scale3d(u.Vector((x1 - x0) / 100., (y1 - y0) / 100., 3.))
        center, extent = actor.get_actor_bounds(True, False)
        audit.S['fixture']['new_walls'].append({'actor': label, 'canonical_bounds': list(rect),
                                               'world_min': audit.v(center - extent),
                                               'world_max': audit.v(center + extent)})
    armor = lookup['S3_Armor_ControlPatrol']
    director = lookup['S3_Objectives']
    bolt = director.get_editor_property('Devices')[2].get_editor_property('LockBolt')
    bolt_before = bolt.get_actor_transform().export_text()
    roots = {a for name, a in lookup.items() if name.startswith('S3_Release3_') and a != bolt}
    selected = set(roots)
    # Include attached presentation children without shifting them twice.
    for actor in lookup.values():
        parent = actor.get_attach_parent_actor()
        while parent:
            if parent in roots:
                selected.add(actor)
                break
            parent = parent.get_attach_parent_actor()
    before = {a: a.get_actor_location() for a in selected}
    def depth(actor):
        result = 0
        parent = actor.get_attach_parent_actor()
        while parent:
            result += 1
            parent = parent.get_attach_parent_actor()
        return result
    moved = []
    for actor in sorted(selected, key=depth):
        pos = before[actor]
        target = pos + u.Vector(0, -50, 0)
        actor.set_actor_location(target, False, True)
        moved.append({'actor': actor.get_actor_label(), 'before': audit.v(pos), 'after': audit.v(target)})
    assert bolt.get_actor_transform().export_text() == bolt_before
    audit.S['fixture']['e3_moved_actors'] = moved
    audit.S['fixture']['fixed_lock_bolt'] = {'actor': bolt.get_actor_label(), 'transform': bolt_before}
    points = list(armor.get_editor_property('PatrolPoints'))
    assert len(points) == len(PATROL)
    original = []
    for actor, (x, y) in zip(points, PATROL):
        p = actor.get_actor_location()
        original.append({'actor': actor.get_actor_label(), 'before': audit.v(p), 'after': [x, -y, p.z]})
        actor.set_actor_location(u.Vector(x, -y, p.z), False, True)
    armor.set_editor_property('bPatrolLoop', True)
    p = armor.get_actor_location()
    audit.S['fixture']['armor_initial_staging'] = {'before': audit.v(p), 'after': [550., -2190., p.z],
                                                 'reason': 'Original capsule intersects new lower-right bracket; one pre-PIE safe start only.'}
    armor.set_actor_location(u.Vector(550, -2190, p.z), False, True)
    audit.S['fixture']['patrol_point_changes'] = original
    grid = lookup['S3_SoundGrid']
    grid.build_grid()
    assert grid.has_grid()
    audit.S['fixture']['grid_rebuilt_in_memory'] = True
    audit.S['fixture']['saved_map_sha256_after_fixture'] = hashlib.sha256(MAP.read_bytes()).hexdigest()
    assert audit.S['fixture']['saved_map_sha256_after_fixture'] == BEFORE_HASH
    audit.persist()


baseline_setup = audit.setup


def setup(world, cat):
    baseline_setup(world, cat)
    queries = {r['portal']: r for r in audit.S['portal_geometry']}
    for name in ('BLeftSide125', 'BRightSide125', 'BLowerCenter230'):
        for shape in ('cat', 'armor'):
            audit.check(name + ' ' + shape + ' actual capsule plus5cm margin clears',
                        queries[name][shape]['capsule_plus_margin_clear'], queries[name][shape])
    audit.check('P2 sixty-cm left gap admits cat capsule', queries['BP2Left60']['cat']['capsule_clear'])
    audit.check('P2 sixty-cm left gap intentionally rejects seventy-cm armor',
                not queries['BP2Left60']['armor']['capsule_clear'], queries['BP2Left60']['armor'])
    audit.check('P2 hundred-cm right gap admits armor plus5cm margin',
                queries['BP2Right100']['armor']['capsule_plus_margin_clear'], queries['BP2Right100']['armor'])
    audit.S['fixture']['e3_bottom_route_query'] = queries['BPatrolBottomE3']
    audit.persist()


audit.setup = setup
baseline_check = audit.check


def check(name, passed, detail=None):
    if name == 'Armor native patrol crosses both axes around altar structure':
        # The B1 authored rectangle is 350x190, shorter than the current 370x280
        # route. Retain two correctly ordered native cycles and use its measured
        # grid/turn tolerance for this secondary span check.
        tolerance = 2. * (audit.LIVE['armor'].get_editor_property('CornerTolerance')
                          + audit.LIVE['grid']['CellSize'] * .5)
        required_x, required_y = 350. - tolerance, 190. - tolerance
        detail.update(required_span_x_cm=required_x, required_span_y_cm=required_y,
                      grid_and_corner_tolerance_cm=tolerance)
        passed = detail['span_x_cm'] >= required_x and detail['span_y_cm'] >= required_y
    return baseline_check(name, passed, detail)


audit.check = check
baseline_start_cat_route = audit.start_cat_route
baseline_observe_armor = audit.observe_armor


def start_cat_route(world):
    if audit.S.get('b1_right_lane_started'):
        baseline_start_cat_route(world)
        return
    audit.S['b1_right_lane_started'] = True
    armor = audit.LIVE['armor']
    start, end = (870., -2050.), (870., -2300.)
    hit = audit.sweep(world, start, start, audit.LIVE['armor_shape'])
    if not audit.check('B1 P2 right-lane independent armor staging clear', not hit, audit.hit_data(hit)):
        baseline_start_cat_route(world)
        return
    # The first loop has finished; seed a separate route once, then let the
    # existing native PatrolIndex/path planner consume its changed point actors.
    for point, xy in zip(audit.LIVE['patrol_points'], (start, end, start, end)):
        p = point.get_actor_location()
        point.set_actor_location(u.Vector(xy[0], xy[1], p.z), False, True)
    p = armor.get_actor_location()
    z = audit.LIVE['floor_z'] + audit.LIVE['armor_shape']['half_height'] + 2.4
    armor.set_actor_location(u.Vector(start[0], start[1], z), False, True)
    armor.set_actor_enable_collision(True)
    armor.set_actor_tick_enabled(True)
    audit.S['b1_right_lane'] = {'initial_staging': {'before': audit.v(p), 'after': [*start, z]},
                               'points': [start, end], 'visits': [], 'samples': [],
                               'start_game': audit.GS.get_time_seconds(world),
                               'scope': 'One independent initial placement; native planner warm-up until far endpoint, then two measured round trips without relocation.'}
    audit.S['b1_right_lane_active'] = True
    audit.phase('observe_native_armor', world)


def observe_armor(world):
    if not audit.S.get('b1_right_lane_active'):
        baseline_observe_armor(world)
        return
    armor = audit.LIVE['armor']
    row = audit.S['b1_right_lane']
    game = audit.GS.get_time_seconds(world)
    if row['samples'] and game - row['samples'][-1]['game_seconds'] < .05:
        return
    p = armor.get_actor_location()
    distances = [((p.x - xy[0]) ** 2 + (p.y - xy[1]) ** 2) ** .5 for xy in row['points']]
    near = min(range(2), key=lambda i: distances[i])
    # The native planner may finish its in-flight old leg once after the fixture
    # changes targets. Record that warm-up, but count neither it nor the initial
    # placement as a completed lane traversal.
    if near == 1 and distances[near] < 35. and 'measured_start_game' not in row:
        row['measured_start_game'] = game
    measuring = 'measured_start_game' in row
    if measuring and distances[near] < 35. and (not row['visits'] or row['visits'][-1]['point'] != near):
        row['visits'].append({'point': near, 'game_seconds': game, 'position': audit.v(p),
                              'distance_cm': distances[near]})
    row['samples'].append({'game_seconds': game, 'position': audit.v(p),
                           'measured': measuring, 'action': str(armor.get_action()), 'velocity': audit.v(armor.get_velocity())})
    passed = len(row['visits']) >= 5
    if passed or game - row['start_game'] > 70.:
        audit.check('B1 P2 hundred-cm right lane actual armor native patrol two round trips', passed,
                    {'visits': row['visits'], 'seconds': game - row['start_game']})
        measured = [sample for sample in row['samples'] if sample['measured']]
        audit.check('B1 P2 measured armor traversals stay inside the right lane',
                    bool(measured) and all(854.5 <= sample['position'][0] <= 885.5 for sample in measured),
                    {'center_x_min': min((s['position'][0] for s in measured), default=None),
                     'center_x_max': max((s['position'][0] for s in measured), default=None),
                     'capsule_radius': audit.LIVE['armor_shape']['radius'], 'physical_gap_x': [820, 920]})
        row['outcome'] = 'actual native round trips completed' if passed else 'native right-lane route failed'
        armor.set_actor_tick_enabled(False)
        armor.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
        armor.set_actor_enable_collision(False)
        audit.S['b1_right_lane_active'] = False
        baseline_start_cat_route(world)


audit.start_cat_route = start_cat_route
audit.observe_armor = observe_armor
baseline_finish = audit.finish


def finish(error=None):
    after = hashlib.sha256(MAP.read_bytes()).hexdigest()
    audit.S['fixture']['saved_map_sha256_after_test'] = after
    audit.check('Saved Stage3 map bytes remain unchanged throughout proposal test', after == BEFORE_HASH,
                {'before': BEFORE_HASH, 'after': after})
    baseline_finish(error)


audit.finish = finish
assert '-SaveToUserDir' in audit.SL.get_command_line(), 'Use isolated run_pie.ps1 process'
audit.S['handle'] = u.register_slate_post_tick_callback(audit.tick)
try:
    assert audit.LE.load_level('/Game/Maps/Stage3')
    prepare_proposal()
    audit.LE.editor_request_begin_play()
except Exception:
    import traceback
    finish(traceback.format_exc())
