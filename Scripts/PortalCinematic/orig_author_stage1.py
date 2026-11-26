"""Edit the candidate's physical copy of LS_Stage1_PortalExit for the Compact cat.

Always restarts from the pristine main copy in Saved/CompactPortal/Before, so it can be re-run.
Gameplay pawn keeps mesh/skeleton; it is hidden and drives an attached cinematic-only spawnable.
"""
import hashlib
import json
import math
import shutil
import sys
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
assert 'CompactPortal_20261125' in str(ROOT)
TOOLS = Path('C:/Users/whghk/.codex/workspaces/CompactPortal_20261125/Tools')
for q in (str(TOOLS), str(ROOT / 'Scripts/GameplayRepair')):
    if q not in sys.path:
        sys.path.insert(0, q)
sys.dont_write_bytecode = True
import importlib
import stubs
import pcommon as pc
importlib.reload(pc)
OUT, FOLDER = pc.OUT, pc.FOLDER
SEQ = '/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit'
SEQ_FILE = pc.pristine('Content/Cinematics/Stage1/Portal/LS_Stage1_PortalExit.uasset')
import stage1_departure_shots as old

h = old.h
h.CAMERAS = old.CAMERA_NAMES
AS = u.EditorAssetLibrary
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
sha = pc.sha
OWNED = ('CompactPortalCat', 'CompactPawRipple', 'CompactEntryRipple', 'PortalOrbitSparks')
CFG = json.loads((TOOLS / 'shots.json').read_text(encoding='utf-8'))
IMP = json.loads((OUT / 'import_report.json').read_text(encoding='utf-8'))
HAND = json.loads((ROOT / 'SourceArt/CompactPortal/handoff.json').read_text(encoding='utf-8'))
PM = IMP['pawn_mesh']
PM['location'][2] += CFG['ground_offset']  # pawn capsule rests 2.1 cm above the visible floor (top -0.9)
SCALE = PM['scale'][0]
FLOOR_Z = 25.2 + PM['location'][2]
# ---- timing (30 fps)
WALK_START, CUT, STOP = CFG['walk_start'], CFG['cut'], CFG['stop']
PREP = STOP + CFG['listen_frames']      # SeatedListenTouch frames 1..91
TAKE = PREP + 52      # HipsBackWiggle 1..53
AIR = TAKE + 12       # SeatedTakeoff 1..13
AIR_FRAMES = CFG['air_frames']
AIR_END = AIR + AIR_FRAMES
END = AIR_END + CFG['tail_frames']
LAST_GROUND = TAKE + HAND['timing']['last_hind_ground_frame'] - 1
CONTACT = (STOP + HAND['timing']['contact'][0] - 1, STOP + HAND['timing']['contact'][1] - 1)
assert 270 <= END <= 360, END
# ---- geometry (measured: BP_Stage1PortalPresentation.Surface plane)
PORTAL_Y = -373.1
STANCE = .32685 * SCALE          # cm per frame of planted paws at rate 1 (pose_samples)
RATE = CFG['walk_rate']
SPEED = STANCE * RATE
STOP_Y = PORTAL_Y - SCALE * 100. * HAND['contact']['portal_plane_y_m']
WALK_Y = old.START_Y - SPEED * CUT
SLOW, SLOW_RATE = CFG['slow_frames'], CFG['slow_rate']
APPROACH_Y = STOP_Y + SPEED * (STOP - SLOW - CUT) + SPEED * SLOW_RATE * SLOW


def dirty():
    return sorted(p.get_path_name() for p in (*u.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                                              *u.EditorLoadingAndSavingUtils.get_dirty_map_packages()))


def keys(channel, rows, interp=u.MovieSceneKeyInterpolation.LINEAR, default=None):
    for k in list(channel.get_keys()):
        channel.remove_key(k)
    if default is not None:
        channel.set_default(default)
    for f, v in rows:
        channel.add_key(u.FrameNumber(h.tick(f)), v, 0., u.MovieSceneTimeUnit.TICK_RESOLUTION, interp)


def axes(section, rows):
    section.set_range(0, END)
    section.set_completion_mode(RESTORE)
    for i, ch in enumerate(h.transform_channels(section)):
        keys(ch, [(f, r[i]) for f, r in rows], default=rows[0][1][i])


