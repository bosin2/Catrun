"""Stage3 Polish 2026-11-26 screen verification (disposable PIE, read-only: nothing is saved).

1) Cutaway: corner posts/decor/cat-hole walls/24cm foot/OutsideGround behind cut camera-side walls.
2) Lock devices: amber floor sigil + pulsing light, then green after a real TryRelease.
3) D1/D2 statue gates (reveal + shake + light) and the final gate 3.45 s profile (leaf trace).
Output: Saved/Stage3Polish20261126/Captures/<PASS>/  (images + report.json)
"""
import json, os, time, math, traceback
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
PASS = os.environ.get('S3P_CAPTURE_PASS', 'Run01')
OUT = ROOT / 'Saved/Stage3Polish20261126/Captures' / PASS
OUT.mkdir(parents=True, exist_ok=True)
POSES = json.loads((ROOT / 'Saved/Stage3Polish20261126/Captures/poses_cutaway.json').read_text(encoding='utf8'))
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
GS = u.GameplayStatics
S = {'phase': 'startup', 'started': time.monotonic(), 'shots': [], 'log': [], 'traces': {}, 'errors': [],
     'command_line': u.SystemLibrary.get_command_line()}
GEN = None
WAIT = {'game': 0.0, 'wall': 0.0, 'ticks': 0}


def vec(v): return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]
def persist(): (OUT / 'report.json').write_text(json.dumps({k: v for k, v in S.items() if k != 'handle'}, indent=1, ensure_ascii=False, default=lambda o: [x for x in o] if hasattr(o, '__iter__') else str(o)), encoding='utf8')
def cmd(w, t): u.SystemLibrary.execute_console_command(w, t)
def note(msg):
    S['log'].append(msg); print('S3P_CAPTURE', msg)


def world(): return ED.get_game_world()


def presenter_state(w):
    out = {}
    try:
        p = [a for a in GS.get_all_actors_of_class(w, u.Actor) if 'S3Polish_Presenter' in a.get_class().get_name()]
        if not p: return {'missing': True}
        p = p[0]
        for c in p.get_components_by_class(u.LightComponent):
            col = c.get_editor_property('light_color')
            out[c.get_name()] = {'intensity': round(c.get_editor_property('intensity'), 2), 'color': [col.r, col.g, col.b]}
        for c in p.get_components_by_class(u.PrimitiveComponent):
            n = c.get_name()
            if n.startswith(('LockSigil', 'OutsideGround')):
                out[n] = {'visible': c.is_visible(), 'loc': vec(c.get_world_location()),
                          'collision': str(c.get_collision_enabled())}
                try: out[n]['cpd0'] = [float(x) for x in c.get_editor_property('custom_primitive_data').get_editor_property('data')][:1]
                except Exception: pass
    except Exception as e:
        out['error'] = repr(e)
    return out


def shot(name, extra=None):
    w = world()
    cam = GS.get_player_camera_manager(w, 0)
    cat = GS.get_player_character(w, 0)
    rec = {'name': name, 'game_t': round(GS.get_time_seconds(w), 3), 'cat': vec(cat.get_actor_location()),
           'camera': vec(cam.get_camera_location()), 'presenter': presenter_state(w)}
    if extra: rec.update(extra)
    S['shots'].append(rec)
    cmd(w, 'HighResShot 1280x720 filename="' + str(OUT / (name + '.png')).replace('\\', '/') + '"')
    persist()


def place(cat, xyz, yaw=90):
    cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    cat.set_actor_location(u.Vector(*xyz), False, True)
    cat.set_actor_rotation(u.Rotator(yaw=yaw), True)


def wait(game=0.0, wall=0.0, ticks=2):
    return ('wait', game, wall, ticks)


