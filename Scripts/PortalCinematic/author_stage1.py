"""Stage1 portal exit, slow 5-shot re-direction (2026-11-26).

Rebuilds LS_Stage1_PortalExit from the pre-Compact base (Saved/PortalCinematic/Base, copied over the package by
run_author.ps1 before the editor starts). The gameplay pawn stays hidden and only drives position; the cinematic-only
Refine cat (existing mesh/skeleton, unchanged) is attached and animated. All cameras are world-space and far from the cat.

S1 corridor wide + door closes | S2 medium look-back | S3 low wide portal reveal | S4 side two-shot hesitation with a
<1 s face insert | S5 leap + flash -> black.
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
import stage1_departure_shots as old

h = old.h
h.CAMERAS = old.CAMERA_NAMES            # DoorFace, FrontTracking, RearPortal, JumpFollow
OUT, FOLDER = pc.OUT, pc.FOLDER
SEQ = '/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit'
SEQ_FILE = pc.pristine('Content/Cinematics/Stage1/Portal/LS_Stage1_PortalExit.uasset')
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
OWNED = ('CompactPortalCat', 'CompactPawRipple', 'CompactEntryRipple', 'PortalOrbitSparks')
CFG = json.loads((HERE / 'shots_s1.json').read_text(encoding='utf-8'))
HAND = json.loads((HERE / 'handoff.json').read_text(encoding='utf-8'))
T = CFG['timing']
PM = {'location': [0., 0., -24. + CFG['ground_offset']], 'rotation': [0., 0., -90.], 'scale': [2., 2., 2.]}
SCALE = PM['scale'][0]
Z0 = 25.2
EPS = 1. / 800
# ---- timing
STOP = T['stop']
SPLIT = STOP + T['sit_split_source'] / T['sit_rate']
assert abs(SPLIT - round(SPLIT)) < 1e-6
SPLIT = round(SPLIT)
PREP = SPLIT + (91 - T['sit_split_source'])      # SeatedListenTouch ends (91 source frames)
TAKE = PREP + 53                                  # HipsBackWiggle 53 frames
AIR = TAKE + 12                                   # SeatedTakeoff
AIR_FRAMES = T['air_frames']
AIR_END = AIR + AIR_FRAMES
END = T['s5'][1]
LAST_GROUND = TAKE + HAND['timing']['last_hind_ground_frame'] - 1
assert T['fade'][1] < END and AIR_END <= END, (AIR_END, END)
SPANS = {k: tuple(T[k]) for k in ('s1', 's2', 's3', 's4a', 'insert', 's4b', 's5')}
assert [SPANS[k][1] for k in list(SPANS)[:-1]] == [SPANS[k][0] for k in list(SPANS)[1:]]
assert SPANS['insert'][1] - SPANS['insert'][0] <= 30, 'face insert must stay under one second'
# ---- geometry (BP_Stage1PortalPresentation Surface plane)
PORTAL_Y = -373.1
STANCE = .32685 * SCALE
RATE, SLOW_RATE = CFG['walk_rate'], CFG['slow_rate']
SPEED = STANCE * RATE
STOP_Y = PORTAL_Y - SCALE * 100. * HAND['contact']['portal_plane_y_m']
Y0 = CFG['start_y']


def smoother(t):
    t = min(1., max(0., t))
    return t * t * t * (t * (6. * t - 15.) + 10.)


def lerp3(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def pawn_path():
    """Piecewise-linear pawn root (frame, y, z). Speed always equals stance x clip rate (planted paws)."""
    look_y = Y0 - SPEED * T['walk_slow'] - SPEED * SLOW_RATE * (T['walk_stop'] - T['walk_slow'])
    resume = T['resume']
    s2_end = SPANS['s2'][1]
    resume_y = look_y - SPEED * .5 * (s2_end - resume)          # eased start, roughly half speed on average
    s3_y = STOP_Y + SPEED * (T['s3_slow'] - SPANS['s3'][0]) + SPEED * SLOW_RATE * (STOP - T['s3_slow'])
    rows = [(0, Y0, Z0), (T['walk_slow'], Y0 - SPEED * T['walk_slow'], Z0), (T['walk_stop'], look_y, Z0),
            (resume, look_y, Z0), (s2_end - EPS, resume_y, Z0), (s2_end, s3_y, Z0),
            (T['s3_slow'], STOP_Y + SPEED * SLOW_RATE * (STOP - T['s3_slow']), Z0), (STOP, STOP_Y, Z0), (LAST_GROUND, STOP_Y, Z0)]
    k = CFG['jump']
    t_lift = AIR - LAST_GROUND
    total = AIR_END - LAST_GROUND
    for f in range(LAST_GROUND + 1, AIR_END + 1):
        n = f - LAST_GROUND
        if n <= t_lift:
            y = k['push_forward'] * (n / t_lift) ** 2
            up = k['push_up'] * (n / t_lift) ** 1.6
        else:
            s = n - t_lift
            v_up = k['push_up'] * 1.6 / t_lift
            v_fw = k['push_forward'] * 2. / t_lift
            air = total - t_lift
            up = k['push_up'] + v_up * s - .5 * (v_up / k['apex_frames']) * s * s
            extra = k['forward'] - k['push_forward'] - v_fw * air
            y = k['push_forward'] + v_fw * s + extra * (s / air) ** k['forward_power']
        rows.append((f, STOP_Y - y, Z0 + up))
    rows.append((END, rows[-1][1], rows[-1][2]))
    return rows, look_y, s3_y


def nominal(frame, rows):
    return (h.interpolate([(f, y) for f, y, _ in rows], frame), h.interpolate([(f, z) for f, _, z in rows], frame))


def axes(section, rows, interp=pc.LINEAR):
    section.set_range(0, END)
    section.set_completion_mode(RESTORE)
    for i, ch in enumerate(h.transform_channels(section)):
        pc.keys(ch, [(f, float(r[i])) for f, r in rows], interp, float(rows[0][1][i]))


def unwrap(rows):
    out, prev = [], None
    for f, r in rows:
        r = list(r)
        if prev is not None:
            r[5] = prev + (r[5] - prev + 180.) % 360. - 180.
        prev = r[5]
        out.append((f, tuple(r)))
    return out


def camera_rows(spans):
    """Eased moves between [frame, eye, aim] poses, sampled every 2 frames; LINEAR keys -> no overshoot."""
    rows = []
    for _, poses in spans:
        for (f0, e0, a0), (f1, e1, a1) in zip(poses, poses[1:]):
            n = max(1, int(math.ceil((f1 - f0) / 2.)))
            for i in range(n + (1 if (f1, e1, a1) == tuple(poses[-1]) else 0)):
                f = f0 + (f1 - f0) * i / n
                t = smoother((f - f0) / (f1 - f0))
                rows.append(h.camera_key(f, lerp3(e0, e1, t), lerp3(a0, a1, t)))
    return unwrap(sorted(rows, key=lambda r: r[0]))


def add_cat(seq, pawn_binding):
    b = pc.cat_spawnable(seq, 'CompactPortalCat', END)
    attach = b.add_track(u.MovieScene3DAttachTrack).add_section()
    attach.set_range(0, END)
    attach.set_completion_mode(RESTORE)
    attach.set_constraint_binding_id(seq.get_binding_id(pawn_binding))
    for p in ('attachment_location_rule', 'attachment_rotation_rule', 'attachment_scale_rule'):
        attach.set_editor_property(p, u.AttachmentRule.KEEP_RELATIVE)
    # Look-back: the cat turns its body toward the closed door and back (relative yaw about its own centre).
    base = (*PM['location'], *PM['rotation'], *PM['scale'])
    yaw0, turn = PM['rotation'][2], CFG['look_back_yaw']
    rel = [(0, base)]
    for (a, z), sign in ((T['turn_out'], 1.), (T['turn_back'], -1.)):
        for i in range(0, 13):
            f = a + (z - a) * i / 12.
            t = smoother(i / 12.)
            yaw = yaw0 + turn * (t if sign > 0 else 1. - t)
            rel.append((f, (*base[:5], yaw, *base[6:])))
    rel.append((END, base))
    axes(b.add_track(u.MovieScene3DTransformTrack).add_section(), rel)
    track = b.add_track(u.MovieSceneSkeletalAnimationTrack)
    walk = pc.clip('AN_CompactPortal_WalkReview')
    mesh = b.get_object_template().get_editor_property('skeletal_mesh_component').get_skeletal_mesh_asset()
    idle = u.load_asset('/Game/Characters/BlackCat/Refine_20261125/AN_BlackCat_Idle')
    assert isinstance(idle, u.AnimSequence) and idle.get_editor_property('skeleton') == mesh.get_editor_property('skeleton'), 'Refine idle skeleton'
    sit, wig, take, air = (pc.clip('AN_CompactPortal_' + n) for n in ('SeatedListenTouch', 'HipsBackWiggle', 'SeatedTakeoff', 'AirReach'))
    for c in (walk, sit, wig, take, air):
        assert c.get_editor_property('skeleton') == mesh.get_editor_property('skeleton'), c.get_name()
    R, ws, wt = RATE, T['walk_slow'], T['walk_stop']
    s3_0, s3_slow = SPANS['s3'][0], T['s3_slow']
    s3_src = 119. - R * SLOW_RATE * (STOP - s3_slow)
    s3_start = s3_src - R * (s3_slow - s3_0)
    assert s3_start >= 0, s3_start
    rows = [
        # gait: 24-frame period, phase kept across the seam at 60
        (walk, 0, 64, R, 0., 0, 4),
        (walk, 60, ws, R, R * 60 - 48., 4, 0),
        (walk, ws, wt + 2, R * SLOW_RATE, R * 60 - 48. + R * (ws - 60), 0, 8),
        (idle, wt - 6, T['resume'] + 6, 1., 0., 8, 6),
        (walk, T['turn_out'][0], T['turn_out'][1], .55, 0., 6, 6),       # paws step while the body turns
        (walk, T['turn_back'][0], T['turn_back'][1], .55, 24., 6, 6),
        (walk, T['resume'], s3_0, R, 48., 6, 0),
        (walk, s3_0, s3_slow, R, s3_start, 0, 0),
        (walk, s3_slow, STOP, R * SLOW_RATE, s3_src, 0, 0),
        (sit, STOP, SPLIT, T['sit_rate'], 0., 0, 0),
        (sit, SPLIT, PREP, 1., float(T['sit_split_source']), 0, 0),
        (wig, PREP, TAKE, 1., 0., 0, 0),
        (take, TAKE, AIR, 1., 0., 0, 0),
        (air, AIR, AIR_END, 18. / AIR_FRAMES, 0., 0, 0),
        (air, AIR_END, END, 0., -(18. - 1. / 800), 0, 0),
    ]
    for c, a, z, r, src, ein, eout in rows:
        if c is walk and r > 0:
            assert src + r * (z - a) <= 119.5, (a, z, src)
        pc.animation(track, c, a, z, r, src, ein, eout)
    return [(c.get_name(), a, z, r, src) for c, a, z, r, src, _, _ in rows]


def hide_sparks(seq, portal):
    """Hide the portal spark cards only for the face insert (camera is near their ring)."""
    actor = pc.only(a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                    if a.get_class().get_name() == 'BP_Stage1PortalPresentation_C')
    comp = pc.only(c for c in actor.get_components_by_class(u.StaticMeshComponent) if c.get_name() == 'PortalOrbitSparks')
    gid = lambda b: b.get_id().export_text()
    before = {gid(b) for b in seq.get_bindings()}
    child = seq.add_possessable(comp)
    auto = child.get_parent()
    assert gid(child) not in before
    if gid(auto) != gid(portal):
        assert gid(auto) not in before and {gid(b) for b in auto.get_child_possessables()} == {gid(child)}
        child.set_parent(portal)
        auto.remove()
    child.set_name('PortalOrbitSparks')
    t = child.add_track(u.MovieSceneVisibilityTrack)
    t.set_property_name_and_path('bHiddenInGame', 'bHiddenInGame')
    s = t.add_section()
    s.set_range(0, END)
    s.set_completion_mode(RESTORE)
    ch = h.only(s.get_all_channels())
    ch.set_default(True)
    for f, v in ((0, True), (SPANS['insert'][0], False), (SPANS['insert'][1], True)):
        ch.add_key(u.FrameNumber(f), v)
    return list(SPANS['insert'])


def retime_door(seq):
    """The door leaves closed over 0..39; stretch that to door_close_frames so S1 shows the whole closure."""
    k = CFG['door_close_frames'] / 39.
    out = {}
    for tag in (old.DOOR_TAG, old.RIGHT_TAG):
        b = pc.only(b for b in seq.get_bindings() if tag in map(str, b.get_binding_tags()))
        for sec in pc.only(b.find_tracks_by_type(u.MovieScene3DTransformTrack)).get_sections():
            for ch in sec.get_channels_by_type(u.MovieSceneScriptingDoubleChannel):
                rows = [(key.get_time(pc.TICKS).frame_number.value / 800., key.get_value()) for key in ch.get_keys()]
                if not rows:
                    continue
                moved = [(f * k if f <= 39.5 else f, v) for f, v in rows]
                assert all(a[0] < b_[0] for a, b_ in zip(moved, moved[1:])), moved
                pc.keys(ch, moved, pc.LINEAR, ch.get_default() if ch.has_default() else moved[0][1])
        out[tag] = b.get_name()
    return out


def cinematic_timeout():
    actor = pc.only(a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                    if a.get_class().get_name() == 'BP_Stage1PortalExit_C')
    return float(actor.get_editor_property('CinematicTimeout'))


def main():
    rep = {'success': False, 'mode': pc.mode(), 'preexisting': pc.dirty()}
    assert pc.mode() == 'dry' or not pc.dirty(), pc.dirty()
    ed_ = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed_.get_editor_world().get_path_name().split('.')[0] != '/Game/Maps/Stage1':
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage1')
    assert not pc.dirty(), pc.dirty()
    try:
        rep['cinematic_timeout_s'] = cinematic_timeout()
        assert rep['cinematic_timeout_s'] > END / 30. + 1., ('BP CinematicTimeout too short for the new length', rep['cinematic_timeout_s'])
        seq = u.load_asset(SEQ)
        parts = h.sequence_parts(seq)
        before = {'end': seq.get_playback_end(), 'bindings': {b.get_name(): b.get_id().export_text() for b in parts['bindings']}}
        assert before['end'] == 312, before['end']
        seq.modify()
        pc.drop(seq, OWNED)
        seq.set_playback_end(END)
        for b in seq.get_bindings():
            for t in b.get_tracks():
                for s in t.get_sections():
                    if s.get_end_frame() == before['end']:
                        s.set_end_frame(END)
        pawn = parts['bindings'][0]
        anims = sorted(parts['anim_track'].get_sections(), key=h.span)
        for s in anims[1:]:
            parts['anim_track'].remove_section(s)
        anims[0].set_range(0, END)
        h.EASING.set_ease_out_duration(anims[0], 0)
        hidden = h.only(h.property_section(pawn, u.MovieSceneVisibilityTrack).get_all_channels())
        for k in list(hidden.get_keys()):
            hidden.remove_key(k)
        hidden.set_default(False)
        hidden.add_key(u.FrameNumber(0), False)
        rows, look_y, s3_y = pawn_path()
        ch = h.transform_channels(parts['cat'])
        pc.keys(ch[1], [(f, y) for f, y, _ in rows])
        pc.keys(ch[2], [(f, z) for f, _, z in rows])
        h.EASING.set_ease_in_duration(parts['cat'], h.tick(CFG['pawn_ease_in']))
        rep['animation'] = add_cat(seq, pawn)
        rep['door'] = retime_door(seq)
        # ---- cameras: world space only (drop the old pawn attachments), 7 cuts over 4 bindings
        cams = dict(zip(old.CAMERA_NAMES, parts['bindings'][3:]))
        comps = dict(zip(old.CAMERA_NAMES, parts['camera_components']))
        secs = dict(zip(old.CAMERA_NAMES, parts['camera_sections']))
        rep['cameras'] = {}
        for name, b in cams.items():
            for t in b.find_tracks_by_type(u.MovieScene3DAttachTrack):
                b.remove_track(t)
            c = CFG['cameras'][name]
            curve = camera_rows(c['spans'])
            axes(secs[name], curve)
            comp = comps[name]
            comp.modify()
            comp.set_field_of_view(c['fov'])
            pc.lens(comp, focus=c['focus'], fstop=c['fstop'], blur=.03, exposure=c['exposure'])
            spawn = h.property_section(b, u.MovieSceneSpawnTrack)
            spawn.set_range(0, END)
            rep['cameras'][name] = {'fov': c['fov'], 'keys': len(curve)}
        cut_track = pc.only(t for t in seq.get_tracks() if isinstance(t, u.MovieSceneCameraCutTrack))
        for s in list(cut_track.get_sections()):
            cut_track.remove_section(s)
        rep['cuts'] = []
        for name, span in CFG['cuts']:
            s = cut_track.add_section()
            s.set_range(*SPANS[span])
            s.set_camera_binding_id(seq.get_binding_id(cams[name]))
            s.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)
            rep['cuts'].append([span, name, *SPANS[span]])
        # subject distance per shot (eye -> cat root at mid-shot), for the report
        rep['distance_cm'] = {}
        for name, span in CFG['cuts']:
            a, z = SPANS[span]
            f = (a + z) / 2.
            cv = camera_rows(CFG['cameras'][name]['spans'])
            e = [h.interpolate([(k[0], k[1][i]) for k in cv], f) for i in range(3)]
            y, zz = nominal(f, rows)
            rep['distance_cm'][span] = round(math.dist(e, (101., y, zz - 15.)), 1)
        # ---- lights, parented to the portal actor (yaw 180, 1.25 scale)
        L = CFG['light']

        def local(p3):
            return ((101. - p3[0]) / 1.25, (PORTAL_Y - p3[1]) / 1.25, (p3[2] + .8) / 1.25, 0., 0., 0., 1., 1., 1.)

        def stage(f):
            return 'walk' if f < SPANS['s3'][0] else 'touch' if f < SPANS['s5'][0] else 'prep'
        frames = sorted({*range(0, END, 6), *(a for a, _ in SPANS.values()), *(s - EPS for s in (SPANS['s3'][0], SPANS['s5'][0])), END})
        blue, fill = [], []
        for f in frames:
            y, z = nominal(f, rows)
            for out_, key in ((blue, 'blue_pos'), (fill, 'fill_pos')):
                o = L[key][stage(f)]
                out_.append((f, local((o[0], y + o[1], z + o[2]))))
        axes(parts['light_transform'], blue)
        axes(h.property_section(old.fill_binding(seq), u.MovieScene3DTransformTrack), fill)
        parts['light'].set_range(0, END)
        pc.keys(h.only(parts['light'].get_all_channels()), [(f, float(v)) for f, v in L['blue']], pc.LINEAR, 300.)
        fs = h.property_section(old.fill_binding(seq), u.MovieSceneFloatTrack)
        fs.set_range(0, END)
        pc.keys(h.only(fs.get_all_channels()), [(f, float(v)) for f, v in L['fill']], pc.LINEAR, 320.)
        a, z = T['fade']
        parts['fade'].set_range(a, END)
        pc.keys(h.only(parts['fade'].get_all_channels()), [(a, 0.), (z, 1.), (END, 1.)])
        rep['sparks_hidden'] = hide_sparks(seq, parts['bindings'][1])
        now = {'bindings': {b.get_name(): b.get_id().export_text() for b in parts['bindings']}}
        assert now['bindings'] == before['bindings'], 'An existing binding GUID changed'
        pc.finish(seq, (), rep)
        rep.update(success=True, end=END, seconds=END / 30.,
                   timing=dict(spans=SPANS, stop=STOP, split=SPLIT, prep=PREP, take=TAKE, last_ground=LAST_GROUND, air=AIR,
                               air_end=AIR_END, end=END, **{k: T[k] for k in ('walk_slow', 'walk_stop', 'turn_out', 'turn_back', 'resume', 'fade')}),
                   speed_cm_per_frame=SPEED, stop_y=STOP_Y, look_back_y=look_y, s3_start_y=s3_y, cut_skip_cm=round(look_y - s3_y, 1),
                   path=rows, sequence_sha256=pc.sha(SEQ_FILE), bindings=now['bindings'])
    except Exception:
        rep['error'] = traceback.format_exc()
        raise
    finally:
        (OUT / ('author_stage1_dry.json' if pc.mode() == 'dry' else 'author_stage1.json')).write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
        print('PORTALCINE_S1', rep['success'], rep.get('end'), rep.get('cut_skip_cm'), str(rep.get('error'))[-1200:])


main()
