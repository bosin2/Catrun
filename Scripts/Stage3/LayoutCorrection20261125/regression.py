"""Saved Stage3 layout regression using the native puzzle/interaction suite.

Observes live patrols, then disables NPC tick/collision for deterministic
fixtures. Walks the new exhibition bridge and left altar elbow/upper corridor.
This is not an unassisted campaign or enemy-difficulty playthrough. No asset,
map or user setting is saved. Run alone so animation sampling is not starved.
"""
import importlib.util
import os
import time
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
spec = importlib.util.spec_from_file_location(
    'layout_final_native', ROOT / 'Scripts/Stage3/GothicRevision/regression_final.py')
final = importlib.util.module_from_spec(spec)
spec.loader.exec_module(final)
test = final.test
suite = final.suite
pass_name = globals().get('OUTPUT_PASS', os.environ.get('CATRUN_LAYOUT_REGRESSION_PASS', 'Regression'))
assert pass_name.replace('_', '').isalnum()
output_area = globals().get('OUTPUT_AREA', 'Stage3LayoutCorrection20261125')
assert output_area in ('Stage3LayoutCorrection20261125', 'Stage3OrientationFix20261125')
test.OUT = ROOT / 'Saved' / output_area / pass_name
test.OUT.mkdir(parents=True, exist_ok=True)
assert not (test.OUT / 'report.json').exists(), 'Preserve previous regression evidence'
test.S['scope'] = __doc__
test.S['layout_route_checks'] = []

# Preserve the previous eight furniture-clearance samples, translating only
# those in the exhibition cohort. Add both directions of the new bridge.
plan_routes = [
    ('LobbyLeft', (-270, 250), (-270, 740)),
    ('LobbyRightGap', (625, 420), (625, 740)),
    ('LowerStrategy', (-210, 850), (-210, 1510)),
    ('LowerBench', (145, 1010), (145, 1450)),
    ('WarehouseNorthOpening', (1000, 1320), (1000, 1660)),
    ('WarehouseBenchFront', (610, 1320), (930, 1320)),
    ('ExhibitionLeftReturn', (-1050, 2038), (-1050, 1480)),
    ('ExhibitionShieldCorner', (-1050, 2040), (-920, 2040)),
    ('P1LeftDockBypass', (-900, 2050), (-900, 2350)),
    ('ExhibitionBridgeIntoRoom', (-300, 1425), (-600, 1425)),
    ('ExhibitionBridgeOutOfRoom', (-600, 1425), (-300, 1425)),
]


def configure_orientation(sign):
    assert sign in (-1, 1)
    test.PLAN_Y_SIGN = sign
    suite.routes = [(name, (a[0], test.plan_y(a[1])), (b[0], test.plan_y(b[1])))
                    for name, a, b in plan_routes]
    test.S['plan_y_sign'] = sign


configure_orientation(1)


def lookup(world):
    return {a.get_actor_label(): a for a in test.GS.get_all_actors_of_class(world, u.Actor)}


def check_dock(world, number):
    """Read the presenter's saved vectors, not the pre-translation JSON file."""
    presenter = lookup(world)['S3_GothicPresentation_Dock%d' % number]
    test.check('Dock%d presenter ticking' % number, presenter.is_actor_tick_enabled())
    test.check('Dock%d cosmetic latch reached closed state' % number,
               abs(presenter.get_editor_property('Alpha') - 1) < .001)
    for key in ('Fork', 'Pin', 'ChainTerminal'):
        actor = presenter.get_editor_property(key)
        expected = presenter.get_editor_property(key + 'Closed')
        error = (actor.get_actor_location() - expected).length()
        test.check('Dock%d %s closed pose' % (number, key), error < .05,
                   {'error_cm': error, 'actual': test.xyz(actor.get_actor_location()),
                    'expected': test.xyz(expected)})
        test.check('Dock%d %s remains nonblocking' % (number, key),
                   actor.static_mesh_component.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION)
    chain = presenter.get_editor_property('OpenChain').static_mesh_component
    test.check('Dock%d uses closed source chain' % number,
               chain.static_mesh.get_name() == 'SM_S3_DockShortChain')
    test.S['dock%d_checked' % number] = True


suite.check_dock = check_dock
native_move = test.move


