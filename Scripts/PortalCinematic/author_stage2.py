"""Stage2 portal arrival, slow 5-shot re-direction (2026-11-26).

Rebuilds LS_Stage2_PortalArrival from the pre-Compact base (Saved/PortalCinematic/Base, copied by run_author.ps1).
A1 room wide + portal opens | A2 cat bursts out and lands | A3 medium shake-off, then walks to the start spot |
A4 cat-eye pan statue -> plate -> gate | A5 crane to the orthographic 1170 gameplay view (BP hand-off 14.4 s).
The Refine cat performs A2..A3 (cinematic-only); the gameplay-model CosmeticCat appears only from A5, so the model
change happens during the point-of-view shot when no cat is on screen.
"""
import importlib
import json
import math
import sys
import traceback
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
ROOT = Path(u.Paths.project_dir()).resolve()
for q in (str(HERE), str(ROOT / 'Scripts/GameplayRepair'), str(ROOT / 'Scripts/Menu')):
    if q not in sys.path:
        sys.path.insert(0, q)
sys.dont_write_bytecode = True
import pcommon as pc
importlib.reload(pc)
import stage2_arrival_shots as old
import stage2_arrival_revision as rev

SEQ = '/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival'
SEQ_FILE = pc.pristine('Content/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival.uasset')
CFG = json.loads((HERE / 'shots_s2.json').read_text(encoding='utf-8'))
TRUTH = json.loads(Path(pc.SRC['truth']).read_text())
OLD_END = rev.END
OLD_PORTAL_END = rev.PORTAL_END
HANDOFF, CRANE_END, END = (CFG['handoff'][k] for k in ('frame', 'crane_end', 'end'))
assert abs(CFG['handoff']['seconds'] - HANDOFF / 30.) < 1e-6 and HANDOFF <= CRANE_END < END
OWNED = ('CompactArrivalCat', 'ArrivalExitRipple')
T = CFG['timing']
SPANS = {k: tuple(T[k]) for k in ('a1', 'a2', 'a3', 'a4', 'a5')}
assert SPANS['a5'][1] == END
REVEAL, TOUCH, LAND_END = T['reveal'], T['touchdown'], T['land_end']
POV, RETURN = SPANS['a4'][0], SPANS['a5'][0]
PLANE_Y, X, FOOT = 3980.75, 1375., 26.2 - 24. + CFG['ground_offset']
SCALE = 2.
RATE = CFG['walk_rate']
SPEED = .32685 * SCALE * RATE
END_Y = 3700.
EPS = 1. / 800


def smoother(t):
    t = min(1., max(0., t))
    return t * t * t * (t * (6. * t - 15.) + 10.)


def landing_shift(src):
    rows = TRUTH['AN_BlackCat_Landing']
    i = min(int(src), len(rows) - 2)
    a, b = rows[i]['paw_F_L'][1], rows[i + 1]['paw_F_L'][1]
    return 100. * SCALE * ((a + (b - a) * (src - i)) - rows[0]['paw_F_L'][1])


def cat_rows():
    rows = []
    n = TOUCH - REVEAL
    f0, lr = CFG['flight'], CFG['landing_rate']
    g2 = f0['height'] / (n * n)
    y0 = PLANE_Y + f0['behind']
    v0, v1 = f0['speed'], f0['speed_end']
    rows.append((0, y0, FOOT + f0['height'], 0.))
    for k in range(n + 1):
        y = y0 - (v0 * k + .5 * (v1 - v0) * k * k / n)
        rows.append((REVEAL + k, y, FOOT + f0['height'] - g2 * k * k, 0.))
    land_y = rows[-1][1]
    for f in range(TOUCH + 1, LAND_END + 1):
        rows.append((f, land_y - landing_shift(min(36., (f - TOUCH) * lr)), FOOT, 0.))
    landed = rows[-1][1]
    a3 = SPANS['a3'][0]
    rows.append((a3 - EPS, landed, FOOT, 0.))
    # A3: shake on the spot, then walk (eased start) to the gameplay start spot exactly at the POV cut.
    w0, w1 = T['walk']
    ramp = 8.
    steps = [SPEED * min(1., (f - w0 - .5) / ramp) for f in range(w0 + 1, w1 + 1)]
    shake_y = END_Y + sum(steps)
    rows.append((a3, shake_y, FOOT, 0.))
    s = CFG['shake']
    a, z = T['shake']
    for f in range(a, z + 1):
        t = (f - a) / (z - a)
        env = math.sin(math.pi * t) ** .7 * (1. - .45 * t)
        w = math.sin(2. * math.pi * (f - a) / s['period_frames'])
        rows.append((f, shake_y, FOOT + s['bob_cm'] * abs(w) * env, s['pitch_deg'] * w * env))
    rows.append((w0, shake_y, FOOT, 0.))
    y = shake_y
    for f, d in zip(range(w0 + 1, w1 + 1), steps):
        y -= d
        rows.append((f, y, FOOT, 0.))
    assert abs(rows[-1][1] - END_Y) < 1e-6
    rows.append((END, END_Y, FOOT, 0.))
    return [(f, (X, y, z, 0., p, -180., SCALE, SCALE, SCALE)) for f, y, z, p in rows], land_y, landed, shake_y


