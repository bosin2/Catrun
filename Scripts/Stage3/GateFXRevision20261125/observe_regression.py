"""Root-run isolated PIE: existing native 188-check suite plus cosmetic evidence.

Observer never triggers the effect directly. Native statue seating and three
physical device pulls from the inherited suite open D1/D2. Fixtures/staging in
that suite remain disclosed; this is not a manual playthrough. Reset mid-burst
is a separate follow-up test, not claimed by this observer.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('CATRUN_GATE_FX_TEST_PASS', 'Regression01')
assert PASS.replace('_', '').isalnum()
OUT = ROOT / 'Saved/Stage3GateFXRevision20261125' / PASS
assert not OUT.exists(), 'Preserve previous evidence'
OUT.mkdir(parents=True)
paths = [ROOT / 'Content/Maps' / (s + '.umap') for s in ('Stage1', 'Stage2', 'Stage3')]
paths += list((ROOT / 'Content/Systems/Interaction/Puzzles/Presentation').glob('*.uasset'))
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
# Underlying wrapper creates an empty output directory before our redirection.
os.environ['CATRUN_ORIENTATION_REGRESSION_PASS'] = 'GateFX_' + PASS
spec = importlib.util.spec_from_file_location('s3_gate_fx_native_suite',
                                             ROOT / 'Scripts/Stage3/OrientationFix20261125/regression.py')
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)
test = suite.test
test.OUT = OUT
test.S['scope'] = __doc__
test.S.pop('expected_checks', None)
old_step, old_finish = test.step, test.finish
data = {'scope': __doc__, 'frames': [], 'initial': {}, 'timing': {},
        'protected_hashes_before': hashes, 'runtime_verified': False}
errors = set()
original_move = test.move


def read_reveal_tuning(reveal):
    result = {key: reveal.get_editor_property(key) for key in
              ('CameraTravelTime', 'CameraReturnTime', 'MaximumLockTime', 'bPreserveGameplayFraming')}
    offset = reveal.get_editor_property('GateCameraOffset')
    result['GateCameraOffset'] = [offset.x, offset.y, offset.z]
    return result


def final_geometry(world):
    """Actual linked leaves and exit trigger; no old terminal coordinates."""
    lookup = suite.layout.lookup(world)
    director = lookup['S3_Objectives']
    left = director.get_editor_property('FinalLeafLeft').get_actor_location()
    right = director.get_editor_property('FinalLeafRight').get_actor_location()
    center = (left + right) * .5
    trigger = lookup['S3_FinalExit'].get_editor_property('Trigger')
    goal = trigger.get_world_location()
    direction = u.Vector(goal.x - center.x, goal.y - center.y, 0).normal()
    assert direction.length() > .99, 'Final gate and exit need a distinct passage axis'
    return center, goal, direction, trigger


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def move(cat, x, y):
    # The inherited native suite reaches this call only after D2 and all elbow
    # walks. Replace its old staging input by current actor geometry, not by a
    # coordinate sentinel. Other fixtures retain their original native checks.
    if test.S['phase'] == 'wait_d2' and test.S.get('elbow_complete'):
        center, goal, direction, _ = final_geometry(test.ED.get_game_world())
        approach = center - direction * 280.
        cap = cat.get_component_by_class(u.CapsuleComponent)
        approach.z = cap.get_scaled_capsule_half_height() + .25
        hit = test.SL.capsule_trace_single_by_profile(test.ED.get_game_world(), approach,
                approach + u.Vector(0, 0, .1), cap.get_scaled_capsule_radius(),
                cap.get_scaled_capsule_half_height(), 'Pawn', False, [cat], u.DrawDebugTrace.NONE, True)
        test.check('Current terminal gate approach staging is clear', not hit, test.xyz(approach))
        test.S['final_gate_staging'] = test.xyz(approach)
        test.S['current_final_gate_center'] = test.xyz(center)
        test.S['current_final_exit_center'] = test.xyz(goal)
        suite.layout.native_move(cat, approach.x, approach.y)
        return
    original_move(cat, x, y)


test.move = move


def configure_saved_geometry(lookup):
    """Append actual saved B1 opening walks; all original routes remain."""
    def box(suffix):
        actor = lookup['S3_Wall_Altar_' + suffix]
        center, extent = actor.get_actor_bounds(True, False)
        return center - extent, center + extent

    boxes = {suffix: box(suffix) for suffix in ('UpperLeft', 'UpperRight',
             'LowerLeftVertical', 'LowerLeftHorizontal', 'LowerRightVertical', 'LowerRightHorizontal')}
    records, routes = {}, []
    for side in ('Left', 'Right'):
        upper, lower = boxes['Upper' + side], boxes['Lower' + side + 'Vertical']
        y = (upper[1].y + lower[0].y) * .5
        opening = lower[0].y - upper[1].y
        test.check('Saved B1 ' + side + ' side opening is 125cm', abs(opening - 125.) < .1, opening)
        a = (lower[0].x - 75., y)
        b = (lower[1].x + 75., y)
        routes.extend([('B1' + side + 'OpeningOut', a, b), ('B1' + side + 'OpeningBack', b, a)])
        records[side] = {'width_cm': opening, 'start': a, 'end': b}
    left, right = boxes['LowerLeftHorizontal'], boxes['LowerRightHorizontal']
    gap = right[0].x - left[1].x
    test.check('Saved B1 lower central opening is 230cm', abs(gap - 230.) < .1, gap)
    x = (right[0].x + left[1].x) * .5
    a, b = (x, max(left[1].y, right[1].y) + 75.), (x, min(left[0].y, right[0].y) - 70.)
    routes.extend([('B1LowerOpeningIn', a, b), ('B1LowerOpeningBack', b, a)])
    records['Lower'] = {'width_cm': gap, 'start': a, 'end': b}
    suite.layout.suite.routes.extend(routes)
    device = lookup['S3_Objectives'].get_editor_property('Devices')[2]
    records['E3'] = {key: test.xyz(device.get_editor_property(key).get_actor_location())
                     for key in ('Housing', 'Ring', 'LockBolt')}
    records['native_release_position_source'] = 'Inherited suite derives front/rear from actual Housing axes and location'
    test.S['current_saved_B1_geometry'] = records
    data['saved_geometry_configured'] = True


def require(name, ok, detail=None):
    if not ok and name not in errors:
        errors.add(name)
        test.check(name, False, detail)


def read(actor):
    cards = [actor.get_editor_property('Dust%02d' % i) for i in range(8)]
    mid = actor.get_editor_property('RumbleMID')
    return {'count': actor.get_editor_property('ImpactCount'),
            'age': actor.get_editor_property('ImpactAge'),
            'active': actor.get_editor_property('DustActive'),
            'armed': actor.get_editor_property('Armed'),
            'shown': sum(not c.get_editor_property('hidden_in_game') for c in cards),
            'rumble': mid.get_scalar_parameter_value('Rumble') if mid else None,
            'components': len(actor.get_components_by_class(u.ActorComponent)),
            'collision_free': all(c.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION
                                  and not c.get_editor_property('generate_overlap_events') for c in cards)}


def step(world):
    game = test.GS.get_time_seconds(world)
    if game >= 1.:
        lookup = {a.get_actor_label(): a for a in test.GS.get_all_actors_of_class(world, u.Actor)}
        if not data.get('saved_geometry_configured'):
            configure_saved_geometry(lookup)
        presenters = [lookup.get('S3_GateImpact_D%d' % n) for n in (1, 2)]
        require('Both saved Stage3 gate FX presenters exist', all(presenters))
        puzzle = lookup['S3_StatuePuzzles']
        reveal = puzzle.get_editor_property('Reveal')
        phase = str(reveal.get_editor_property('Phase'))
        links = puzzle.get_editor_property('Links')
        tuning = read_reveal_tuning(reveal)
        if not data['timing']:
            data['timing'] = tuning
        require('Gate effect preserves native reveal tuning', tuning == data['timing'])
        frame = {'game': game, 'native_phase': phase, 'gates': []}
        for index, actor in enumerate(presenters):
            row = read(actor)
            label = actor.get_actor_label()
            row.update(label=label, native_completed=links[index].get_editor_property('bCompleted'),
                       native_offset=links[index].get_editor_property('GateOffset'),
                       gate_z=actor.get_editor_property('Gate').get_actor_location().z,
                       expected_z=actor.get_editor_property('ExpectedOpenZ'))
            if label not in data['initial']:
                data['initial'][label] = row.copy()
                test.check(label + ' BeginPlay remains silent',
                           row['count'] == 0 and not row['active'] and row['shown'] == 0 and row['rumble'] == 0, row)
            require(label + ' fixed pool and no gameplay collision', row['collision_free']
                    and row['components'] == data['initial'][label]['components'], row)
            require(label + ' never loops or fires twice', row['count'] in (0, 1), row)
            if row['count']:
                require(label + ' triggers only at actual recessed completion', row['native_completed']
                        and row['gate_z'] <= row['expected_z'] + .5, row)
            if row['active']:
                require(label + ' finite visible dust pool', row['age'] < .78 and row['shown'] == 8, row)
                require(label + ' finite bounded rumble', row['rumble'] is not None
                        and 0 <= row['rumble'] <= .000551, row)
                if row['age'] >= .26:
                    require(label + ' rumble ends by 0.26 seconds', abs(row['rumble']) < 1e-8, row)
            else:
                require(label + ' inactive dust and rumble are zero', row['shown'] == 0 and row['rumble'] == 0, row)
            if 'INACTIVE' in phase:
                require(label + ' native Inactive terminates effects', not row['active'] and not row['armed'], row)
            frame['gates'].append(row)
        if not data['frames'] or game != data['frames'][-1]['game']:
            data['frames'].append(frame)
    if test.S['phase'] == 'walk_exit':
        cat = test.GS.get_player_character(world, 0)
        if cat:
            _, goal, direction, trigger = final_geometry(world)
            if test.flow(world).get_editor_property('bStageComplete'):
                extent = trigger.get_scaled_box_extent()
                forward, right = trigger.get_forward_vector(), trigger.get_right_vector()
                half = abs(dot(direction, forward)) * extent.x + abs(dot(direction, right)) * extent.y
                position = cat.get_actor_location()
                signed_distance = dot(position - goal, direction)
                test.check('Physical walk through final gate completes Stage3', signed_distance > -half - 5.,
                    {'cat': test.xyz(position), 'exit_center': test.xyz(goal), 'entry_half_extent': half,
                     'axis': test.xyz(direction), 'signed_distance_cm': signed_distance})
                test.shot(world, 'Completion')
                test.phase('complete_wait')
                return
            cat.add_movement_input(direction, 1., False)
            return
    old_step(world)


def finish(error=None):
    if not error:
        try:
            for index in range(2):
                rows = [f['gates'][index] for f in data['frames']]
                label = 'D%d' % (index + 1)
                test.check(label + ' completion fired exactly one impact', rows and rows[-1]['count'] == 1)
                active = [row for row in rows if row['active']]
                test.check(label + ' dust visibly sampled after native completion', len(active) >= 2, len(active))
                test.check(label + ' nonzero rumble observed', any(row['rumble'] > 0 for row in active))
                test.check(label + ' final state fully silent', not rows[-1]['active']
                           and rows[-1]['rumble'] == 0 and rows[-1]['shown'] == 0)
            after = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in hashes}
            data['protected_hashes_after'] = after
            test.check('FX test preserves Stage1/2/3 and shared asset disk hashes', after == hashes)
            data['runtime_verified'] = True
        except Exception as exc:
            error = repr(exc)
    data['error'] = error
    (OUT / 'fx_observation.json').write_text(json.dumps(data, indent=2), encoding='utf8')
    old_finish(error)


test.step, test.finish = step, finish
