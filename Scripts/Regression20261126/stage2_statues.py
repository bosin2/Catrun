"""정식 Stage2 조각상 A/B/C: 저장된 실제 배치에서 경로를 계산해 네이티브 밀기로 안착시키고 철문·연출·입력 복귀를 본다.

구형 Scripts/Prototype/verify_task4d_routes.py 는 방2 개편 전 좌표를 하드코딩해 현재 맵에 쓸 수 없어 대체한다.
고양이를 미는 면에 놓는 것은 fixture 이고, 이동은 TryPushStatue(충돌·가속·바닥 지지 포함)로만 한다. 저장하지 않는다.
"""
import json
import time
import traceback
from pathlib import Path

import unreal as u

ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS = u.GameplayStatics
FLOW = u.CatrunLevelFlowLibrary
OUT = Path(u.Paths.project_dir()) / 'Saved/Stage2Statues'
OUT.mkdir(parents=True, exist_ok=True)
R = {'scope': __doc__, 'checks': [], 'puzzles': {}, 'success': False, 'error': None}
S = {'phase': 'wait', 'index': 0, 'started': time.monotonic(), 'changed': time.monotonic(), 'used': False}


def persist():
    (OUT / 'report.json').write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def check(name, ok, detail=None):
    R['checks'].append({'name': name, 'passed': bool(ok), 'detail': detail})
    persist()
    return ok


def phase(name):
    S.update(phase=name, changed=time.monotonic())


def finish(error=None):
    bad = [c for c in R['checks'] if not c['passed']]
    R.update(error=error, success=not error and not bad)
    persist()
    phase('shutdown')
    LE.editor_request_end_play()


