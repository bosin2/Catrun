"""PIE: real Stage1 exit overlap -> departure -> Stage2 arrival -> title -> movement input. Saves no package.

Every game tick of both cinematics is captured with telemetry. The only fixture is placing the pawn just inside
the exit (same as the repository's verify_stage2_arrival_runtime.py).
"""
import datetime
import json
import math
import sys
import time
import traceback
from pathlib import Path

import unreal as u

LABEL = globals().get('LABEL', 'run')
cmd = u.SystemLibrary.get_command_line().lower()
assert all(t in cmd for t in ('-renderoffscreen', '-savetouserdir', '-userdir=', '-usefixedtimestep', '-fps=30', '-d3d12'))
RUN = Path('D:/CatrunWork/portal/runs') / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + LABEL)
RUN.mkdir(parents=True, exist_ok=False)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS = u.GameplayStatics
assert not ED.get_game_world()
STATE = {'start': time.monotonic(), 'changed': time.monotonic(), 'phase': 'stage1', 'frames': [], 'events': [], 'label': LABEL}
BONES = ('root', 'pelvis', 'head', 'ear_tip_L', 'ear_tip_R', 'ear_L', 'neck', 'chest', 'paw_F_L', 'paw_F_R', 'paw_H_L', 'paw_H_R', 'tail_01', 'tail_07', 'bell')
SUB = u.load_object(None, '/Script/Engine.Default__SubsystemBlueprintLibrary')


def xyz(v):
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


def advance(p):
    STATE.update(phase=p, changed=time.monotonic())
    STATE['events'].append([p, round(time.monotonic() - STATE['start'], 2)])


def finish(error=None):
    STATE['success'] = error is None
    STATE['error'] = error
    (RUN / 'report.json').write_text(json.dumps({k: v for k, v in STATE.items() if k != 'handle'}), encoding='utf-8')
    LEVEL.editor_request_end_play()
    STATE.update(phase='shutdown', changed=time.monotonic())
    print('COMPACT_CAPTURE_DONE', LABEL, str(error)[-600:], str(RUN))


def mesh_state(actor, pc):
    m = actor.get_component_by_class(u.SkeletalMeshComponent)
    row = {'visible': bool(not actor.get_editor_property('hidden') and m.is_visible() and not m.get_editor_property('hidden_in_game')),
           'asset': m.get_skeletal_mesh_asset().get_name(), 'scale': xyz(m.get_world_scale()), 'collision': str(m.get_collision_enabled()),
           'bones': {n: xyz(m.get_socket_location(n)) for n in BONES}, 'screen': {}}
    for n, p in row['bones'].items():
        s = pc.project_world_location_to_screen(u.Vector(*p), True)
        row['screen'][n] = [round(s.x, 1), round(s.y, 1)] if s else None
    r = m.get_socket_rotation('head')
    row['head_rot'] = [r.pitch, r.yaw, r.roll]
    return row


def bound(player, name):
    seq = player.get_sequence()
    for b in seq.get_bindings():
        if b.get_name() == name:
            return player.get_bound_objects(seq.get_binding_id(b))
    return []


def clock(world):
    try:
        s = SUB.call_method('GetWorldSubsystem', args=(world, u.CatrunLevelFlowSubsystem.static_class())).get_stage_clock_state()
        return [round(s.get_editor_property('RemainingSeconds'), 2), s.get_editor_property('bRunning'), s.get_editor_property('bTimed')]
    except Exception:
        return None


def record(world, pc, cat, seqname, player, director):
    stem = f'V{len(STATE["frames"]):05d}_'
    path = str(RUN / (stem + '.png')).replace('\\', '/')
    u.SystemLibrary.execute_console_command(world, f'Shot filename="{path}"', pc)
    row = {'shot': stem, 'seq': seqname, 't': round(GS.get_time_seconds(world), 4), 'vp': list(pc.get_viewport_size()),
           'input_ignored': pc.is_move_input_ignored(), 'look_ignored': pc.is_look_input_ignored(),
           'pawn': xyz(cat.get_actor_location()), 'pawn_hidden': cat.get_editor_property('hidden'),
           'suspended': u.CatrunPuzzleSuspension.is_suspended(world), 'hud_hidden': u.CatrunLevelFlowLibrary.should_hide_gameplay_hud(world),
           'clock': clock(world), 'view': pc.get_view_target().get_name() if pc.get_view_target() else ''}
    m = GS.get_player_camera_manager(world, 0)
    if m:
        r = m.get_camera_rotation()
        row['cam'] = xyz(m.get_camera_location())
        row['rot'] = [r.pitch, r.yaw, r.roll]
        row['fov'] = m.get_fov_angle()
        try:
            row['fading'] = [bool(m.get_editor_property('enable_fading')), float(m.get_editor_property('fade_amount'))]
        except Exception as ex:
            row['fading'] = str(ex)[:60]
    row['titles'] = [w.get_class().get_name() for w in u.WidgetLibrary.get_all_widgets_of_class(world, u.UserWidget, True)
                     if w.is_in_viewport() and w.is_visible() and 'Title' in w.get_class().get_name()]
    if player:
        at = player.get_current_time().time
        row['f'] = round(at.frame_number.value + at.sub_frame)
        row['end'] = player.get_sequence().get_playback_end()
        row['cats'] = {}
        for n in ('CompactPortalCat', 'CompactArrivalCat', 'CosmeticCat'):
            objs = bound(player, n)
            if objs:
                row['cats'][n] = mesh_state(objs[0], pc)
        for n in ('CompactPawRipple', 'CompactEntryRipple', 'ArrivalExitRipple'):
            objs = bound(player, n)
            if objs:
                row.setdefault('rings', {})[n] = xyz(objs[0].get_actor_location())
    row['cats_real'] = mesh_state(cat, pc)
    if director:
        row['director'] = {n: director.get_editor_property(n) for n in ('Playing', 'Started', 'Finished', 'HandoffStarted')}
    STATE['frames'].append(row)
    return row