def move(cat, x, y):
    # The sole fixed final-gate staging point in the inherited native suite.
    # Derive the translated center from the actual linked leaves instead.
    if x == -200 and y == test.plan_y(3720):
        world = test.ED.get_game_world()
        director = test.actors(world, u.CatrunStage3Objectives)[0]
        left = director.get_editor_property('FinalLeafLeft').get_actor_location()
        right = director.get_editor_property('FinalLeafRight').get_actor_location()
        x, y = (left.x + right.x) * .5, (left.y + right.y) * .5 - test.plan_y(280)
        test.S['final_gate_staging'] = [x, y]
    native_move(cat, x, y)


test.move = move
previous_step = test.step
elbow_routes = [
    ('MainEntryIntoAltar', (100, 1850), (100, 2025)),
    ('AltarLeftElbow', (100, 2025), (-250, 2025)),
    ('LeftElbowToUpper', (-250, 2025), (-250, 2220)),
    ('UpperPastD2', (-250, 2220), (-250, 2830)),
    ('UpperIntoGateHall', (-250, 2830), (-250, 3000)),
]


def walk_elbow(world, cat):
    if test.S.get('elbow_complete'):
        return True
    if 'elbow_index' not in test.S:
        test.S['elbow_index'] = 0
        test.S['elbow_state'] = 'start'
        ignored = test.actors(world, u.CatrunArmor) + test.actors(world, u.CatrunCandle)
        blocked = test.SL.capsule_trace_single_by_profile(
            world, u.Vector(-250, test.plan_y(2400), 26.2), u.Vector(150, test.plan_y(2400), 26.2),
            20., 26., 'Pawn', False, ignored, u.DrawDebugTrace.NONE, True)
        test.check('Upper corridor cannot directly shortcut into altar', bool(blocked))
    name, start, end = elbow_routes[test.S['elbow_index']]
    start, end = (start[0], test.plan_y(start[1])), (end[0], test.plan_y(end[1]))
    if test.S['elbow_state'] == 'start':
        test.move(cat, *start)
        test.S['elbow_game_start'] = test.GS.get_time_seconds(world)
        test.S['elbow_state'] = 'walk'
        test.S['changed'] = time.monotonic()
        return False
    pos = cat.get_actor_location()
    delta = u.Vector(end[0] - pos.x, end[1] - pos.y, 0)
    elapsed = test.GS.get_time_seconds(world) - test.S['elbow_game_start']
    if delta.length() < 15:
        row = {'route': name, 'start': start, 'end': end,
               'actual': test.xyz(pos), 'seconds': elapsed}
        test.S['layout_route_checks'].append(row)
        test.check('Corrected layout traversal ' + name, True, row)
        test.S['elbow_index'] += 1
        test.S['elbow_state'] = 'start'
        if test.S['elbow_index'] == len(elbow_routes):
            test.S['elbow_complete'] = True
            test.S['changed'] = time.monotonic()
            return True
        return False
    if elapsed > 18:
        test.check('Corrected layout traversal ' + name + ' not blocked', False,
                   {'actual': test.xyz(pos), 'end': end, 'seconds': elapsed})
    cat.add_movement_input(delta.normal(), 1., False)
    return False


def step(world):
    cat = test.GS.get_player_character(world, 0)
    if not cat:
        return
    phase = test.S['phase']
    if phase == 'wait_d2':
        puzzle = test.actors(world, u.CatrunStatuePuzzle)[0]
        links = puzzle.get_editor_property('Links')
        ready = (links[1].get_editor_property('bCompleted') and
                 'INACTIVE' in str(puzzle.get_editor_property('Reveal').get_editor_property('Phase')))
        if ready and not walk_elbow(world, cat):
            return
    if phase == 'walk_exit':
        if test.flow(world).get_editor_property('bStageComplete'):
            exit_actor = lookup(world)['S3_FinalExit']
            trigger = exit_actor.get_editor_property('Trigger')
            threshold = trigger.get_world_location().y - test.plan_y(trigger.get_scaled_box_extent().y + 5.)
            test.check('Physical walk through final gate completes Stage3',
                       test.PLAN_Y_SIGN * (cat.get_actor_location().y - threshold) > 0,
                       {'cat': test.xyz(cat.get_actor_location()), 'entry_threshold_y': threshold,
                        'exit_center': test.xyz(trigger.get_world_location())})
            test.shot(world, 'Completion')
            test.phase('complete_wait')
            return
        cat.add_movement_input(u.Vector(0, test.PLAN_Y_SIGN, 0), 1., False)
        return
    previous_step(world)


test.step = step