def eased(poses, step=2):
    """[(frame, values tuple)] -> dense rows, smootherstep between consecutive poses (identical poses = hold)."""
    out = []
    for i, ((f0, v0), (f1, v1)) in enumerate(zip(poses, poses[1:])):
        n = max(1, int(math.ceil((f1 - f0) / step)))
        last = i == len(poses) - 2
        for j in range(n + (1 if last else 0)):
            f = f0 + (f1 - f0) * j / n
            t = smoother(j / n)
            out.append((f, tuple(a + (b - a) * t for a, b in zip(v0, v1))))
    return out


def look(frame, eye, aim, fov):
    r = u.MathLibrary.find_look_at_rotation(u.Vector(*eye), u.Vector(*aim))
    return frame, [*eye, 0., r.pitch, r.yaw, 1., 1., 1.], fov


def move_curve(poses):
    dense = eased([(f, (*e, *a, fov)) for f, e, a, fov in poses])
    rows, prev = [], None
    for f, v in dense:
        fr, row, fov = look(f, v[:3], v[3:6], v[6])
        if prev is not None:
            row[5] = prev + (row[5] - prev + 180.) % 360. - 180.
        prev = row[5]
        rows.append((fr, row, fov))
    return rows


def gaze_curve():
    dense = eased([(f, (p, y, fov)) for f, p, y, fov in CFG['gaze']])
    return [(f, [*rev.EYE, 0., p, y, 1., 1., 1.], fov) for f, (p, y, fov) in dense]


def return_curve(gameplay):
    """Front hold, rise, then orbit to the exact gameplay view."""
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
    for f in (*range(hold + 3, CRANE_END, 3), CRANE_END):
        t = (f - hold) / (CRANE_END - hold)
        s = smoother(t)
        l = smoother(min(t / c.get('lift', .5), 1.))
        w = smoother(max(0., (t - c.get('width_delay', 0.)) / (1. - c.get('width_delay', 0.))))
        yaw, pitch = yaw0 + (yaw1 - yaw0) * s, pitch0 + (pitch1 - pitch0) * l
        radius = r0 + (r1 - r0) * s
        cx, cy, cz = [a + (b - a) * s for a, b in zip(subject, end)]
        eye = [cx - radius * math.cos(math.radians(yaw)), cy - radius * math.sin(math.radians(yaw)), cz - radius * math.tan(math.radians(pitch))]
        rows.append((f, [*eye, s * roll1, pitch, yaw, 1., 1., 1.], front[2] * (gameplay['width'] / front[2]) ** w))
    rows.append((END, rows[-1][1], rows[-1][2]))
    return rows