def checkpoint(world, cat):
    capsule = cat.get_component_by_class(u.CapsuleComponent)
    ex = next(a for a in GS.get_all_actors_of_class(world, u.CatrunStageExit) if 'CatrunAuthoredStage1Exit' in map(str, a.tags))
    center = ex.get_editor_property('Trigger').get_world_location()
    y = center.y - ex.get_editor_property('MinimumInteriorDepth') - 3.
    target = u.Vector(center.x, y, 74.)
    hit = u.SystemLibrary.capsule_trace_single_by_profile(world, target, u.Vector(target.x, y, -40.), capsule.get_scaled_capsule_radius(),
                                                          capsule.get_scaled_capsule_half_height(), 'Pawn', False, [cat, ex], u.DrawDebugTrace.NONE, False)
    assert hit, 'No floor at exit checkpoint'
    target = hit.to_dict()['location'] + u.Vector(0, 0, 2.2)
    cat.set_actor_location_and_rotation(target, u.Rotator(yaw=-90), False, True)


def named(world, cls):
    return next((a for a in GS.get_all_actors_of_class(world, u.Actor) if a.get_class().get_name() == cls), None)


def tick(_):
    try:
        now = time.monotonic()
        if STATE['phase'] == 'shutdown':
            if not ED.get_game_world() and now - STATE['changed'] > 1.5 and 'handle' in STATE:
                u.unregister_slate_post_tick_callback(STATE.pop('handle'))
                STATE['phase'] = 'done'
            return
        if STATE['phase'] == 'done':
            return
        if now - STATE['start'] > 900:
            finish('timeout in ' + STATE['phase'])
            return
        world = ED.get_game_world()
        if not world:
            return
        pc, cat = GS.get_player_controller(world, 0), GS.get_player_pawn(world, 0)
        if not pc or not cat:
            return
        moment = (world.get_path_name(), GS.get_time_seconds(world))
        if moment == STATE.get('moment'):
            return
        STATE['moment'] = moment
        stage, phase = world.get_name(), STATE['phase']
        if phase == 'stage1':
            if (now - STATE['start'] > 5 and moment[1] > 1. and not pc.is_move_input_ignored()
                    and cat.get_component_by_class(u.CharacterMovementComponent).movement_mode == u.MovementMode.MOVE_WALKING):
                STATE['clock_stage1'] = clock(world)
                checkpoint(world, cat)
                advance('portal')
        elif phase == 'portal':
            if stage.endswith('Stage1'):
                d = named(world, 'BP_Stage1PortalExit_C')
                if d and d.get_editor_property('Playing'):
                    p = d.get_editor_property('SequencePlayer')
                    if p:
                        record(world, pc, cat, 'departure', p, None)
                assert now - STATE['changed'] < 400, 'Portal did not finish'
            elif stage.endswith('Stage2'):
                STATE['stage2_reached'] = True
                advance('arrival')
        elif phase in ('arrival', 'after'):
            assert phase == 'after' or GS.get_time_seconds(world) < 30., 'Arrival did not finish within 30 s'
            d = named(world, 'BP_Stage2PortalArrival_C')
            p = d.get_editor_property('SequencePlayer') if d else None
            row = record(world, pc, cat, 'arrival' if phase == 'arrival' else 'after', p, d)
            if phase == 'arrival' and d and d.get_editor_property('Finished') and row['titles']:
                STATE['title_frame'] = len(STATE['frames'])
                advance('after')
            elif phase == 'after' and len(STATE['frames']) - STATE['title_frame'] > 30:
                # A leftover camera fade would make every later exit lease (elevator included) refuse to start.
                lease = d.get_editor_property('ExitTransition')
                got = lease.acquire_exit_lease(cat)
                STATE['post_arrival_lease'] = ['rejected' if got is None else 'accepted', lease.has_exit_lease()]
                if lease.has_exit_lease():
                    lease.release_exit_lease(False)
                STATE['post_arrival_lease'].append(lease.has_exit_lease())
                STATE['move_start'] = xyz(cat.get_actor_location())
                STATE['final_view'] = {'proj': str(pc.get_view_target().get_component_by_class(u.CameraComponent).projection_mode),
                                       'width': pc.get_view_target().get_component_by_class(u.CameraComponent).ortho_width}
                advance('move')
        elif phase == 'move':
            cat.add_movement_input(u.Vector(0, -1, 0), 1., False)
            if cat.get_actor_location().y < STATE['move_start'][1] - 3:
                STATE['move_end'] = xyz(cat.get_actor_location())
                STATE['clock_end'] = clock(world)
                finish()
            else:
                assert now - STATE['changed'] < 8, 'Pawn did not move on restored input'
    except Exception:
        finish(traceback.format_exc())


# Keep the level viewport from answering the global Shot request instead of the game viewport.
try:
    for k in LEVEL.get_viewport_config_keys():
        LEVEL.editor_set_viewport_realtime(False, k)
    STATE['editor_viewport_realtime_off'] = True
except Exception as ex:
    STATE['editor_viewport_realtime_off'] = str(ex)[:120]
STATE['handle'] = u.register_slate_post_tick_callback(tick)
LEVEL.editor_request_begin_play()
print('COMPACT_CAPTURE_STARTED', LABEL, str(RUN))