def script():
    w = world(); cat = GS.get_player_character(w, 0)
    # ---- 1) cutaway ----
    order = ['Corner09', 'Corner02', 'Corner04', 'Corner00', 'Corner08', 'DecorTrophyLobby', 'DecorStandoffCentral',
             'CatHole1', 'CatHole2', 'CatHole3', 'VoidEast1325', 'VoidGateEast', 'VoidWest1425', 'VoidLobbySouth']
    for name in order:
        pose = POSES.get(name)
        if not pose or not pose['cat']: note('skip ' + name); continue
        place(cat, pose['cat'])
        yield wait(game=2.5, wall=2.0, ticks=30)
        cmd(w, 'Editor.AsyncAssetCompilationFinishAll')
        yield wait(game=0.5, wall=1.5, ticks=20)
        shot('cut_' + name, {'target': pose['label'], 'expected_cut': pose['cut_groups_at_pose']})
        yield wait(game=0.3, wall=1.5, ticks=10)
    # ---- 2) lock devices ----
    obj = GS.get_all_actors_of_class(w, u.CatrunStage3Objectives)[0]
    puzzle = GS.get_all_actors_of_class(w, u.CatrunStatuePuzzle)[0]
    devs = obj.get_editor_property('devices')
    S['devices'] = [{'housing': d.get_editor_property('housing').get_actor_label(), 'ring': vec(d.get_editor_property('ring').get_actor_location()),
                     'rot': d.get_editor_property('housing').get_actor_rotation().yaw} for d in devs]
    links = puzzle.get_editor_property('links')
    S['links'] = [{'id': str(l.get_editor_property('puzzle_id')), 'statue': l.get_editor_property('statue').get_actor_label(),
                   'plate': l.get_editor_property('plate').get_actor_label(), 'gate': l.get_editor_property('gate').get_actor_label(),
                   'statue_loc': vec(l.get_editor_property('statue').get_actor_location()),
                   'plate_loc': vec(l.get_editor_property('plate').get_actor_location()),
                   'gate_loc': vec(l.get_editor_property('gate').get_actor_location())} for l in links]
    persist()
    for i, d in enumerate(devs):
        housing = d.get_editor_property('housing'); ring = d.get_editor_property('ring')
        rl = ring.get_actor_location(); rot = housing.get_actor_rotation()
        released = False
        for dist in (60, 50, 70, 45, 80, 40, 88):
            rv = housing.get_actor_right_vector()
            place(cat, (rl.x + rv.x * dist, rl.y + rv.y * dist, 26.2), yaw=rot.yaw - 90)
            yield wait(game=0.6, wall=0.5, ticks=10)
            if dist == 60:
                shot('lock%d_locked_a' % i)
                yield wait(game=0.55, wall=1.0, ticks=10)
                shot('lock%d_locked_b' % i)
                yield wait(game=0.3, wall=1.0, ticks=10)
            if obj.can_release(i, cat) and obj.try_release(i, cat):
                released = True; note('device %d release started at dist %d' % (i, dist)); break
        if not released:
            S['errors'].append('device %d: TryRelease failed at all offsets' % i); persist(); continue
        yield wait(game=1.0, wall=0.5, ticks=10)
        shot('lock%d_releasing' % i)
        for _ in range(80):
            yield wait(game=0.1, ticks=1)
            if obj.get_editor_property('devices')[i].get_editor_property('released') and obj.get_editor_property('active_device') == -1: break
        yield wait(game=0.8, wall=1.0, ticks=10)
        shot('lock%d_released' % i, {'released': obj.get_editor_property('devices')[i].get_editor_property('released')})
        yield wait(game=0.3, wall=1.0, ticks=10)
    S['all_released'] = obj.all_released(); persist()
    # ---- 3) statue gates (D1/D2 and the locked S3_P2) ----
    for j in range(len(links)):
        lk = puzzle.get_editor_property('links')[j]
        statue = lk.get_editor_property('statue'); plate = lk.get_editor_property('plate'); gate = lk.get_editor_property('gate')
        sid = str(lk.get_editor_property('puzzle_id'))
        g0 = gate.get_actor_location(); s0 = statue.get_actor_location()
        # cat stands at the vacated statue spot, offset 80cm away from the plate
        pl = plate.get_actor_location(); away = u.Vector(s0.x - pl.x, s0.y - pl.y, 0); n = max(1.0, math.hypot(away.x, away.y))
        place(cat, (s0.x + away.x / n * 90, s0.y + away.y / n * 90, 26.2))
        yield wait(game=0.6, wall=0.5, ticks=10)
        statue.set_actor_location(u.Vector(pl.x, pl.y, s0.z), False, True)
        t0 = GS.get_time_seconds(w); trace = []; marks = [0.15, 0.6, 1.0, 1.5, 2.0, 2.6, 3.4, 4.4]; taken = 0
        S['traces'][sid] = trace
        while GS.get_time_seconds(w) - t0 < 7.0:
            t = GS.get_time_seconds(w) - t0
            lk = puzzle.get_editor_property('links')[j]
            cam = GS.get_player_camera_manager(w, 0)
            trace.append([round(t, 3), round(gate.get_actor_location().z - g0.z, 2), lk.get_editor_property('pressed'),
                          lk.get_editor_property('completed'), vec(cam.get_camera_location()), presenter_state(w).get('GateLight%d' % j, {}).get('intensity')])
            if taken < len(marks) and t >= marks[taken]:
                shot('gate_%s_t%03d' % (sid, int(marks[taken] * 100))); taken += 1
            yield wait(ticks=1)
        persist()
    # ---- 4) final gate ----
    fl = obj.get_editor_property('final_leaf_left'); fr = obj.get_editor_property('final_leaf_right')
    L0, R0 = fl.get_actor_location(), fr.get_actor_location()
    mid = u.Vector((L0.x + R0.x) / 2, (L0.y + R0.y) / 2, 26.2)
    S['final'] = {'left0': vec(L0), 'right0': vec(R0), 'seated_P2': puzzle.is_puzzle_seated('S3_P2'), 'all_released': obj.all_released()}
    place(cat, (mid.x, mid.y + 320, 26.2), yaw=-90)
    # t=0 is the trigger (reveal camera starts travelling). Leaves open on camera arrival (~2.0 s),
    # reach the stops 3.45 s later (~5.45 s), hold 1 s, then the camera eases back to the cat (~6.45-8.05 s).
    trace = []; S['traces']['final'] = trace; t0 = None; taken = 0
    marks = [0.3, 1.0, 1.7, 2.3, 3.0, 4.0, 4.8, 5.5, 6.2, 7.0, 8.4]
    reveal = obj.get_editor_property('final_reveal')
    start = GS.get_time_seconds(w)
    while GS.get_time_seconds(w) - start < 16.0:
        dl = fl.get_actor_location().x - L0.x; dr = fr.get_actor_location().x - R0.x
        phase = str(reveal.get_editor_property('phase')).split('.')[-1] if reveal else 'none'
        opened = obj.get_editor_property('final_gate_open'); pending = obj.get_editor_property('final_reveal_pending')
        if t0 is None and (abs(dl) > 0.01 or opened or pending):
            t0 = GS.get_time_seconds(w); note('final gate triggered (pending=%s open=%s phase=%s)' % (pending, opened, phase))
        if t0 is not None:
            t = GS.get_time_seconds(w) - t0
            cam = GS.get_player_camera_manager(w, 0)
            vt = GS.get_player_controller(w, 0).get_view_target()
            trace.append([round(t, 3), round(dl, 2), round(dr, 2), vec(cam.get_camera_location()), presenter_state(w).get('GateLight2', {}).get('intensity'),
                          phase, bool(opened), vt.get_class().get_name() if vt else None])
            if taken < len(marks) and t >= marks[taken]:
                shot('final_t%03d' % int(marks[taken] * 100), {'phase': phase, 'gate_open': bool(opened), 'leaf_offset': round(-dl, 2)}); taken += 1
            if t > 9.0: break
        yield wait(ticks=1)
    if t0 is None: S['errors'].append('final gate never moved: ' + json.dumps(S['final']))
    persist()


