"""Edit the existing Stage1 exit sequence and portal material in place.

Set CATRUN_PORTAL_POLISH_MODE to inspect, author, or audit in the editor Python
namespace, or use -catrunPortalPolishInspect/Author/Audit in a commandlet.
Only author mode can save, and it saves only the two named packages.
"""

import datetime
import hashlib
import json
import math
import os
import shutil
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / "Saved/CinematicPolish20261111/Portal" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
BASE = "/Game/Cinematics/Stage1/Portal/"
SEQUENCE = BASE + "LS_Stage1_PortalExit"
MATERIAL = BASE + "M_Stage1PortalBlue"
ORIGINAL = {
    SEQUENCE: "e6c7441c5a8c8c9fb34b088ec82b49037a3c6117e97538a4e2b2e00e30867df0",
    MATERIAL: "e390c6d1f6023df08bfed40671df73ff1f33809d93009fcb46af908bba66d3db",
}
PROTECTED = (
    BASE + "BP_Stage1PortalPresentation", BASE + "BP_Stage1PortalExit",
    BASE + "WBP_ExitTransition", "/Game/Maps/Stage1", "/Game/Maps/SoundTest_Stage1",
)
FPS, TICK_RATE = 30, 24000
TICKS_PER_FRAME = TICK_RATE // FPS
TICKS = u.MovieSceneTimeUnit.TICK_RESOLUTION
WALK_END, INSPECT_END, JUMP_END, FADE_END = 96, 240, 285, 309
JUMP_LIFT, JUMP_CROSS = 261.875, 277.5
RATES = (0.75, 5 / 6, 0.8)
NAMES = ("Front_BackwardTracking", "Face_BlueInspection", "Rear_PortalJump")
FRONT_START, FRONT_END = (58., -206., 61.), (28., -274., 65.)
FACE = (30., -278., 61.)
FOVS = (65., 62., 75.)
AS = u.EditorAssetLibrary
EDIT = u.MaterialEditingLibrary
EASING = u.MovieSceneSectionEasingExtensions

EMISSIVE = """// Stage1 geometric portal
float2 p = (UV - 0.5) * 2.0;
float r = length(p);
float aa = clamp(fwidth(r) * 0.65, 0.002, 0.028);
float a = atan2(p.y, p.x + 0.00001) * 0.159154943;

// Elliptical paired rails follow the stone aperture.
float rail = 1.0 - smoothstep(0.005, 0.005 + aa, abs(r - 0.947));
rail += 0.55 * (1.0 - smoothstep(0.005, 0.005 + aa, abs(r - 0.867)));

// Two counter-rotating groups of arcs, with staggered gaps.
float sectorA = abs(frac(a * 8.0 - T * 0.16) - 0.5);
float sectorB = abs(frac(a * 12.0 + T * 0.17 + 0.33) - 0.5);
float arcs = (1.0 - smoothstep(0.009, 0.009 + aa, abs(r - 0.792)))
           * (1.0 - smoothstep(0.31, 0.41, sectorA));
arcs += 0.72 * (1.0 - smoothstep(0.006, 0.006 + aa, abs(r - 0.721)))
      * (1.0 - smoothstep(0.25, 0.39, sectorB));

// Inner octagon is measured in circular world proportions within the oval.
float2 q = p * float2(1.0, 1.714285714);
float qAngle = atan2(q.y, q.x + 0.00001) * 1.273239545;
float oct = length(q) * cos((frac(qAngle + 0.5) - 0.5) * 0.785398163);
float octAA = clamp(fwidth(oct) * 0.65, 0.002, 0.032);
float octagon = 1.0 - smoothstep(0.005, 0.005 + octAA, abs(oct - 0.585));

// Fixed diamond glyphs read against the moving arcs.
float glyphAngle = abs(frac(a * 8.0 + 0.5) - 0.5);
float glyphDist = abs(r - 0.823) / 0.025 + glyphAngle / 0.1;
float glyph = 1.0 - smoothstep(0.67, 1.16, glyphDist);
float drift = 0.5 + 0.5 * sin(p.x * 7.0 + p.y * 10.0 + T * 0.42);
float3 center = float3(0.007, 0.025, 0.082)
              + float3(0.008, 0.027, 0.078) * drift * saturate(1.0 - r);
return center + rail * float3(0.065, 0.46, 1.65)
              + arcs * float3(0.025, 0.26, 1.0)
              + octagon * float3(0.025, 0.23, 0.84)
              + glyph * float3(0.14, 0.75, 1.9);
"""


