"""Re-stage LS_Stage2_PortalArrival in the candidate. END / handoff frame and the final view stay untouched.

Compact cat performs 8..POV; the existing gameplay-model CosmeticCat is revealed only after the point-of-view
shots, so the model change happens while no cat is on screen.
"""
import importlib
import json
import math
import sys
import traceback
from pathlib import Path

import unreal as u

TOOLS = Path('C:/Users/whghk/.codex/workspaces/CompactPortal_20261125/Tools')
ROOT = Path(u.Paths.project_dir()).resolve()
for q in (str(TOOLS), str(ROOT / 'Scripts/GameplayRepair')):
    if q not in sys.path:
        sys.path.insert(0, q)
sys.dont_write_bytecode = True
import stubs
import pcommon as pc
importlib.reload(pc)
import stage2_arrival_shots as old
import stage2_arrival_revision as rev
import stage1_departure_shots as s1

SEQ = '/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival'
SEQ_FILE = pc.pristine('Content/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival.uasset')
CFG = json.loads((TOOLS / 'shots2.json').read_text(encoding='utf-8'))
TRUTH = json.loads(Path(pc.SRC['truth']).read_text())
IMP = json.loads((pc.OUT / 'import_report.json').read_text(encoding='utf-8'))
OLD_END = rev.END
HANDOFF, CRANE_END, END = (CFG['handoff'][k] for k in ('frame', 'crane_end', 'end'))
assert abs(CFG['handoff']['seconds'] - HANDOFF / 30.) < 1e-6 and HANDOFF <= CRANE_END < END
OWNED = ('CompactArrivalCat', 'ArrivalExitRipple')
T = CFG['timing']
REVEAL, TOUCH, CUT_B, CUT_C, POV, RETURN = (T[k] for k in ('reveal', 'touchdown', 'cut_walk', 'cut_sit', 'pov', 'return'))
PLANE_Y, X, FOOT = 3980.75, 1375., 26.2 + IMP['pawn_mesh']['location'][2] + CFG['ground_offset']
SCALE = 2.
RATE = CFG['walk_rate']
SPEED = .32685 * SCALE * RATE
END_Y = 3700.


def landing_shift(src):
    """World forward travel that keeps the front paws planted while they slide back in the Landing clip."""
    rows = TRUTH['AN_BlackCat_Landing']
    i = min(int(src), len(rows) - 2)
    a, b = rows[i]['paw_F_L'][1], rows[i + 1]['paw_F_L'][1]
    return 100. * SCALE * ((a + (b - a) * (src - i)) - rows[0]['paw_F_L'][1])


def cat_rows():
    rows = []
    n = TOUCH - REVEAL
    f0, lr = CFG['flight'], CFG['landing_rate']
    g2 = f0['height'] / (n * n)                  # falls from the apex: z = h - g2 * k^2
    y0 = PLANE_Y + f0['behind']
    v0, v1 = f0['speed'], f0['speed_end']
    for k in range(n + 1):
        y = y0 - (v0 * k + .5 * (v1 - v0) * k * k / n)
        rows.append((REVEAL + k, y, FOOT + f0['height'] - g2 * k * k))
    land_y = rows[-1][1]
    f = TOUCH
    while f < T['walk']:
        f += 1
        rows.append((f, land_y - landing_shift(min(36., (f - TOUCH) * lr)), FOOT))
    y = rows[-1][1]
    ramp = 8.
    while f < CUT_B - 1:
        f += 1
        y -= SPEED * min(1., (f - T['walk'] - .5) / ramp)
        rows.append((f, y, FOOT))
    eps = 1. / 800
    rows.append((CUT_B - eps, y, FOOT))
    stop, slow, sr = T['stop'], CFG['slow_frames'], CFG['slow_rate']
    c_start = END_Y + SPEED * (stop - slow - CUT_C) + SPEED * sr * slow
    b_end = c_start + CFG['b_gap']
    rows += [(CUT_B, b_end + SPEED * (CUT_C - CUT_B), FOOT), (CUT_C - eps, b_end, FOOT), (CUT_C, c_start, FOOT),
             (stop - slow, END_Y + SPEED * sr * slow, FOOT), (stop, END_Y, FOOT), (END, END_Y, FOOT)]
    return [(f, (X, y, z, 0., 0., -180., SCALE, SCALE, SCALE)) for f, y, z in rows], land_y


def look(frame, eye, aim, fov):
    r = u.MathLibrary.find_look_at_rotation(u.Vector(*eye), u.Vector(*aim))
    return frame, [*eye, 0., r.pitch, r.yaw, 1., 1., 1.], fov