def animation(track, clip, first, last, rate, source):
    s = track.add_section()
    s.set_range(first, last)
    s.set_completion_mode(RESTORE)
    p = u.MovieSceneSkeletalAnimationParams()
    for n, v in (('animation', clip), ('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp(rate)),
                 ('start_frame_offset', u.FrameNumber(h.tick(max(0., source)))),
                 ('first_loop_start_frame_offset', u.FrameNumber(h.tick(max(0., -source)))),  # negative source = frozen pose
                 ('force_custom_mode', True), ('skip_anim_notifiers', True)):
        p.set_editor_property(n, v)
    s.set_editor_property('params', p)
    return s


def clip(name):
    c = u.load_asset(f'{FOLDER}/AN_CompactPortal_{name}')
    assert isinstance(c, u.AnimSequence), name
    return c


def path():
    """Nominal pawn root path [(frame, y, z)]; y before CUT is the ease target behaviour."""
    z = 25.2
    rows = [(CUT, APPROACH_Y, z), (STOP - SLOW, STOP_Y + SPEED * SLOW_RATE * SLOW, z), (STOP, STOP_Y, z),
            (LAST_GROUND, STOP_Y, z)]
    k = CFG['jump']
    t_lift = AIR - LAST_GROUND            # rest of the takeoff clip
    total = AIR_END - LAST_GROUND
    for f in range(LAST_GROUND + 1, AIR_END + 1):
        n = f - LAST_GROUND
        # constant initial acceleration through the push, then a ballistic rise
        if n <= t_lift:
            y = k['push_forward'] * (n / t_lift) ** 2
            up = k['push_up'] * (n / t_lift) ** 1.6
        else:
            s = n - t_lift
            v_up = k['push_up'] * 1.6 / t_lift
            v_fw = k['push_forward'] * 2. / t_lift
            air = total - t_lift
            peak = k['apex_frames']
            up = k['push_up'] + v_up * s - .5 * (v_up / peak) * s * s
            extra = k['forward'] - k['push_forward'] - v_fw * air
            y = k['push_forward'] + v_fw * s + extra * (s / air) ** k['forward_power']
        rows.append((f, STOP_Y - y, z + up))
    rows.append((END, rows[-1][1], rows[-1][2]))
    return rows


def nominal(frame, rows):
    if frame < CUT:
        return old.START_Y + (WALK_Y - old.START_Y) * frame / CUT, 25.2
    return (h.interpolate([(f, y) for f, y, _ in rows], frame), h.interpolate([(f, z) for f, _, z in rows], frame))


def spawn(binding, first, last):
    s = h.property_section(binding, u.MovieSceneSpawnTrack)
    s.set_range(first, last)
    s.set_completion_mode(RESTORE)
    h.only(s.get_all_channels()).set_default(True)


def no_collision(actor, comp):
    actor.set_actor_enable_collision(False)
    comp.set_collision_profile_name('NoCollision')
    comp.set_editor_property('generate_overlap_events', False)


def add_cat(seq, pawn_binding):
    b = pc.cat_spawnable(seq, 'CompactPortalCat', END)
    attach = b.add_track(u.MovieScene3DAttachTrack).add_section()
    attach.set_range(0, END)
    attach.set_completion_mode(RESTORE)
    attach.set_constraint_binding_id(seq.get_binding_id(pawn_binding))
    for p in ('attachment_location_rule', 'attachment_rotation_rule', 'attachment_scale_rule'):
        attach.set_editor_property(p, u.AttachmentRule.KEEP_RELATIVE)
    rel = (*PM['location'], *PM['rotation'], *PM['scale'])
    axes(b.add_track(u.MovieScene3DTransformTrack).add_section(), [(0, rel)])
    track = b.add_track(u.MovieSceneSkeletalAnimationTrack)
    walk = clip('WalkReview')
    # Seamless gait: source 0..119 has a 24-frame period; source 119 equals the sit clip's first pose.
    s3 = 119. - RATE * SLOW_RATE * SLOW
    f2 = STOP - SLOW
    split = CFG['walk_split']
    s2 = s3 - RATE * (f2 - split)
    assert s2 >= 0, s2
    n = math.ceil((RATE * split - s2) / 24.)
    s1_end = s2 + 24. * max(n, 0)
    s1 = s1_end - RATE * split
    BLEND = 4  # legs match exactly; only the freely moving tail needs the cross-fade
    assert 0 <= s1 and s1_end + BLEND * RATE <= 119.5, (s1, s1_end)
    pc.animation(track, walk, 0, split + BLEND, RATE, s1, 0, BLEND)
    pc.animation(track, walk, split, f2, RATE, s2, BLEND, 0)
    sections = [(f2, STOP, walk, RATE * SLOW_RATE, s3),
                (STOP, PREP, clip('SeatedListenTouch'), 1., 0.), (PREP, TAKE, clip('HipsBackWiggle'), 1., 0.),
                (TAKE, AIR, clip('SeatedTakeoff'), 1., 0.), (AIR, AIR_END, clip('AirReach'), 18. / AIR_FRAMES, 0.),
                (AIR_END, END, clip('AirReach'), 0., -(18. - 1. / 800))]
    for a, z, c, r, src in sections:
        animation(track, c, a, z, r, src)
    return [(a, z, c.get_name(), r, src) for a, z, c, r, src in sections]


def hide_sparks(seq, portal):
    """The touch camera stands inside the portal's spark ring; hide only those cards during that cut."""
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_editor_world().get_path_name().split('.')[0] != '/Game/Maps/Stage1':
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage1')
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
    assert {gid(b) for b in seq.get_bindings()} == before | {gid(child)}
    t = child.add_track(u.MovieSceneVisibilityTrack)
    t.set_property_name_and_path('bHiddenInGame', 'bHiddenInGame')
    s = t.add_section()
    s.set_range(0, END)
    s.set_completion_mode(RESTORE)
    ch = h.only(s.get_all_channels())
    ch.set_default(True)
    for f, v in ((0, True), (CUT, False), (PREP, True)):
        ch.add_key(u.FrameNumber(f), v)
    return [CUT, PREP]


def main():
    rep = {'success': False, 'mode': pc.mode(), 'preexisting': dirty()}
    assert pc.mode() == 'dry' or not dirty(), dirty()
    ed_ = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed_.get_editor_world().get_path_name().split('.')[0] != '/Game/Maps/Stage1':
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage1')
    assert not dirty(), dirty()
    try:
        seq = u.load_asset(SEQ)
        parts = h.sequence_parts(seq)
        before = h.describe_sequence(seq)
        assert before['end'] == 312 or pc.mode() == 'reapply'
        seq.modify()
        pc.drop(seq, OWNED)
        seq.set_playback_end(END)
        for b in seq.get_bindings():
            for t in b.get_tracks():
                for s in t.get_sections():
                    if s.get_end_frame() == before['end']:
                        s.set_end_frame(END)
        pawn = parts['bindings'][0]
        # pawn: hidden driver. Keep one locomotion section so its saved animation state is restored as before.
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
        rows = path()
        eps = 1. / 800
        ys = [(0, WALK_Y), (CUT - eps, WALK_Y)] + [(f, y) for f, y, _ in rows]
        zs = [(0, 25.2), (CUT - eps, 25.2)] + [(f, z) for f, _, z in rows]
        ch = h.transform_channels(parts['cat'])
        keys(ch[1], ys)
        keys(ch[2], zs)
        h.EASING.set_ease_in_duration(parts['cat'], h.tick(CUT))
        rep['animation'] = add_cat(seq, pawn)
        # cameras
        for cut, span in zip(parts['cuts'], ((0, WALK_START), (WALK_START, CUT), (CUT, PREP), (PREP, END))):
            cut.set_range(*span)
        dz = CFG['head_drop']
        front, eyes = (85., 6., 7. + dz), (8., 0., dz)
        c = CFG['touch_cam']
        p = CFG['prep_cam']
        curves = [
            [h.camera_key(f, l, t) for f, l, t in ((0, (88., 5., 2. + dz), eyes), (WALK_START * .45, (88., 5., 3. + dz), eyes),
                                                   (WALK_START * .76, (88., 9., 13. + dz), (5., 0., dz)), (WALK_START, front, eyes))],
            [h.camera_key(f, l, t) for f, l, t in ((WALK_START, front, eyes), ((WALK_START + CUT) / 2., (80., 5., 6. + dz), eyes),
                                                   (CUT, (64., 3., 4. + dz), eyes))],
            [h.camera_key(f, l, t) for f, l, t in [(f_, tuple(c['eye']), tuple(c['aim'])) for f_ in (CUT, PREP)]],
        ]
        follow = [h.camera_key(f, tuple(p['eye']), tuple(p['aim'])) for f in (PREP, LAST_GROUND + 1)]
        base_y, base_z = STOP_Y, 25.2
        for f in range(LAST_GROUND + 2, AIR_END + 1):
            y, z = nominal(f, rows)
            w = min(1., (f - LAST_GROUND - 1) / 5.)
            w = w * w * (3 - 2 * w)
            up, fw = (z - base_z) * w, min(0., y - base_y) * w
            eye = (p['eye'][0], p['eye'][1] + p['eye_follow_y'] * fw, p['eye'][2] + p['eye_follow_z'] * up)
            aim = (p['aim'][0], p['aim'][1] + p['aim_follow_y'] * fw, p['aim'][2] + p['aim_follow_z'] * up)
            follow.append(h.camera_key(f, eye, aim))
        follow.append((END, *follow[-1][1:]))
        curves.append(follow)
        for i, (sec, comp, curve, fov, focus) in enumerate(zip(
                parts['camera_sections'], parts['camera_components'], curves,
                (old.FOV[0], old.FOV[1], c['fov'], p['fov']), (old.FOCUS[0], old.FOCUS[1], c['focus'], p['focus']))):
            axes(sec, curve)
            comp.modify()
            comp.set_field_of_view(fov)
            st = comp.get_editor_property('post_process_settings').copy()
            for n, v in (('depth_of_field_fstop', 3.5 if i == 0 else 16. if i > 1 else 8.),
                         ('depth_of_field_focal_distance', focus), ('motion_blur_amount', .035 if i > 1 else .06)):
                st.set_editor_property('override_' + n, True)
                st.set_editor_property(n, v)
            comp.set_editor_property('post_process_settings', st)
            if CFG.get('exposure', [None] * 4)[i] is not None:
                pc.lens(comp, exposure=CFG['exposure'][i])
            if CFG.get('near', [None] * 4)[i] is not None:
                pc.lens(comp, near=CFG['near'][i])
        # lights, parented to the portal actor (yaw 180, 1.25 scale)
        L = CFG['light']

        def local(p3):
            return ((101. - p3[0]) / 1.25, (PORTAL_Y - p3[1]) / 1.25, (p3[2] + .8) / 1.25, 0., 0., 0., 1., 1., 1.)
        frames = [0, WALK_START * .6, WALK_START, (WALK_START + CUT) / 2., CUT - 12, CUT - eps, CUT, STOP - SLOW, STOP, PREP - eps, PREP, LAST_GROUND,
                  *range(LAST_GROUND + 4, AIR_END, 4), AIR_END]
        blue, fill = [], []
        for f in frames:
            y, z = nominal(f, rows)
            stage = 'walk' if f < CUT else 'touch' if f < PREP else 'prep'
            for out_, name in ((blue, 'blue'), (fill, 'fill')):
                o = L[name][stage]
                out_.append((f, local((o[0], y + o[1], z + o[2]))))
        axes(parts['light_transform'], blue)
        axes(h.property_section(old.fill_binding(seq), u.MovieScene3DTransformTrack), fill)
        parts['light'].set_range(0, END)
        keys(h.only(parts['light'].get_all_channels()),
             [(0, 300.), (WALK_START, 360.), ((WALK_START + CUT) / 2., L['blue_walk_mid']), (CUT - eps, L['blue_walk_end']),
              (CUT, L['blue_touch']), (PREP - eps, L['blue_touch']), (PREP, L['blue_prep']), (LAST_GROUND, L['blue_prep']),
              (AIR_END, L['blue_end'])], default=300.)
        fs = h.property_section(old.fill_binding(seq), u.MovieSceneFloatTrack)
        fs.set_range(0, END)
        keys(h.only(fs.get_all_channels()),
             [(0, 320.), (WALK_START * .67, 320.), (WALK_START, 245.), (CUT - eps, L['fill_walk_end']), (CUT, L['fill_touch']),
              (PREP - eps, L['fill_touch']), (PREP, L['fill_prep']), (LAST_GROUND, L['fill_prep']), (AIR_END, L['fill_end'])], default=320.)
        parts['fade'].set_range(AIR_END - CFG['fade_lead'], END)
        keys(h.only(parts['fade'].get_all_channels()), [(AIR_END - CFG['fade_lead'], 0.), (END - 1, 1.)])
        k = HAND['contact']['palm_center_model_local_m']
        contact = (101. - SCALE * 100 * k[0], PORTAL_Y + .35, FLOOR_Z + SCALE * 100 * k[2])
        rep['sparks_hidden_in_touch'] = hide_sparks(seq, parts['bindings'][1])
        now = h.describe_sequence(seq)
        assert now['bindings'] == before['bindings'], 'An existing binding GUID changed'
        pc.finish(seq, (), rep)
        rep.update(success=True, timing=dict(walk_start=WALK_START, cut=CUT, stop=STOP, contact=CONTACT, prep=PREP, take=TAKE,
                                             last_ground=LAST_GROUND, air=AIR, air_end=AIR_END, end=END),
                   speed_cm_per_frame=SPEED, stop_y=STOP_Y, walk_target_y=WALK_Y, approach_y=APPROACH_Y,
                   contact_world=contact, floor_z=FLOOR_Z, path=rows, cuts=now['cuts'], sequence_sha256=sha(SEQ_FILE),
                   bindings=now['bindings'])
    except Exception:
        rep['error'] = traceback.format_exc()
        raise
    finally:
        (OUT / ('author_stage1_dry.json' if pc.mode() == 'dry' else 'author_report.json')).write_text(json.dumps(rep, indent=1), encoding='utf-8')
        print('COMPACT_AUTHOR', rep['success'], rep.get('timing'), rep.get('stop_y'), rep.get('walk_target_y'), rep.get('approach_y'))


main()