def package_file(package):
    suffix = ".umap" if package.startswith("/Game/Maps/") else ".uasset"
    return ROOT / "Content" / (package.removeprefix("/Game/") + suffix)


def hashes():
    return {name: hashlib.sha256(package_file(name).read_bytes()).hexdigest()
            for name in (*ORIGINAL, *PROTECTED)}


def dirty_packages():
    saving = u.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in (
        list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())))


def only(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]


def span(section):
    return section.get_start_frame(), section.get_end_frame()


def section_of(binding, track_type):
    return only(only(binding.find_tracks_by_type(track_type)).get_sections())


def sequence_parts(sequence):
    assert sequence.get_display_rate().numerator == FPS and sequence.get_display_rate().denominator == 1
    assert sequence.get_tick_resolution().numerator == TICK_RATE and sequence.get_tick_resolution().denominator == 1
    assert sequence.get_playback_start() == 0
    bindings = sequence.get_bindings()
    cat = only(b for b in bindings if "CatrunCat" in map(str, b.get_binding_tags()))
    portal = only(b for b in bindings if "CatrunPortal" in map(str, b.get_binding_tags()))
    cameras = [only(b for b in bindings if b.get_name() == name) for name in NAMES]
    portal_id = portal.get_id().export_text()
    light = only(b for b in bindings if b.get_name() == "BlueLight" and b.get_parent().get_id().export_text() == portal_id)
    tracks = sequence.get_tracks()
    cuts = sorted(only(t for t in tracks if isinstance(t, u.MovieSceneCameraCutTrack)).get_sections(), key=span)
    assert len(cuts) == len(cameras)
    for cut, camera in zip(cuts, cameras):
        assert cut.get_camera_binding_id().export_text() == sequence.get_binding_id(camera).export_text()
    animations = sorted(only(cat.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)).get_sections(), key=span)
    assert len(animations) == 4, animations
    return {
        "bindings": [cat, portal, light, *cameras],
        "cat": section_of(cat, u.MovieScene3DTransformTrack),
        "camera_xforms": [section_of(b, u.MovieScene3DTransformTrack) for b in cameras],
        "camera_components": [b.get_object_template().get_editor_property("camera_component") for b in cameras],
        "spawns": [section_of(b, u.MovieSceneSpawnTrack) for b in cameras],
        "cuts": cuts,
        "animations": animations,
        "light": section_of(light, u.MovieSceneFloatTrack),
        "fade": only(only(t for t in tracks if isinstance(t, u.MovieSceneFadeTrack)).get_sections()),
    }


def tick(frame):
    return round(frame * TICKS_PER_FRAME)


def key_tick(key):
    return key.get_time(TICKS).get_editor_property("frame_number").value


def key_values(channel):
    return [(key_tick(key), key.get_value()) for key in channel.get_keys()]


def xform_channels(section):
    channels = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(channels) == 9, len(channels)
    return channels


def look_at(camera, target):
    x, y, z = (b - a for a, b in zip(camera, target))
    return (0., math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x)))


def front_sample(frame):
    alpha = frame / WALK_END
    position = tuple(a + (b - a) * alpha for a, b in zip(FRONT_START, FRONT_END))
    return position + look_at(position, (101., -115. - 127. * alpha, 33.)) + (1., 1., 1.)


FRONT_FRAMES = (0, 24, 48, 72, WALK_END)
FACE_DEFAULTS = FACE + look_at(FACE, (101., -250., 33.)) + (1., 1., 1.)
REAR_DEFAULTS = (101., -5., 105., 0., -1., -90., 1., 1., 1.)