def return_curve(gameplay):
    """Front hold, rise, then orbit to the exact gameplay view (7b1c correction of the statue crossing)."""
    c = CFG['return_cam']
    subject = (1375., 3690., 28.)
    front = rev.aim(RETURN, tuple(c['eye']), subject, c['width'])
    pitch1, yaw1, roll1 = gameplay['pyr']
    pitch0, yaw0 = front[1][4:6]
    yaw1 = yaw0 + (yaw1 - yaw0 + 180.) % 360. - 180.
    r0 = math.dist(subject[:2], front[1][:2])
    r1 = math.hypot(gameplay['xyz'][0] - 1375., gameplay['xyz'][1] - 3700.)
    end = [gameplay['xyz'][0] + r1 * math.cos(math.radians(yaw1)), gameplay['xyz'][1] + r1 * math.sin(math.radians(yaw1)),
           gameplay['xyz'][2] + r1 * math.tan(math.radians(pitch1))]
    hold = c['hold']
    rows = [front, (hold, list(front[1]), front[2])]
    for f in (*range(hold + 4, CRANE_END, 4), CRANE_END):
        t = (f - hold) / (CRANE_END - hold)
        s = t * t * (3. - 2. * t)
        l = min(t / c.get('lift', .5), 1.)
        l = l * l * (3. - 2. * l)
        w = max(0., (t - c.get('width_delay', 0.)) / (1. - c.get('width_delay', 0.)))
        w = w * w * (3. - 2. * w)
        yaw, pitch = yaw0 + (yaw1 - yaw0) * s, pitch0 + (pitch1 - pitch0) * l
        radius = r0 + (r1 - r0) * s
        cx, cy, cz = [a + (b - a) * s for a, b in zip(subject, end)]
        eye = [cx - radius * math.cos(math.radians(yaw)), cy - radius * math.sin(math.radians(yaw)), cz - radius * math.tan(math.radians(pitch))]
        rows.append((f, [*eye, s * roll1, pitch, yaw, 1., 1., 1.], front[2] * (gameplay['width'] / front[2]) ** w))
    return rows