def main():
    rep = {'success': False, 'mode': pc.mode(), 'preexisting': pc.dirty()}
    assert pc.mode() == 'dry' or not pc.dirty(), pc.dirty()
    try:
        seq = u.load_asset(SEQ)
        bs = old.bindings(seq)
        previous_end = seq.get_playback_end()
        assert previous_end == OLD_END, previous_end
        guids = {n: old.guid(b) for n, b in bs.items() if n not in (*OWNED, 'ArrivalExitRippleMaterial')}
        fr = old.section(bs['FaceReturn'], u.MovieScene3DTransformTrack)
        last = [sorted((old.frameof(k), k.get_value()) for k in ch.get_keys())[-1] for ch in pc.doubles(fr)]
        wch, = old.section(bs['FaceReturnLens'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        width = sorted((old.frameof(k), k.get_value()) for k in wch.get_keys())[-1]
        v = [x for _, x in last]
        gameplay = {'xyz': v[:3], 'pyr': [v[4], v[5], v[3]], 'width': width[1]}
        rep['gameplay_view'] = gameplay
        assert abs(gameplay['width'] - 1170.) < .5, gameplay
        seq.modify()
        pc.drop(seq, OWNED)
        bs = old.bindings(seq)
        seq.set_playback_end(END)
        extended = []
        cosmetic_anim = pc.only(bs['CosmeticCat'].find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack))
        shift = CFG['cosmetic_anim_shift']
        for b in seq.get_bindings():
            for t in b.get_tracks():
                for sec in list(t.get_sections()):
                    a, z = sec.get_start_frame(), sec.get_end_frame()
                    if t == cosmetic_anim:
                        # gameplay-model cat: move its idle / gentle head reaction into the A5 crane
                        if a >= 250:
                            sec.set_range(a + shift, END if z >= OLD_END else z + shift)
                        elif z >= OLD_END - 120:
                            sec.set_end_frame(END if z >= OLD_END else z + shift)
                        extended.append([b.get_name(), 'anim', a, z, sec.get_start_frame(), sec.get_end_frame()])
                    elif z == OLD_END:
                        sec.set_end_frame(END)
                    elif z == OLD_PORTAL_END:
                        sec.set_end_frame(CFG['portal_hold_end'])
                        # keys that switched the portal off at the old end move to the new end
                        for ch in sec.get_all_channels():
                            for key in list(ch.get_keys()):
                                kf = key.get_time(u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value
                                if OLD_PORTAL_END - 3 <= kf <= OLD_PORTAL_END:
                                    key.set_time(u.FrameNumber(kf - OLD_PORTAL_END + CFG['portal_hold_end']), 0., u.MovieSceneTimeUnit.DISPLAY_RATE)
                                    extended.append([b.get_name(), 'key', kf, kf - OLD_PORTAL_END + CFG['portal_hold_end'], str(key.get_value())])
                        extended.append([b.get_name(), t.get_class().get_name(), a, z, sec.get_start_frame(), sec.get_end_frame()])
        for t in seq.get_tracks():
            for sec in t.get_sections():
                if sec.get_end_frame() == OLD_END:
                    sec.set_end_frame(END)
        # the portal used to switch off at 87 (planes hidden) / 91 (actor despawn): keep it until it has closed
        shift_keys = CFG['portal_hold_end'] - OLD_PORTAL_END
        for b in seq.get_bindings():
            if b.get_name() not in ('ArrivalPortal', 'Surface', 'PortalDepthCore', 'PortalAetherHalo', 'PortalOrbitSparks'):
                continue
            for t in b.get_tracks():
                if not isinstance(t, (u.MovieSceneVisibilityTrack, u.MovieSceneSpawnTrack)):
                    continue
                for sec in t.get_sections():
                    for ch in sec.get_all_channels():
                        for key in list(ch.get_keys()):
                            kf = key.get_time(u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value
                            if 80 <= kf <= OLD_PORTAL_END:
                                key.set_time(u.FrameNumber(kf + shift_keys), 0., u.MovieSceneTimeUnit.DISPLAY_RATE)
                                extended.append([b.get_name(), 'key', kf, kf + shift_keys, str(key.get_value())])
        rep['retimed_sections'] = extended
        # ---- black start (director holds black from BeginPlay), slow fade-in on the portal
        for t in [t for t in seq.get_tracks() if isinstance(t, u.MovieSceneFadeTrack)]:
            seq.remove_track(t)
        fade = seq.add_track(u.MovieSceneFadeTrack).add_section()
        fade.set_range(0, CFG['fade'][-1][0] + 2)
        fade.set_completion_mode(pc.RESTORE)
        pc.keys(pc.only(fade.get_all_channels()), CFG['fade'], pc.LINEAR, 1.)
        # ---- cinematic cat
        cat = pc.cat_spawnable(seq, 'CompactArrivalCat', END)
        rows, land_y, landed_y, shake_y = cat_rows()
        pc.transform(cat, rows, END)
        pc.visible_track(cat, [(0, False), (REVEAL, True), (POV, False)], END)
        track = cat.add_track(u.MovieSceneSkeletalAnimationTrack)
        mesh = cat.get_object_template().get_editor_property('skeletal_mesh_component').get_skeletal_mesh_asset()
        air, jump, land = pc.clip('AN_CompactPortal_AirReach'), pc.clip('AN_BlackCat_JumpDown'), pc.clip('AN_BlackCat_Landing')
        walk = pc.clip('AN_CompactPortal_WalkReview')
        idle = u.load_asset('/Game/Characters/BlackCat/Refine_20261125/AN_BlackCat_Idle')
        for c in (air, jump, land, walk, idle):
            assert c.get_editor_property('skeleton') == mesh.get_editor_property('skeleton'), c.get_name()
        wb = T['blend']
        n = TOUCH - REVEAL
        pc.animation(track, air, 0, REVEAL, 0., -4.)
        pc.animation(track, air, REVEAL - 2, REVEAL + 12, 1., 4., 2, 6)
        pc.animation(track, jump, REVEAL + 6, TOUCH, 15. / (n - 6), 24., 6, 0)
        pc.animation(track, land, TOUCH, LAND_END + wb, CFG['landing_rate'], 0., 0, wb)
        w0, w1 = T['walk']
        pc.animation(track, idle, LAND_END, w0 + wb, 1., 0., wb, wb)
        pc.animation(track, walk, w0, w1, RATE, 0., wb, 0)
        assert RATE * (w1 - w0) <= 119.5
        pc.visible_track(bs['CosmeticCat'], [(0, False), (RETURN, True)], END)
        # ---- cuts
        master = pc.only(t for t in seq.get_tracks() if isinstance(t, u.MovieSceneCameraCutTrack))
        cuts = sorted(master.get_sections(), key=lambda p: p.get_start_frame())
        names = ('Entrance', 'RearWalk', 'Face', 'Puzzle', 'FaceReturn')
        span_of = dict(zip(names, (SPANS[k] for k in ('a1', 'a2', 'a3', 'a4', 'a5'))))
        for part, name in zip(cuts, names, strict=True):
            assert part.get_camera_binding_id().export_text() == seq.get_binding_id(bs[name]).export_text()
            part.set_range(*span_of[name])
        curves = {n_: move_curve(CFG['cams'][n_]) for n_ in ('Entrance', 'RearWalk', 'Face')}
        curves['Puzzle'] = gaze_curve()
        curves['FaceReturn'] = return_curve(gameplay)
        rep['distance_cm'] = {}
        for name, curve in curves.items():
            comp = bs[name].get_object_template().get_editor_property('CameraComponent')
            interp = pc.AUTO if name == 'FaceReturn' else pc.LINEAR
            pc.transform(bs[name], [(f, r) for f, r, _ in curve], END, interp)
            persp = name != 'FaceReturn'
            comp.modify()
            if persp:
                comp.set_editor_property('projection_mode', u.CameraProjectionMode.PERSPECTIVE)
                comp.set_editor_property('field_of_view', curve[0][2])
            else:
                comp.set_editor_property('ortho_width', curve[0][2])
            if name + 'Lens' in bs:
                ch, = old.section(bs[name + 'Lens'], u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
                pc.keys(ch, [(f, w) for f, _, w in curve], interp, curve[0][2])
            o = CFG['lens'].get(name, {})
            if o:
                pc.lens(comp, **o)
            if name in CFG['cams']:
                a, z = span_of[name]
                mid = min(curve, key=lambda r: abs(r[0] - (a + z) / 2.))
                cy = next(r[1][1] for r in sorted(rows, key=lambda r: abs(r[0] - mid[0]))[:1])
                rep['distance_cm'][name] = round(math.dist(mid[1][:3], (X, cy, FOOT + 12.)), 1)
        rep['lens_bindings'] = sorted(n_ for n_ in bs if n_.endswith('Lens'))
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
            old.section(bs[name + 'Bulb'], u.MovieSceneFloatTrack).set_range(0, END)
            pc.keys(ch, [(f, float(v_)) for f, v_ in L['keys']], pc.LINEAR, float(L['keys'][0][1]))
        bl = old.section(bs['BlueLight'], u.MovieSceneFloatTrack)
        ch, = bl.get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        pc.keys(ch, [(f, float(v_)) for f, v_ in CFG['portal_light']], pc.LINEAR, float(CFG['portal_light'][0][1]))
        # portal opens in A1, holds, closes behind the cat during A3
        C = CFG['portal_scale']
        for name in (*old.PLANES, old.STYLE_COMPONENT):
            sec = old.section(bs[name], u.MovieScene3DTransformTrack)
            tr = pc.doubles(sec)
            base = [sorted((old.frameof(k), k.get_value()) for k in c.get_keys())[0][1] if c.get_keys() else c.get_default() for c in tr[6:9]]
            rep.setdefault('portal_scale_base', {})[name] = base
            for c, b in zip(tr[6:9], base):
                flat = abs(b - 1.) < 1e-4 and c is not tr[6] and name in old.PLANES and c is tr[8]
                depth = name == old.STYLE_COMPONENT and c is tr[7]
                pc.keys(c, [(f, b if (flat or depth) else b * s) for f, s in C], pc.LINEAR, b)
            rep.setdefault('portal_ranges', {})[name] = [sec.get_start_frame(), sec.get_end_frame()]
        after = {n_: old.guid(b) for n_, b in old.bindings(seq).items()}
        assert all(after[n_] == g for n_, g in guids.items()), 'An existing binding GUID changed'
        pc.finish(seq, (), rep)
        rep.update(success=True, end=END, seconds=END / 30., spans=span_of, land_y=land_y, landed_y=landed_y, shake_y=shake_y,
                   cut_skip_cm=round(landed_y - shake_y, 1), rows=[(f, r[1], r[2], r[4]) for f, r in rows], timing=T,
                   foot_z=FOOT, handoff=CFG['handoff'], sequence_sha256=pc.sha(SEQ_FILE))
    except Exception:
        rep['error'] = traceback.format_exc()
        raise
    finally:
        (pc.OUT / ('author_stage2_dry.json' if pc.mode() == 'dry' else 'author_stage2.json')).write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
        print('PORTALCINE_S2', rep['success'], rep.get('end'), rep.get('cut_skip_cm'), str(rep.get('error'))[-1200:])


main()