def move_key_times(channel, new_tick):
    for key in sorted(channel.get_keys(), key=key_tick, reverse=True):
        old_tick = key_tick(key)
        target = new_tick(old_tick)
        if target != old_tick:
            key.set_time(u.FrameNumber(target), 0., TICKS)


def retime_cat(old_tick):
    if old_tick <= tick(72):
        return round(old_tick * 4 / 3)
    if old_tick <= tick(192):
        return tick(WALK_END) + round((old_tick - tick(72)) * 6 / 5)
    if old_tick <= tick(228):
        return tick(INSPECT_END) + round((old_tick - tick(192)) * 5 / 4)
    assert old_tick == tick(244), old_tick
    return tick(FADE_END)


def write_camera(section, defaults, samples):
    for index, channel in enumerate(xform_channels(section)):
        for key in channel.get_keys():
            channel.remove_key(key)
        channel.set_default(defaults[index])
        if samples and any(values[index] != defaults[index] for _, values in samples):
            for frame, values in samples:
                channel.add_key(u.FrameNumber(tick(frame)), values[index], 0., TICKS,
                                u.MovieSceneKeyInterpolation.LINEAR)


def patch_sequence(sequence, parts):
    sequence.modify()
    sequence.set_playback_end(FADE_END)
    for section in (parts["cat"], parts["light"], *parts["camera_xforms"], *parts["spawns"]):
        section.set_range(0, FADE_END)
    for channel in xform_channels(parts["cat"]):
        move_key_times(channel, retime_cat)
    EASING.set_ease_in_duration(parts["cat"], tick(32))
    for section, start, end in zip(parts["cuts"], (0, WALK_END, INSPECT_END), (WALK_END, INSPECT_END, FADE_END)):
        section.set_range(start, end)
    bounds = (0, WALK_END, INSPECT_END, JUMP_END, FADE_END)
    for index, section in enumerate(parts["animations"]):
        if index < len(RATES):
            params = section.get_editor_property("params")
            params.set_editor_property("play_rate", u.MovieSceneTimeWarpExtensions.make_time_warp(RATES[index]))
            section.set_editor_property("params", params)
        # Sequencer changes the duration when PlayRate is edited.
        section.set_range(bounds[index], bounds[index + 1])
    write_camera(parts["camera_xforms"][0], front_sample(0), [(f, front_sample(f)) for f in FRONT_FRAMES])
    write_camera(parts["camera_xforms"][1], FACE_DEFAULTS, [])
    for component, fov in zip(parts["camera_components"][:2], FOVS):
        component.modify()
        component.set_field_of_view(fov)
    new_light_frames = dict(zip(map(tick, (0, 45, 72, 102, 244)), map(tick, (0, 60, WALK_END, 132, FADE_END))))
    move_key_times(only(parts["light"].get_all_channels()), new_light_frames.__getitem__)
    parts["fade"].set_range(JUMP_END, FADE_END)
    new_fade_frames = {tick(228): tick(JUMP_END), tick(243): tick(FADE_END - 1)}
    move_key_times(only(parts["fade"].get_all_channels()), new_fade_frames.__getitem__)


def material_nodes(material):
    assert material.get_editor_property("two_sided")
    assert material.get_editor_property("blend_mode") == u.BlendMode.BLEND_MASKED
    color = EDIT.get_material_property_input_node(material, u.MaterialProperty.MP_EMISSIVE_COLOR)
    mask = EDIT.get_material_property_input_node(material, u.MaterialProperty.MP_OPACITY_MASK)
    assert isinstance(color, u.MaterialExpressionCustom) and isinstance(mask, u.MaterialExpressionCustom)
    for node, expected in ((color, ["UV", "T"]), (mask, ["UV"])):
        names = [str(item.get_editor_property("input_name")) for item in node.get_editor_property("inputs")]
        assert names == expected, names
    assert mask.get_editor_property("code") == "float2 p=(UV-.5)*2; return 1-dot(p,p);"
    return color, mask