def finish(error=None):
    S['success'] = error is None and not S['errors']; S['error'] = error; S['phase'] = 'shutdown'; S['changed'] = time.monotonic()
    try: persist()
    except Exception: print('S3P_CAPTURE persist failed', traceback.format_exc())
    w = world()
    if w: GS.set_game_paused(w, False); LE.editor_request_end_play()


def tick(_dt):
    global GEN
    try:
        if S['phase'] == 'shutdown':
            if not world() and time.monotonic() - S['changed'] > 1:
                u.unregister_slate_post_tick_callback(S['handle']); cmd(ED.get_editor_world(), 'QUIT_EDITOR')
            return
        assert time.monotonic() - S['started'] < 1500, 'Capture timeout'
        w = world()
        if not w: return
        cat = GS.get_player_character(w, 0)
        if not cat: return
        if S['phase'] == 'startup':
            if GS.get_time_seconds(w) < 3: return
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            for a in list(GS.get_all_actors_of_class(w, u.CatrunArmor)) + list(GS.get_all_actors_of_class(w, u.CatrunCandle)):
                a.set_actor_tick_enabled(False)
            cmd(w, 'Editor.AsyncAssetCompilationFinishAll')
            S['phase'] = 'warmup'; S['changed'] = time.monotonic(); S['wt'] = 0; return
        if S['phase'] == 'warmup':
            S['wt'] += 1
            if time.monotonic() - S['changed'] < 10 or S['wt'] < 60: return
            cmd(w, 'Editor.AsyncAssetCompilationFinishAll')
            GEN = script(); S['phase'] = 'run'; WAIT.update(game=0, wall=0, ticks=0)
        if S['phase'] == 'run':
            if WAIT['ticks'] > 0: WAIT['ticks'] -= 1
            if WAIT['ticks'] > 0 or GS.get_time_seconds(w) < WAIT['game'] or time.monotonic() < WAIT['wall']: return
            try:
                _, g, wl, tk = next(GEN)
                WAIT.update(game=GS.get_time_seconds(w) + g, wall=time.monotonic() + wl, ticks=tk)
            except StopIteration:
                note('script complete'); S['phase'] = 'drain'; S['changed'] = time.monotonic(); return
        if S['phase'] == 'drain' and time.monotonic() - S['changed'] > 3:
            missing = [s['name'] for s in S['shots'] if not (OUT / (s['name'] + '.png')).exists()]
            if missing: S['errors'].append('missing images: ' + ','.join(missing))
            finish()
    except Exception:
        finish(traceback.format_exc())


assert '-SaveToUserDir' in S['command_line']
assert LE.load_level('/Game/Maps/Stage3')
cmd(ED.get_editor_world(), 'Editor.AsyncAssetCompilationFinishAll')
S['started'] = time.monotonic(); S['handle'] = u.register_slate_post_tick_callback(tick)
try: LE.editor_request_begin_play()
except Exception: finish(traceback.format_exc())