def main():
    rep = {'success': False, 'mode': pc.mode(), 'preexisting': pc.dirty()}
    assert pc.mode() == 'dry' or not pc.dirty(), pc.dirty()
    try:
        seq = u.load_asset(SEQ)
        bs = old.bindings(seq)
        previous_end = seq.get_playback_end()
        assert previous_end in (OLD_END, END)
        guids = {n: old.guid(b) for n, b in bs.items() if n not in (*OWNED, 'ArrivalExitRippleMaterial')}
        # Exact final gameplay view already stored in the sequence (handoff pose).
        fr = old.section(bs['FaceReturn'], u.MovieScene3DTransformTrack)
        last = [sorted((old.frameof(k), k.get_value()) for k in ch.get_keys())[-1] for ch in pc.doubles(fr)]
        wch, = old.section(bs['FaceReturnLens'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        width = sorted((old.frameof(k), k.get_value()) for k in wch.get_keys())[-1]
        v = [x for _, x in last]
        gameplay = {'xyz': v[:3], 'pyr': [v[4], v[5], v[3]], 'width': width[1]}
        rep['gameplay_view'] = gameplay
        seq.modify()
        pc.drop(seq, OWNED)
        bs = old.bindings(seq)
        seq.set_playback_end(END)
        for b in seq.get_bindings():
            for t in b.get_tracks():
                for sec in list(t.get_sections()):
                    if sec.get_start_frame() >= END:
                        t.remove_section(sec)
                    elif sec.get_end_frame() > END:
                        sec.set_end_frame(END)
        # ---- black start (the director holds black from BeginPlay), then the portal appears
        for t in [t for t in seq.get_tracks() if isinstance(t, u.MovieSceneFadeTrack)]:
            seq.remove_track(t)
        fade = seq.add_track(u.MovieSceneFadeTrack).add_section()
        fade.set_range(0, CFG['fade'][-1][0] + 2)
        fade.set_completion_mode(pc.RESTORE)
        pc.keys(pc.only(fade.get_all_channels()), CFG['fade'], pc.LINEAR, 1.)
        # ---- cats
        cat = pc.cat_spawnable(seq, 'CompactArrivalCat', END)
        rows, land_y = cat_rows()
        pc.transform(cat, rows, END)
        pc.visible_track(cat, [(0, False), (REVEAL, True), (POV, False)], END)
        track = cat.add_track(u.MovieSceneSkeletalAnimationTrack)
        air, jump, land = pc.clip('AN_CompactPortal_AirReach'), pc.clip('AN_BlackCat_JumpDown'), pc.clip('AN_BlackCat_Landing')
        walk, sit = pc.clip('AN_CompactPortal_WalkReview'), pc.clip('AN_CompactPortal_SeatedListenTouch')
        lr, b0 = CFG['landing_rate'], CFG['reach_blend']
        n = TOUCH - REVEAL
        pc.animation(track, air, 0, REVEAL + b0[1], 18. / (REVEAL + b0[1]), 0., 0, b0[1] - b0[0])
        # JumpDown 24..39 reaches for the floor; its last frame equals Landing frame 0.
        pc.animation(track, jump, REVEAL + b0[0], TOUCH, 15. / (n - b0[0]), 24., b0[1] - b0[0], 0)
        wb = T['walk_blend']
        pc.animation(track, land, TOUCH, T['walk'] + wb, lr, 0., 0, wb)
        stop, slow, sr = T['stop'], CFG['slow_frames'], CFG['slow_rate']
        pc.animation(track, walk, T['walk'], CUT_B, RATE, CFG['walk_phase'], wb, 0)
        pc.animation(track, walk, CUT_B, CUT_C, RATE, 40.)
        s3 = 119. - RATE * sr * slow
        pc.animation(track, walk, CUT_C, stop - slow, RATE, s3 - RATE * (stop - slow - CUT_C))
        pc.animation(track, walk, stop - slow, stop, RATE * sr, s3)
        pc.animation(track, sit, stop, END, 1., 0.)
        # gameplay-model cat only after the POV
        final = bs['CosmeticCat']
        pc.visible_track(final, [(0, False), (RETURN, True)], END)
        # ---- ring on the portal plane when the cat bursts out
        # ---- cuts
        master = pc.only(t for t in seq.get_tracks() if isinstance(t, u.MovieSceneCameraCutTrack))
        cuts = sorted(master.get_sections(), key=lambda p: p.get_start_frame())
        spans = {'Entrance': (0, CUT_B), 'RearWalk': (CUT_B, CUT_C), 'Face': (CUT_C, POV), 'Puzzle': (POV, RETURN), 'FaceReturn': (RETURN, END)}
        for part, (name, span) in zip(cuts, spans.items(), strict=True):
            assert part.get_camera_binding_id().export_text() == seq.get_binding_id(bs[name]).export_text()
            part.set_range(*span)
        curves = {n: [look(*k) for k in CFG['cams'][n]] for n in ('Entrance', 'RearWalk', 'Face')}
        curves['Puzzle'] = [(f, [*rev.EYE, 0., p, y, 1., 1., 1.], fov) for a, b, p, y, fov in CFG['gaze'] for f in (a, b)]
        curves['FaceReturn'] = return_curve(gameplay)
        for name, curve in curves.items():
            comp = bs[name].get_object_template().get_editor_property('CameraComponent')
            pc.transform(bs[name], [(f, r) for f, r, _ in curve], END, pc.AUTO)
            persp = name != 'FaceReturn'
            comp.modify()
            if persp:
                comp.set_editor_property('projection_mode', u.CameraProjectionMode.PERSPECTIVE)
                comp.set_editor_property('field_of_view', curve[0][2])
            else:
                comp.set_editor_property('ortho_width', curve[0][2])
            if name + 'Lens' in bs:
                ch, = old.section(bs[name + 'Lens'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
                pc.keys(ch, [(f, w) for f, _, w in curve], pc.AUTO, curve[0][2])
            o = CFG['lens'].get(name, {})
            if o:
                pc.lens(comp, **o)
        # ---- lights
        for name, L in CFG['lights'].items():
            c = bs[name].get_object_template().get_editor_property('PointLightComponent')
            c.modify()
            c.set_light_color(u.LinearColor(*L['color'], 1.))
            c.set_attenuation_radius(L['radius'])
            c.set_editor_property('source_radius', L.get('source', 24.))
            c.set_intensity(max(k[1] for k in L['keys']))
            pc.transform(bs[name], [(f, (*p, 0., 0., 0., 1., 1., 1.)) for f, p in L['path']], END)
            ch, = old.section(bs[name + 'Bulb'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
            pc.keys(ch, [(f, v_) for f, v_ in L['keys']], pc.LINEAR, L['keys'][0][1])
        ch, = old.section(bs['BlueLight'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        pc.keys(ch, CFG['portal_light'], pc.LINEAR, CFG['portal_light'][0][1])
        # portal closes while it is still visible behind the walking cat
        C = CFG['portal_close']
        for name in (*old.PLANES, old.STYLE_COMPONENT):
            tr = pc.doubles(old.section(bs[name], u.MovieScene3DTransformTrack))
            base = [sorted((old.frameof(k), k.get_value()) for k in c.get_keys())[0][1] for c in tr[6:9]]
            rep.setdefault('portal_scale_base', {})[name] = base
            for c, b in zip(tr[6:9], base):
                flat = abs(b - 1.) < 1e-4 and c is not tr[6] and name in old.PLANES and c is tr[8]
                depth = name == old.STYLE_COMPONENT and c is tr[7]
                pc.keys(c, [(f, b if (flat or depth) else b * s) for f, s in C], pc.LINEAR, b)
        after = {n: old.guid(b) for n, b in old.bindings(seq).items()}
        assert all(after[n] == g for n, g in guids.items()), 'An existing binding GUID changed'
        pc.finish(seq, (), rep)
        rep.update(success=True, spans=spans, land_y=land_y, rows=[(f, r[1], r[2]) for f, r in rows], timing=T,
                   foot_z=FOOT, sequence_sha256=pc.sha(SEQ_FILE))
    except Exception:
        rep['error'] = traceback.format_exc()
        raise
    finally:
        (pc.OUT / ('author_stage2_dry.json' if pc.mode() == 'dry' else 'author_stage2.json')).write_text(json.dumps(rep, indent=1), encoding='utf-8')
        print('COMPACT_AUTHOR2', rep['success'], rep.get('land_y'), str(rep.get('error'))[-900:])


main()