def describe(sequence, parts, color):
    cameras = []
    for name, section, component in zip(NAMES, parts["camera_xforms"], parts["camera_components"]):
        channels = xform_channels(section)
        cameras.append({"name": name, "fov": component.get_editor_property("field_of_view"),
                        "defaults": [ch.get_default() for ch in channels], "keys": [key_values(ch) for ch in channels]})
    animations = []
    for section in parts["animations"]:
        params = section.get_editor_property("params")
        animations.append({
            "range": span(section), "asset": params.get_editor_property("animation").get_name(),
            "time_warp": params.get_editor_property("play_rate").export_text(),
            "hold_offset": params.get_editor_property("first_loop_start_frame_offset").value,
            "force_custom_mode": params.get_editor_property("force_custom_mode"),
            "skip_anim_notifiers": params.get_editor_property("skip_anim_notifiers"),
        })
    return {
        "binding_ids": {b.get_name(): b.get_id().export_text() for b in parts["bindings"]},
        "end": sequence.get_playback_end(), "cuts": [span(s) for s in parts["cuts"]],
        "section_ranges": [span(s) for s in (parts["cat"], parts["light"], *parts["camera_xforms"], *parts["spawns"])],
        "fade_range": span(parts["fade"]), "fade_keys": key_values(only(parts["fade"].get_all_channels())),
        "cat_ease_ticks": EASING.get_ease_in_duration(parts["cat"]),
        "cat_defaults": [c.get_default() for c in xform_channels(parts["cat"])],
        "cat_keys": [key_values(c) for c in xform_channels(parts["cat"])],
        "blue_light_keys": key_values(only(parts["light"].get_all_channels())),
        "cameras": cameras, "animations": animations,
        "geometric_material": color.get_editor_property("code").strip() == EMISSIVE.strip(),
    }


def verify_sequence(state):
    assert state["end"] == FADE_END
    assert all(bounds == (0, FADE_END) for bounds in state["section_ranges"])
    assert state["cuts"] == [(0, WALK_END), (WALK_END, INSPECT_END), (INSPECT_END, FADE_END)]
    assert state["fade_range"] == (JUMP_END, FADE_END)
    assert state["fade_keys"] == [(tick(JUMP_END), 0.), (tick(FADE_END - 1), 1.)]
    assert state["cat_ease_ticks"] == tick(32)
    expected_y = [(0, -115.), (WALK_END, -242.), (119.04, -250.), (JUMP_LIFT, -250.),
                  (JUMP_END, -315.), (FADE_END, -315.)]
    assert state["cat_keys"][1] == [(tick(frame), y) for frame, y in expected_y], state["cat_keys"][1]
    (lift_time, lift_y), (land_time, land_y) = state["cat_keys"][1][3:5]
    cross_y = lift_y + (land_y - lift_y) * (tick(JUMP_CROSS) - lift_time) / (land_time - lift_time)
    assert math.isclose(cross_y, -293.9189189189189, abs_tol=1e-6)
    assert len(state["cat_keys"][2]) == 27
    for (time, height), frame in zip(state["cat_keys"][2][-2:], (JUMP_END, FADE_END)):
        assert time == tick(frame) and math.isclose(height, 39.2, abs_tol=1e-5)
    assert state["blue_light_keys"] == list(zip(map(tick, (0, 60, WALK_END, 132, FADE_END)), (0., 0., 650., 1200., 1200.)))
    assert [row["fov"] for row in state["cameras"]] == list(FOVS)
    for row, defaults in zip(state["cameras"], (front_sample(0), FACE_DEFAULTS, REAR_DEFAULTS)):
        assert all(math.isclose(value, expected, abs_tol=1e-5)
                   for value, expected in zip(row["defaults"], defaults)), row
    for index, keys in enumerate(state["cameras"][0]["keys"]):
        expected = [(tick(frame), front_sample(frame)[index]) for frame in FRONT_FRAMES]
        if all(value == expected[0][1] for _, value in expected):
            expected = []
        assert len(keys) == len(expected) and all(
            time == expected_time and math.isclose(value, expected_value, abs_tol=1e-5)
            for (time, value), (expected_time, expected_value) in zip(keys, expected)), keys
    assert all(not any(row["keys"]) for row in state["cameras"][1:])
    clips = ("Walk", "PortalInspect", "PortalJumpIn", "PortalJumpIn")
    bounds = (0, WALK_END, INSPECT_END, JUMP_END, FADE_END)
    for i, row in enumerate(state["animations"]):
        warp = u.MovieSceneTimeWarpExtensions.make_time_warp((*RATES, 0.)[i]).export_text()
        assert row == {
            "range": (bounds[i], bounds[i + 1]), "asset": "AN_BlackCat_" + clips[i], "time_warp": warp,
            "hold_offset": 28799 if i == 3 else 0, "force_custom_mode": True, "skip_anim_notifiers": True,
        }, row