def xy(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def link_of(d):
    return d.get_editor_property('Links')[S['index']]


def step(w, dt):
    pc, cat = GS.get_player_controller(w, 0), GS.get_player_character(w, 0)
    ds = GS.get_all_actors_of_class(w, u.CatrunStatuePuzzle)
    if not pc or not cat or not ds:
        return
    d = ds[0]
    reveal = d.get_editor_property('Reveal')
    if S['phase'] == 'wait':
        if pc.is_move_input_ignored() or FLOW.should_hide_gameplay_hud(w) or GS.get_time_seconds(w) < 4:
            return
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        for cls in (u.CatrunArmor, u.CatrunCandle):
            for a in GS.get_all_actors_of_class(w, cls):
                a.set_actor_tick_enabled(False)
                a.set_actor_enable_collision(False)
        S['links'] = len(d.get_editor_property('Links'))
        check('three statue puzzles linked', S['links'] == 3, S['links'])
        phase('begin')
        return
    link = link_of(d)
    key = str(link.get_editor_property('PuzzleId'))
    statue, plate = link.get_editor_property('Statue'), link.get_editor_property('Plate')
    row = R['puzzles'].setdefault(key, {'blocked': []})
    if S['phase'] == 'begin':
        if pc.is_move_input_ignored():
            return
        row.update(statue_start=xy(statue.get_actor_location()), plate=xy(plate.get_actor_bounds(False)[0]),
                   statue_center=xy(statue.get_actor_bounds(False)[0]))
        c, p = statue.get_actor_bounds(False)[0], plate.get_actor_bounds(False)[0]
        S['axis'] = 'x' if abs(p.x - c.x) >= abs(p.y - c.y) else 'y'
        S.update(steps=0, blocked=0, swaps=0)
        check(key + ' starts unsolved and gate closed', not link.get_editor_property('bCompleted')
              and abs(link.get_editor_property('GateOffset')) < .1)
        d.set_actor_tick_enabled(False)
        phase('push')
        return
    if S['phase'] == 'push':
        if link.get_editor_property('bPressed'):
            check(key + ' seats on plate', True, {'steps': S['steps'], 'at': xy(statue.get_actor_location())})
            d.set_actor_tick_enabled(True)
            S['locked'] = False
            phase('reveal')
            return
        for _ in range(4):
            c, extent = statue.get_actor_bounds(False)
            p = plate.get_actor_bounds(False)[0]
            dx, dy = p.x - c.x, p.y - c.y
            if abs(dx if S['axis'] == 'x' else dy) < 1.4:
                S['axis'] = 'y' if S['axis'] == 'x' else 'x'
            rem = dx if S['axis'] == 'x' else dy
            if abs(rem) < .01:
                d.update_plates_and_gates(.02)
                if S['steps'] > 4000:
                    break
                S['steps'] += 1
                continue
            sign = 1. if rem > 0 else -1.
            direction = u.Vector(sign, 0, 0) if S['axis'] == 'x' else u.Vector(0, sign, 0)
            radius = cat.capsule_component.get_scaled_capsule_radius()
            half = extent.x if S['axis'] == 'x' else extent.y
            at = statue.get_actor_location() - direction * (60 + radius + 3)
            at.z = 26.2
            cat.set_actor_location(at, False, True)
            cat.character_movement.set_movement_mode(u.MovementMode.MOVE_WALKING)
            delta = min(.025, max(.0001, abs(rem) / 100))
            moved = d.try_push_statue(S['index'], cat, direction, delta)
            d.update_plates_and_gates(delta)
            S['steps'] += 1
            S['blocked'] = 0 if moved else S['blocked'] + 1
            if S['blocked'] > 25:
                row['blocked'].append({'at': xy(statue.get_actor_location()), 'axis': S['axis'], 'half': half, 'remaining': [dx, dy]})
                S['axis'], S['blocked'], S['swaps'] = ('y' if S['axis'] == 'x' else 'x'), 0, S['swaps'] + 1
        if S['swaps'] > 6 or S['steps'] > 5000 or time.monotonic() - S['changed'] > 90:
            check(key + ' seats on plate', False, {'steps': S['steps'], 'blocked': row['blocked'][-3:], 'at': xy(statue.get_actor_location())})
            d.set_actor_tick_enabled(True)
            nxt()
        return
    if S['phase'] == 'reveal':
        S['locked'] = S['locked'] or pc.is_move_input_ignored()
        inactive = 'INACTIVE' in str(reveal.get_editor_property('Phase')).upper()
        age = time.monotonic() - S['changed']
        if age < 1.5 or not (link.get_editor_property('bCompleted') and inactive and not pc.is_move_input_ignored()):
            if age > 60:
                check(key + ' gate opens and input returns', False, {
                    'completed': link.get_editor_property('bCompleted'), 'reveal': str(reveal.get_editor_property('Phase')),
                    'ignored': pc.is_move_input_ignored(), 'offset': link.get_editor_property('GateOffset')})
                nxt()
            return
        travel, need = link.get_editor_property('GateOffset'), link.get_editor_property('RequiredGateTravel')
        check(key + ' gate opens and input returns', True, {'offset': travel, 'required': need, 'wall_s': age})
        check(key + ' gate fully recessed', abs(travel + need) < .5, {'offset': travel, 'required': need})
        check(key + ' reveal locked input during camera', S['locked'])
        check(key + ' statue stays centred on plate', max(abs(statue.get_actor_bounds(False)[0].x - plate.get_actor_bounds(False)[0].x),
              abs(statue.get_actor_bounds(False)[0].y - plate.get_actor_bounds(False)[0].y)) < 12)
        nxt()


def nxt():
    S['index'] += 1
    if S['index'] >= S['links']:
        finish()
    else:
        phase('begin')


def tick(dt):
    try:
        if S['phase'] == 'shutdown':
            if not ED.get_game_world() and time.monotonic() - S['changed'] > 1:
                u.unregister_slate_post_tick_callback(S['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        if time.monotonic() - S['started'] > 800 or time.monotonic() - S['changed'] > 200:
            finish('Timeout in ' + S['phase'])
            return
        w = ED.get_game_world()
        if w:
            step(w, dt)
    except Exception:
        finish(traceback.format_exc())


assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
assert LE.load_level('/Game/Maps/Stage2')
S['handle'] = u.register_slate_post_tick_callback(tick)
LE.editor_request_begin_play()
