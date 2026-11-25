"""Reflected Stage3: unchanged 176-check layout/native suite plus D0 and camera.

NPC motion is observed before deterministic fixtures disable NPC tick/collision.
D0 uses native SetOpen, capsule blocking and physical walks from both sides;
this does not test armor OpenFrom hinge selection or hand-driven animation.
No assets, map or user settings are saved. Run alone for animation sampling.
"""
import importlib.util
import os
import time
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
spec = importlib.util.spec_from_file_location(
    'orientation_layout_regression', ROOT / 'Scripts/Stage3/LayoutCorrection20261125/regression.py')
layout = importlib.util.module_from_spec(spec)
layout.OUTPUT_AREA = 'Stage3OrientationFix20261125'
layout.OUTPUT_PASS = os.environ.get('CATRUN_ORIENTATION_REGRESSION_PASS', 'Regression01')
spec.loader.exec_module(layout)
layout.configure_orientation(-1)
test = layout.test
test.S['scope'] = __doc__
test.S['expected_checks'] = 188
EXPECTED_CAMERA_YAW = float(os.environ.get('CATRUN_STAGE3_CAMERA_YAW', '-135'))
previous_step = test.step


def angle_delta(a, b):
    return (a - b + 180.) % 360. - 180.


def d0_stage(name, world):
    test.S['d0_state'] = name
    test.S['d0_game_start'] = test.GS.get_time_seconds(world)
    test.S['changed'] = time.monotonic()


def d0_regression(world, cat):
    """Transient door fixture; restore its closed state before baseline routes."""
    if test.S.get('d0_complete'):
        return True
    door = layout.lookup(world)['S3_D0']
    leaf = door.get_editor_property('DoorMesh')
    gate = door.get_editor_property('GateBox')
    capsule = cat.get_component_by_class(u.CapsuleComponent)
    z = capsule.get_scaled_capsule_half_height() + .25
    center = gate.get_world_location()
    normal = gate.get_right_vector()
    normal = u.Vector(normal.x, normal.y, 0).normal()
    side_a = u.Vector(center.x, center.y, z) + normal * 110.
    side_b = u.Vector(center.x, center.y, z) - normal * 110.
    game = test.GS.get_time_seconds(world)
    state = test.S.get('d0_state')
    if state is None:
        test.S['d0_original_cat'] = test.xyz(cat.get_actor_location())
        test.S['d0_observed_initially_open'] = door.is_open()
        door.set_open(False)
        test.move(cat, side_a.x, side_a.y)
        d0_stage('closing_fixture', world)
        return False
    elapsed = game - test.S['d0_game_start']
    duration = max(.01, door.get_editor_property('OpenDuration')) + .25
    if state == 'closing_fixture':
        if elapsed < duration:
            return False
        test.check('D0 closed leaf blocks pawns',
                   not door.is_open() and leaf.get_collision_enabled() == u.CollisionEnabled.QUERY_AND_PHYSICS)
        test.S['d0_closed_location'] = test.xyz(leaf.get_world_location())
        rot = leaf.get_world_rotation()
        test.S['d0_closed_rotation'] = [rot.pitch, rot.yaw, rot.roll]
        ignored = [cat] + test.actors(world, u.CatrunArmor) + test.actors(world, u.CatrunCandle)
        for name, start, end in [('A to B', side_a, side_b), ('B to A', side_b, side_a)]:
            hit = test.SL.capsule_trace_single_by_profile(
                world, start, end, capsule.get_scaled_capsule_radius(),
                capsule.get_scaled_capsule_half_height(), 'Pawn', False,
                ignored, u.DrawDebugTrace.NONE, True)
            test.check('D0 closed capsule blocked ' + name, bool(hit),
                       {'start': test.xyz(start), 'end': test.xyz(end)})
        door.set_open(True)
        test.check('D0 native SetOpen opens state', door.is_open())
        test.check('D0 native opening releases collision',
                   leaf.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION)
        d0_stage('opening', world)
        return False
    if state == 'opening':
        if elapsed < duration:
            return False
        rotation = leaf.get_world_rotation()
        yaw_change = angle_delta(rotation.yaw, test.S['d0_closed_rotation'][1])
        expected = door.get_editor_property('OpenYaw')
        test.check('D0 native opening reaches configured angle',
                   abs(angle_delta(yaw_change, expected)) < .1,
                   {'yaw_change': yaw_change, 'expected': expected})
        test.move(cat, side_a.x, side_a.y)
        d0_stage('walk_a_to_b', world)
        return False
    if state in ('walk_a_to_b', 'walk_b_to_a'):
        target = side_b if state == 'walk_a_to_b' else side_a
        pos = cat.get_actor_location()
        delta = u.Vector(target.x - pos.x, target.y - pos.y, 0)
        if delta.length() < 15.:
            test.check('D0 physical traversal ' + state, True,
                       {'actual': test.xyz(pos), 'target': test.xyz(target), 'seconds': elapsed})
            cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
            if state == 'walk_a_to_b':
                # Continue from the reached side; do not teleport across the door.
                d0_stage('walk_b_to_a', world)
            else:
                door.set_open(False)
                original = test.S['d0_original_cat']
                test.move(cat, original[0], original[1])
                d0_stage('restore_closed', world)
            return False
        if elapsed > 18.:
            test.check('D0 physical traversal ' + state + ' not blocked', False,
                       {'actual': test.xyz(pos), 'target': test.xyz(target), 'seconds': elapsed})
        cat.add_movement_input(delta.normal(), 1., False)
        return False
    if state == 'restore_closed':
        if elapsed < duration:
            return False
        test.check('D0 native close restores closed state', not door.is_open())
        test.check('D0 native close restores collision',
                   leaf.get_collision_enabled() == u.CollisionEnabled.QUERY_AND_PHYSICS)
        location_error = (leaf.get_world_location() - u.Vector(*test.S['d0_closed_location'])).length()
        rotation = leaf.get_world_rotation()
        rotation_error = max(abs(angle_delta(actual, expected)) for actual, expected in
                             zip((rotation.pitch, rotation.yaw, rotation.roll), test.S['d0_closed_rotation']))
        test.check('D0 native close restores saved leaf pose', location_error < .05 and rotation_error < .1,
                   {'position_error_cm': location_error, 'rotation_error_degrees': rotation_error})
        test.S['d0_complete'] = True
        test.S['changed'] = time.monotonic()
        return True
    raise AssertionError(('Unknown D0 regression state', state))


def step(world):
    cat = test.GS.get_player_character(world, 0)
    if not cat:
        return
    if test.S['phase'] == 'observe' and not test.S.get('orientation_camera_checked'):
        manager = test.GS.get_player_camera_manager(world, 0)
        yaw = manager.get_camera_rotation().yaw
        test.check('Actual player camera uses requested Stage3 yaw', abs(angle_delta(yaw, EXPECTED_CAMERA_YAW)) < .1,
                   {'actual_yaw': yaw, 'expected_yaw': EXPECTED_CAMERA_YAW})
        test.S['orientation_camera_checked'] = True
    if test.S['phase'] == 'push1' and not d0_regression(world, cat):
        return
    previous_step(world)


test.step = step