def run(mode):
    report = {"mode": mode, "process_id": os.getpid(), "completed": False, "saved": [], "backups": []}
    OUT.mkdir(parents=True, exist_ok=False)

    def persist():
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    try:
        assert mode in ("inspect", "author", "audit"), mode
        report["dirty_before"] = dirty_packages()
        before_hashes = report["before_hashes"] = hashes()
        sequence, material = (AS.load_asset(package) for package in ORIGINAL)
        parts = sequence_parts(sequence)
        color, mask = material_nodes(material)
        before = report["before"] = describe(sequence, parts, color)
        persist()
        if mode == "author":
            assert not report["dirty_before"] and not dirty_packages(), "Start author mode with a clean editor"
            assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(), "Stop PIE before authoring"
            rewrite_sequence = before_hashes[SEQUENCE] == ORIGINAL[SEQUENCE]
            rewrite_material = before_hashes[MATERIAL] == ORIGINAL[MATERIAL]
            if not rewrite_sequence:
                verify_sequence(before)
            if not rewrite_material:
                assert before["geometric_material"], "Unrecognized portal material revision"
            pending = [name for name, rewrite in ((SEQUENCE, rewrite_sequence), (MATERIAL, rewrite_material)) if rewrite]
            for name in pending:
                source = package_file(name)
                backup = OUT / "Before" / source.relative_to(ROOT)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, backup)
                assert hashlib.sha256(backup.read_bytes()).hexdigest() == before_hashes[name]
                report["backups"].append(str(backup))
            persist()
            if rewrite_sequence:
                patch_sequence(sequence, parts)
            if rewrite_material:
                material.modify()
                color.modify()
                color.set_editor_property("code", EMISSIVE)
                EDIT.recompile_material(material)

        after = report["after"] = describe(sequence, sequence_parts(sequence), color)
        assert after["binding_ids"] == before["binding_ids"] and material_nodes(material)[1] == mask
        if mode in ("author", "audit"):
            verify_sequence(after)
            assert after["geometric_material"]
        if mode == "author":
            if rewrite_sequence:
                expected = [[(retime_cat(time), value) for time, value in keys] for keys in before["cat_keys"]]
                assert after["cat_keys"] == expected and after["cat_defaults"] == before["cat_defaults"]
            assert not (set(dirty_packages()) - set(pending)), dirty_packages()
            for name in pending:
                assert AS.save_asset(name, only_if_is_dirty=False), name
                report["saved"].append(name)
                persist()
        after_hashes = report["after_hashes"] = hashes()
        report["dirty_after"] = dirty_packages()
        allowed = report["saved"]
        assert all(before_hashes[name] == after_hashes[name] for name in before_hashes if name not in allowed)
        assert all(before_hashes[name] != after_hashes[name] for name in allowed)
        assert report["dirty_after"] == report["dirty_before"], report["dirty_after"]
        report["completed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
        report["dirty_after"] = dirty_packages()
        raise
    finally:
        persist()
        print("CATRUN_PORTAL_POLISH", mode, report["completed"], str(OUT / "report.json"))


command = u.SystemLibrary.get_command_line().lower()
selected_modes = [mode for mode in ("inspect", "author", "audit") if "-catrunportalpolish" + mode in command]
run(globals().get("CATRUN_PORTAL_POLISH_MODE") or (only(selected_modes) if selected_modes else "inspect"))
