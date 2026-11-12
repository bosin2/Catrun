"""Inspect, author, and cold-audit the Stage1 portal sequence and settings paw.

Run in fresh Unreal Python commandlets with -catrunPortalPawProbe, Author,
or Audit appended to the same flag prefix. Author and Audit require a
completed previous report via -catrunPortalPawBaseline=".../report.json".
Only Author saves packages. No sequence playback or PIE is used.
"""

import datetime
import hashlib
import json
import math
import os
import re
import shutil
import sys
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "Scripts/Menu"))
from menu_graph import compile_bp, widgets

BASE = "/Game/Cinematics/Stage1/Portal/"
SEQUENCE = BASE + "LS_Stage1_PortalExit"
PORTAL_MATERIAL = BASE + "M_Stage1PortalBlue"
SETTINGS = "/Game/UI/Settings/WBP_Setting"
PAW_MATERIAL = "/Game/UI/Settings/M_UI_SettingsPawMetal"
PAW_TEXTURE = "/Game/Environment/UI/CatJelly"
MAPS = ("/Game/Maps/Stage1", "/Game/Maps/SoundTest_Stage1")
OWNED = (SEQUENCE, PORTAL_MATERIAL, PAW_MATERIAL, SETTINGS)
CLIP_DIR = "/Game/Characters/BlackCat/Final/Animations/"
CLIPS = tuple(CLIP_DIR + name for name in (
    "AN_BlackCat_Walk", "Cinematics/AN_BlackCat_PortalInspect", "Cinematics/AN_BlackCat_PortalJumpIn",
))
PROTECTED = (*MAPS, *CLIPS, PAW_TEXTURE, BASE + "BP_Stage1PortalPresentation",
             BASE + "BP_Stage1PortalExit", BASE + "WBP_ExitTransition", "/Game/UI/WBP_MainMenu")
ISOLATED_CVARS = ("Editor.AsyncStaticMeshCompilation", "Editor.AsyncSkinnedAssetCompilation",
                  "p.EnableDeferredPhysicsCreation", "p.Chaos.EnableAsyncInitBody")
CAMERAS = ("Front_BackwardTracking", "Face_BlueInspection", "Rear_PortalJump")
FOVS = (80., 55., 74.)
FPS, TICK_RATE, TICKS_PER_FRAME = 30, 24000, 800
WALK_END, FACE_END, CROUCH_START, LIFT, AIR_END, END = 96, 168, 216, 238, 284, 308
GROUNDED_Z, INSPECT_Y, ENTRY_Y, ENTRY_Z = 25.2, -250., -315., 39.2
PORTAL_Y = -293.9189189189189
EASE_FRAMES = 32
TAKEOFF_SOURCE_FRAME = 17.5  # Last hind-paw support, zero-based on the source clip.
TICKS = u.MovieSceneTimeUnit.TICK_RESOLUTION
LINEAR = u.MovieSceneKeyInterpolation.LINEAR
AS = u.EditorAssetLibrary
EDIT = u.MaterialEditingLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
EASING = u.MovieSceneSectionEasingExtensions
NONE = u.DrawDebugTrace.NONE
VISIBILITY = u.TraceTypeQuery.TRACE_TYPE_QUERY1


def only(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]


def load_asset(package):
    asset = AS.load_asset(package)
    assert asset, package
    return asset


def tick(frame):
    return round(frame * TICKS_PER_FRAME)


def span(section):
    return section.get_start_frame(), section.get_end_frame()


def key_data(channel):
    return [(key.get_time(TICKS).frame_number.value, key.get_value()) for key in channel.get_keys()]


def property_track(binding, track_type):
    return only(binding.find_tracks_by_type(track_type))


def property_section(binding, track_type):
    return only(property_track(binding, track_type).get_sections())


def sequence_parts(sequence):
    display, resolution = sequence.get_display_rate(), sequence.get_tick_resolution()
    assert (display.numerator, display.denominator, resolution.numerator, resolution.denominator) == (30, 1, 24000, 1)
    assert sequence.get_playback_start() == 0
    bindings = sequence.get_bindings()
    cat = only(b for b in bindings if "CatrunCat" in map(str, b.get_binding_tags()))
    portal = only(b for b in bindings if "CatrunPortal" in map(str, b.get_binding_tags()))
    cameras = [only(b for b in bindings if b.get_name() == name) for name in CAMERAS]
    portal_id = portal.get_id().export_text()
    light = only(b for b in bindings if b.get_name() == "BlueLight" and b.get_parent().get_id().export_text() == portal_id)
    cuts = sorted(only(t for t in sequence.get_tracks() if isinstance(t, u.MovieSceneCameraCutTrack)).get_sections(), key=span)
    light_transforms = light.find_tracks_by_type(u.MovieScene3DTransformTrack)
    assert len(light_transforms) <= 1
    assert len(cuts) == len(cameras)
    for cut, camera in zip(cuts, cameras):
        assert cut.get_camera_binding_id().export_text() == sequence.get_binding_id(camera).export_text()
    return {
        "bindings": [cat, portal, light, *cameras], "cuts": cuts, "light_binding": light,
        "cat": property_section(cat, u.MovieScene3DTransformTrack),
        "camera_sections": [property_section(b, u.MovieScene3DTransformTrack) for b in cameras],
        "camera_components": [b.get_object_template().get_editor_property("camera_component") for b in cameras],
        "spawns": [property_section(b, u.MovieSceneSpawnTrack) for b in cameras],
        "anim_track": property_track(cat, u.MovieSceneSkeletalAnimationTrack),
        "light": property_section(light, u.MovieSceneFloatTrack),
        "light_transform": only(light_transforms[0].get_sections()) if light_transforms else None,
        "fade": only(only(t for t in sequence.get_tracks() if isinstance(t, u.MovieSceneFadeTrack)).get_sections()),
    }


def transform_channels(section):
    channels = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(channels) == 9, len(channels)
    return channels


def describe_sequence(sequence):
    parts = sequence_parts(sequence)
    animations = []
    for section in sorted(parts["anim_track"].get_sections(), key=span):
        params = section.get_editor_property("params")
        animations.append({
            "range": span(section), "clip": params.get_editor_property("animation").get_path_name(),
            "play_rate": params.get_editor_property("play_rate").export_text(),
            "start_offset": params.get_editor_property("start_frame_offset").value,
            "first_loop_offset": params.get_editor_property("first_loop_start_frame_offset").value,
            "custom_mode": params.get_editor_property("force_custom_mode"),
            "skip_notifiers": params.get_editor_property("skip_anim_notifiers"),
        })

    def transform(section):
        channels = transform_channels(section)
        return {"range": span(section), "defaults": [c.get_default() for c in channels],
                "keys": [key_data(c) for c in channels]}

    return {
        "end": sequence.get_playback_end(), "cuts": [span(cut) for cut in parts["cuts"]],
        "bindings": {b.get_name(): b.get_id().export_text() for b in parts["bindings"]},
        "spawn_ranges": [span(s) for s in parts["spawns"]],
        "cameras": [dict(transform(s), fov=c.get_editor_property("field_of_view"))
                    for s, c in zip(parts["camera_sections"], parts["camera_components"])],
        "cat": dict(transform(parts["cat"]), ease_ticks=EASING.get_ease_in_duration(parts["cat"])),
        "light": {"range": span(parts["light"]), "keys": key_data(only(parts["light"].get_all_channels()))},
        "light_transform": transform(parts["light_transform"]) if parts["light_transform"] else None,
        "fade": {"range": span(parts["fade"]), "keys": key_data(only(parts["fade"].get_all_channels()))},
        "animations": animations,
    }


def lerp(first, last, fraction):
    return first + (last - first) * fraction


def flight_z(fraction):
    return lerp(GROUNDED_Z, ENTRY_Z, fraction) + 54. * math.sin(math.pi * fraction) ** 1.15


def cat_curve():
    # Translation stays with the Sequencer binding. Clips remain in-place.
    approach = [(0., -115.), (WALK_END, -242.)]
    for index in range(1, 13):
        fraction = index / 12.
        distance = 16. * (fraction - fraction**3 + .5 * fraction**4)
        approach.append((WALK_END + 19.2 * fraction, -242. - distance))
    y_keys = [*approach, (LIFT, INSPECT_Y), (AIR_END, ENTRY_Y), (END, ENTRY_Y)]
    z_keys = [(0., GROUNDED_Z), (LIFT, GROUNDED_Z)]
    z_keys.extend((frame, flight_z((frame - LIFT) / (AIR_END - LIFT)))
                  for frame in range(LIFT + 1, AIR_END + 1))
    z_keys.append((END, ENTRY_Z))
    return y_keys, z_keys


def interpolate(keys, frame):
    for (first, start), (last, end) in zip(keys, keys[1:]):
        if frame <= last:
            return lerp(start, end, (frame - first) / (last - first))
    return keys[-1][1]


def cat_point(frame, arrival=(101., -115., GROUNDED_Z)):
    y_keys, z_keys = CAT_CURVE
    target = (101., interpolate(y_keys, frame), interpolate(z_keys, frame))
    fraction = min(frame / EASE_FRAMES, 1.)
    # The saved section uses cubic in/out easing to blend from captured arrival.
    weight = 4. * fraction**3 if fraction < .5 else 1. - (-2. * fraction + 2.)**3 / 2.
    return tuple(lerp(start, end, weight) for start, end in zip(arrival, target))


def look_at(position, target):
    x, y, z = (end - start for start, end in zip(position, target))
    return 0., math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def camera_key(frame, position, target):
    return frame, position + look_at(position, target) + (1., 1., 1.)


def camera_curves():
    front = []
    for frame in (0, 24, 48, 72, WALK_END):
        fraction = frame / WALK_END
        position = (lerp(73., 55., fraction), lerp(-215., -282., fraction), lerp(72., 66., fraction))
        # Keep the approaching cat full length with the corridor opening behind it.
        target = (103., lerp(-108., -231., fraction), 41.)
        front.append(camera_key(frame, position, target))
    face = [camera_key(WALK_END, (54., -279., 54.), (101., -260., 43.)),
            camera_key(124, (56., -282., 53.), (101., -263., 44.)),
            camera_key(FACE_END, (60., -285., 52.), (101., -264., 45.))]
    rear = [camera_key(frame, position, (101., PORTAL_Y, aim_z))
            for frame, position, aim_z in (
                (FACE_END, (101., -15., 89.), 92.),
                (CROUCH_START, (101., -33., 85.), 90.),
                (LIFT, (101., -40., 84.), 90.),
                (AIR_END, (101., -54., 87.), 95.),
                (END, (101., -54., 87.), 95.),
            )]
    return front, face, rear


CAT_CURVE = cat_curve()
CAMERA_CURVES = camera_curves()
CUTS = ((0, WALK_END), (WALK_END, FACE_END), (FACE_END, END))
LIGHT_KEYS = ((0, 180.), (30, 330.), (63, 720.), (WALK_END, 1500.),
              (132, 2250.), (CROUCH_START, 2050.), (LIFT, 2200.), (AIR_END, 2300.), (END, 2300.))
LIGHT_DEFAULTS = (0., -40., 65., 0., 0., 0., 1., 1., 1.)
# Relative to the yaw-180 portal actor, this moves the light toward the cat's face.
LIGHT_POSITION = ((), ((0, -40.), (48, -30.), (WALK_END, -15.), (END, -15.)),
                  ((0, 65.), (48, 62.), (WALK_END, 54.), (END, 54.)), (), (), (), (), (), ())
FADE_KEYS = ((AIR_END, 0.), (END - 1, 1.))
ANIMATIONS = (
    (0, WALK_END, CLIPS[0], .75, 0, 0),
    (WALK_END, CROUCH_START, CLIPS[1], 1., 0, 0),
    (CROUCH_START, LIFT, CLIPS[2], TAKEOFF_SOURCE_FRAME / (LIFT - CROUCH_START), 0, 0),
    (LIFT, AIR_END, CLIPS[2], (36. - TAKEOFF_SOURCE_FRAME) / (AIR_END - LIFT), tick(TAKEOFF_SOURCE_FRAME), 0),
    (AIR_END, END, CLIPS[2], 0., 0, tick(36.) - 1),
)


def camera_values(curve, frame):
    return tuple(interpolate([(time, values[i]) for time, values in curve], frame) for i in range(9))


def write_keys(channel, keys, default=None):
    for key in channel.get_keys():
        channel.remove_key(key)
    if default is not None:
        channel.set_default(default)
    for frame, value in keys:
        channel.add_key(u.FrameNumber(tick(frame)), value, 0., TICKS, LINEAR)


def patch_sequence(sequence):
    parts = sequence_parts(sequence)
    sequence.modify()
    sequence.set_playback_end(END)
    for section in (parts["cat"], parts["light"], *parts["camera_sections"], *parts["spawns"]):
        section.set_range(0, END)
    for section, (first, last) in zip(parts["cuts"], CUTS):
        section.set_range(first, last)
    for channel, keys in zip(transform_channels(parts["cat"])[1:3], CAT_CURVE):
        write_keys(channel, keys)
    EASING.set_ease_in_duration(parts["cat"], tick(EASE_FRAMES))
    for section, component, curve, fov in zip(parts["camera_sections"], parts["camera_components"], CAMERA_CURVES, FOVS):
        for index, channel in enumerate(transform_channels(section)):
            keys = [(frame, values[index]) for frame, values in curve]
            default = keys[0][1]
            write_keys(channel, keys if any(value != default for _, value in keys) else (), default)
        component.modify()
        component.set_field_of_view(fov)
    track = parts["anim_track"]
    existing = sorted(track.get_sections(), key=span)
    assert len(existing) == 4
    sections = existing[:3] + [track.add_section()] + existing[3:]
    for section, (first, last, clip, rate, start, hold) in zip(sections, ANIMATIONS):
        params = section.get_editor_property("params")
        params.set_editor_property("animation", load_asset(clip))
        params.set_editor_property("force_custom_mode", True)
        params.set_editor_property("skip_anim_notifiers", True)
        params.set_editor_property("play_rate", u.MovieSceneTimeWarpExtensions.make_time_warp(rate))
        params.set_editor_property("start_frame_offset", u.FrameNumber(start))
        params.set_editor_property("first_loop_start_frame_offset", u.FrameNumber(hold))
        section.set_editor_property("params", params)
        section.set_range(first, last)
        section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    write_keys(only(parts["light"].get_all_channels()), LIGHT_KEYS)
    assert parts["light_transform"] is None
    light_transform = parts["light_binding"].add_track(u.MovieScene3DTransformTrack).add_section()
    light_transform.set_range(0, END)
    light_transform.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    for channel, keys, default in zip(transform_channels(light_transform), LIGHT_POSITION, LIGHT_DEFAULTS):
        write_keys(channel, keys, default)
    parts["fade"].set_range(AIR_END, END)
    write_keys(only(parts["fade"].get_all_channels()), FADE_KEYS)


def verify_sequence(state):
    assert state["end"] == END and tuple(state["cuts"]) == CUTS
    assert all(bounds == (0, END) for bounds in state["spawn_ranges"])
    assert state["cat"]["range"] == (0, END) and state["cat"]["ease_ticks"] == tick(EASE_FRAMES)
    assert state["light"]["range"] == (0, END) and state["fade"]["range"] == (AIR_END, END)
    assert state["cat"]["defaults"] == [101., -115., 25.2, 0., 0., -90., 1., 1., 1.]

    def verify_keys(actual, expected):
        assert len(actual) == len(expected), (actual, expected)
        assert all(time == tick(frame) and math.isclose(value, wanted, abs_tol=1.e-5)
                   for (time, value), (frame, wanted) in zip(actual, expected)), (actual, expected)

    for channel, keys in zip(state["cat"]["keys"], ((), *CAT_CURVE, (), (), (), (), (), ())):
        verify_keys(channel, keys)
    for camera, curve, fov in zip(state["cameras"], CAMERA_CURVES, FOVS):
        assert camera["range"] == (0, END) and camera["fov"] == fov
        for index, channel in enumerate(camera["keys"]):
            keys = [(frame, values[index]) for frame, values in curve]
            default = keys[0][1]
            assert math.isclose(camera["defaults"][index], default, abs_tol=1.e-5)
            verify_keys(channel, keys if any(value != default for _, value in keys) else ())
    verify_keys(state["light"]["keys"], LIGHT_KEYS)
    assert state["light_transform"]["range"] == (0, END)
    assert state["light_transform"]["defaults"] == list(LIGHT_DEFAULTS)
    for channel, keys in zip(state["light_transform"]["keys"], LIGHT_POSITION):
        verify_keys(channel, keys)
    verify_keys(state["fade"]["keys"], FADE_KEYS)
    assert len(state["animations"]) == len(ANIMATIONS)
    for row, (first, last, clip, rate, start, hold) in zip(state["animations"], ANIMATIONS):
        assert row == {"range": (first, last), "clip": clip + "." + clip.rsplit("/", 1)[1],
                       "play_rate": u.MovieSceneTimeWarpExtensions.make_time_warp(rate).export_text(),
                       "start_offset": start, "first_loop_offset": hold,
                       "custom_mode": True, "skip_notifiers": True}, row


def dirty():
    saving = u.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in (*saving.get_dirty_map_packages(), *saving.get_dirty_content_packages()))


def asset_file(package):
    return ROOT / "Content" / (package.removeprefix("/Game/") + (".umap" if package in MAPS else ".uasset"))


def digest(path):
    if not path.is_file():
        return None
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def hashes():
    return {package: digest(asset_file(package)) for package in (*OWNED, *PROTECTED)}


def tuple3(vector):
    return vector.x, vector.y, vector.z


def verify_map(package):
    assert not dirty() and LEVEL.load_level(package), (package, dirty())
    world = ED.get_editor_world()
    assert world.get_path_name().split(".")[0] == package and not ED.get_game_world()
    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
    cat = only(a for a in actors if isinstance(a, u.Character) and a.get_name() == "BP_Cat_C_0")
    director = only(a for a in actors if "CatrunAuthoredStage1Exit" in map(str, a.tags))
    portal = only(a for a in actors if "CatrunAuthoredStage1Portal" in map(str, a.tags))
    assert director.get_editor_property("PortalPresentation") == portal
    assert math.dist(tuple3(portal.get_actor_location()), (101., PORTAL_Y, -.8)) < .01
    assert director.get_editor_property("CinematicTimeout") > END / FPS
    assert director.get_editor_property("CinematicActor").get_editor_property("level_sequence_asset") == load_asset(SEQUENCE)
    capsule = cat.get_component_by_class(u.CapsuleComponent)
    movement = cat.get_component_by_class(u.CharacterMovementComponent)
    tolerance = director.get_component_by_class(u.CatrunExitTransitionComponent).get_editor_property("GroundTolerance")
    radius, half = capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height()
    assert str(capsule.get_collision_profile_name()) == "Pawn" and math.isclose(radius, 20.) and math.isclose(half, 24.)
    assert capsule.get_collision_object_type() == u.CollisionChannel.ECC_PAWN
    for channel in ("WORLD_STATIC", "WORLD_DYNAMIC", "PAWN", "PHYSICS_BODY", "VEHICLE", "DESTRUCTIBLE"):
        assert capsule.get_collision_response_to_channel(getattr(u.CollisionChannel, "ECC_" + channel)) == u.CollisionResponseType.ECR_BLOCK
    assert abs(capsule.get_up_vector().z) >= .99
    step = movement.get_editor_property("max_step_height")
    walkable = max(.65, movement.get_walkable_floor_z())
    ignore = [cat, director]
    counters = {"capsule_sweeps": 0, "ground_queries": 0, "camera_sweeps": 0, "camera_sightlines": 0}

    def capsule_trace(start, end, counter):
        counters[counter] += 1
        return u.SystemLibrary.capsule_trace_single_by_profile(world, start, end, radius, half, "Pawn", False, ignore, NONE, False)

    def support(point, frame, require_height):
        above = point + u.Vector(0, 0, step)
        below = point - u.Vector(0, 0, step + tolerance)
        hit = capsule_trace(above, below, "ground_queries")
        assert hit, (package, frame, "No capsule floor support", tuple3(point))
        data = hit.to_dict()
        assert data["blocking_hit"] and not data["initial_overlap"] and data["impact_normal"].z >= walkable, (package, frame, data)
        assert not isinstance(data["hit_actor"], u.Pawn)
        center, contact = data["location"], data["impact_point"]
        assert math.hypot(contact.x - center.x, contact.y - center.y) <= radius - .15
        assert below.z - .01 <= center.z <= above.z + .01
        if require_height:
            assert abs(center.z + 2. - point.z) <= tolerance, (package, frame, tuple3(point), tuple3(center))
        return center.z + 2.

    def audit_path(arrival, frames):
        previous = None
        for frame in frames:
            point = u.Vector(*cat_point(frame, arrival))
            if point.z - arrival[2] <= 2.:
                support(point, frame, True)
            # A tiny first segment checks initial penetration as well as the moving sweeps.
            start = previous if previous is not None and (previous - point).length() > .001 else point + u.Vector(0, 0, .01)
            hit = capsule_trace(start, point, "capsule_sweeps")
            assert not hit, (package, frame, tuple3(start), tuple3(point), hit.to_dict())
            previous = point

    for x in (71., 101., 131.):
        for y in (-115., -80.):
            audit_path((x, y, GROUNDED_Z), (frame / 2. for frame in range(2 * EASE_FRAMES + 1)))
    audit_path((101., -115., GROUNDED_Z), (frame / 2. for frame in range(2 * EASE_FRAMES, 2 * END + 1)))
    endpoint_support = support(u.Vector(*cat_point(END)), END, False)

    camera_ignore = [cat, director, portal]
    for index, ((first, last), curve) in enumerate(zip(CUTS, CAMERA_CURVES)):
        previous = None
        for sample in range(first * 2, last * 2 + 1):
            frame = sample / 2.
            position = u.Vector(*camera_values(curve, frame)[:3])
            start = previous if previous is not None and (previous - position).length() > .001 else position + u.Vector(0, 0, .01)
            counters["camera_sweeps"] += 1
            hit = u.SystemLibrary.sphere_trace_single(world, start, position, 2., VISIBILITY, False, camera_ignore, NONE, False)
            assert not hit, (package, CAMERAS[index], frame, "Camera collision", hit.to_dict())
            previous = position
            if sample % 12 == 0 or frame in (first, last):
                x, y, z = cat_point(frame)
                targets = [(x, y - (12. if index < 2 else 0.), z + 15.)]
                if index == 2:
                    targets.append((101., PORTAL_Y, 90.))
                for target in targets:
                    counters["camera_sightlines"] += 1
                    hit = u.SystemLibrary.line_trace_single(world, position, u.Vector(*target), VISIBILITY, False, camera_ignore, NONE, False)
                    assert not hit, (package, CAMERAS[index], frame, "Obstructed framing", target, hit.to_dict())
    assert not dirty(), (package, dirty())
    cross_frame = LIFT + (AIR_END - LIFT) * (PORTAL_Y - INSPECT_Y) / (ENTRY_Y - INSPECT_Y)
    apex = max(cat_point(sample / 2.)[2] for sample in range(LIFT * 2, AIR_END * 2 + 1))
    assert 85. <= apex <= 100.
    return dict(counters, apex_z=apex, crossing_frame=cross_frame, crossing_position=cat_point(cross_frame),
                endpoint_position=cat_point(END), endpoint_support_z=endpoint_support,
                capsule_radius=radius, capsule_half_height=half)


RIM = """float2 p = (UV - 0.5) * 2.0;
float radius = length(p);
float angle = atan2(p.y, p.x + 0.000001);
float ripple = 0.015 * sin(7.0 * angle - 0.75 * T)
             + 0.007 * sin(17.0 * angle + 0.92 * T)
             + 0.004 * sin(29.0 * angle - 0.68 * T);
float edge = radius - (0.909 + ripple);
float aa = clamp(fwidth(radius) * 0.75, 0.002, 0.022);
float rim = 1.0 - smoothstep(0.007, 0.022 + aa, abs(edge));
float corona = exp(-27.0 * abs(edge));
"""

PORTAL_COLOR = RIM + """// Wind the luminous threads inward through a dark, violet-blue well.
float wind = angle + 1.94 * log(max(radius, 0.025)) - 0.36 * T;
float shear = 0.20 * sin(3.0 * angle + 8.0 * radius + 0.48 * T);
float stream = pow(0.5 + 0.5 * cos(3.0 * wind + shear), 3.0);
float threads = pow(0.5 + 0.5 * sin(12.0 * wind + 11.0 * radius + shear), 10.0);
float mist = smoothstep(0.06, 0.27, radius) * (1.0 - smoothstep(0.71, 0.94, radius));
float purple = 0.5 + 0.5 * sin(2.0 * wind + 0.6);
float3 filament = lerp(float3(0.018, 0.24, 0.88), float3(0.39, 0.055, 0.79), purple);
float3 rimColor = lerp(float3(0.13, 1.12, 2.85), float3(0.51, 0.54, 2.10),
                       0.5 + 0.5 * cos(2.0 * angle + 0.32 * T));
float spark = pow(saturate(0.5 + 0.5 * sin(19.0 * angle - 2.1 * T + 4.0 * shear)), 5.0);
float3 well = float3(0.006, 0.008, 0.026) + filament * mist * (0.43 * stream + 0.22 * threads);
return well + rimColor * (0.20 * corona + rim * (0.85 + 0.42 * spark));
"""

PORTAL_OPACITY = RIM + """float outerFade = 1.0 - smoothstep(0.015, 0.052 + aa, edge);
float swirl = 0.5 + 0.5 * cos(3.0 * (angle + 1.94 * log(max(radius, 0.025)) - 0.36 * T));
float body = 0.74 - 0.21 * smoothstep(0.06, 0.66, radius) + 0.09 * swirl;
return outerFade * saturate(body + 0.16 * corona + 0.20 * rim);
"""

PAW_COLOR = """// Use the source silhouette for a warm bevel and a polished reflection.
float2 across = float2(0.018, -0.022);
float upper = Texture2DSample(Paw, PawSampler, saturate(UV + across)).a;
float lower = Texture2DSample(Paw, PawSampler, saturate(UV - across)).a;
float bevel = lower - upper;
float reflection = UV.y + UV.x * 0.19;
float bandDistance = (reflection - 0.50) * 18.0;
float bounceDistance = (reflection - 0.88) * 11.0;
float brightBand = exp(-bandDistance * bandDistance);
float bounce = exp(-bounceDistance * bounceDistance);
float3 copper = float3(0.39, 0.19, 0.051);
float3 gold = float3(0.90, 0.63, 0.26);
float3 ivory = float3(0.99, 0.86, 0.54);
float3 metal = lerp(copper, gold, 0.47 + 0.29 * cos(6.0 * reflection));
metal = lerp(metal, ivory, 0.84 * brightBand + 0.19 * bounce);
metal = lerp(metal, ivory, saturate(bevel) * 0.66);
return metal * (1.0 - saturate(-bevel) * 0.42);
"""


def material_input(material, property_id):
    return EDIT.get_material_property_input_node(material, property_id)


def custom_inputs(node):
    return [str(item.get_editor_property("input_name")) for item in node.get_editor_property("inputs")]


def new_expression(material, expression_type, position):
    expression = EDIT.create_material_expression(material, expression_type, *position)
    assert expression, expression_type
    return expression


def custom_expression(material, position, description, code, output_type, inputs):
    expression = new_expression(material, u.MaterialExpressionCustom, position)
    expression.set_editor_property("description", description)
    expression.set_editor_property("output_type", output_type)
    expression.set_editor_property("code", code)
    custom = []
    for name, source in inputs:
        entry = u.CustomInput()
        entry.set_editor_property("input_name", name)
        custom.append(entry)
    expression.set_editor_property("inputs", custom)
    for name, source in inputs:
        assert EDIT.connect_material_expressions(source, "", expression, name), name
    return expression


def patch_portal_material(material):
    emissive = material_input(material, u.MaterialProperty.MP_EMISSIVE_COLOR)
    mask = material_input(material, u.MaterialProperty.MP_OPACITY_MASK)
    assert isinstance(emissive, u.MaterialExpressionCustom) and custom_inputs(emissive) == ["UV", "T"]
    assert isinstance(mask, u.MaterialExpressionCustom) and custom_inputs(mask) == ["UV"]
    inputs = EDIT.get_inputs_for_material_expression(material, emissive)
    uv = only(node for node in inputs if isinstance(node, u.MaterialExpressionTextureCoordinate))
    time = only(node for node in inputs if isinstance(node, u.MaterialExpressionTime))
    material.modify()
    emissive.modify()
    emissive.set_editor_property("description", "Cyan rim and violet vortex")
    emissive.set_editor_property("code", PORTAL_COLOR)
    EDIT.delete_material_expression(material, mask)
    opacity = custom_expression(material, (-200, 260), "Vortex transmission", PORTAL_OPACITY,
                                u.CustomMaterialOutputType.CMOT_FLOAT1, (("UV", uv), ("T", time)))
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    assert EDIT.connect_material_property(opacity, "", u.MaterialProperty.MP_OPACITY)


def paw_state(settings):
    tree = widgets(settings)
    heading, bounds, paw = (tree[name] for name in ("SettingsHeading", "SettingsPawBounds", "SettingsPaw"))
    assert isinstance(paw, u.Image) and bounds.get_parent() == heading and paw.get_parent() == bounds
    outer, inner = (widget.get_editor_property("slot") for widget in (bounds, paw))
    size = bounds.get_editor_property("width_override"), bounds.get_editor_property("height_override")
    assert size == (36., 36.) and bounds.get_editor_property("override_width_override") and bounds.get_editor_property("override_height_override")
    brush = paw.get_editor_property("brush")
    resource = brush.get_editor_property("resource_object")
    brush_size = brush.get_editor_property("image_size")
    tint = paw.get_editor_property("color_and_opacity")
    return paw, {
        "resource": resource.get_path_name(), "tint": (tint.r, tint.g, tint.b, tint.a),
        "size": size, "brush_size": brush_size.export_text(),
        "outer_alignment": str(outer.get_editor_property("vertical_alignment")),
        "inner_alignment": str(inner.get_editor_property("vertical_alignment")),
        "visibility": str(paw.get_editor_property("visibility")),
        "tree": [(name, str(widget.get_class().get_path_name()),
                  widget.get_parent().get_name() if widget.get_parent() else None) for name, widget in sorted(tree.items())],
    }


def author_paw(settings, texture):
    assert not AS.does_asset_exist(PAW_MATERIAL)
    folder, name = PAW_MATERIAL.rsplit("/", 1)
    material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    assert material
    material.set_editor_property("material_domain", u.MaterialDomain.MD_UI)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    uv = new_expression(material, u.MaterialExpressionTextureCoordinate, (-660, -140))
    paw = new_expression(material, u.MaterialExpressionTextureObject, (-660, 25))
    paw.set_editor_property("texture", texture)
    alpha = new_expression(material, u.MaterialExpressionTextureSample, (-360, 200))
    alpha.set_editor_property("texture", texture)
    color = custom_expression(material, (-330, -100), "Polished gold", PAW_COLOR,
                               u.CustomMaterialOutputType.CMOT_FLOAT3, (("UV", uv), ("Paw", paw)))
    assert EDIT.connect_material_property(color, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert EDIT.connect_material_property(alpha, "A", u.MaterialProperty.MP_OPACITY)

    widget, before = paw_state(settings)
    assert before["resource"] == texture.get_path_name()
    settings.modify()
    widget.modify()
    widget.set_brush_from_material(material)
    widget.set_editor_property("color_and_opacity", u.LinearColor(1., 1., 1., 1.))
    compile_bp(settings)
    assert paw_state(settings)[1] == dict(before, resource=material.get_path_name(), tint=(1., 1., 1., 1.))
    return material


def describe_material(material):
    color = material_input(material, u.MaterialProperty.MP_EMISSIVE_COLOR)
    opacity = material_input(material, u.MaterialProperty.MP_OPACITY)
    mask = material_input(material, u.MaterialProperty.MP_OPACITY_MASK)
    result = {"domain": str(material.get_editor_property("material_domain")),
              "blend": str(material.get_editor_property("blend_mode")),
              "two_sided": material.get_editor_property("two_sided"),
              "shading": str(material.get_editor_property("shading_model")),
              "has_mask": bool(mask)}
    for name, node in (("color", color), ("opacity", opacity)):
        if isinstance(node, u.MaterialExpressionCustom):
            result[name] = {"code": node.get_editor_property("code"), "inputs": custom_inputs(node)}
        elif isinstance(node, u.MaterialExpressionTextureSample):
            result[name] = {"texture": node.get_editor_property("texture").get_path_name(),
                            "output": EDIT.get_material_property_input_node_output_name(material, u.MaterialProperty.MP_OPACITY)}
        else:
            result[name] = None
    return result


def verify_materials(portal, paw, texture):
    state = describe_material(portal)
    assert portal.get_editor_property("blend_mode") == u.BlendMode.BLEND_TRANSLUCENT
    assert portal.get_editor_property("shading_model") == u.MaterialShadingModel.MSM_UNLIT
    assert state["two_sided"] and not state["has_mask"]
    assert state["color"] == {"code": PORTAL_COLOR, "inputs": ["UV", "T"]}
    assert state["opacity"] == {"code": PORTAL_OPACITY, "inputs": ["UV", "T"]}
    assert paw.get_editor_property("material_domain") == u.MaterialDomain.MD_UI
    assert paw.get_editor_property("blend_mode") == u.BlendMode.BLEND_TRANSLUCENT
    state = describe_material(paw)
    assert state["color"] == {"code": PAW_COLOR, "inputs": ["UV", "Paw"]}
    assert state["opacity"] == {"texture": texture.get_path_name(), "output": "A"}
    inputs = EDIT.get_inputs_for_material_expression(paw, material_input(paw, u.MaterialProperty.MP_EMISSIVE_COLOR))
    mask = only(node for node in inputs if isinstance(node, u.MaterialExpressionTextureObject))
    assert mask.get_editor_property("texture") == texture


def shader_statistics(material):
    stats = EDIT.get_statistics(material)
    return {name: stats.get_editor_property(name) for name in (
        "num_pixel_shader_instructions", "num_vertex_shader_instructions", "num_pixel_texture_samples",
    )}


def clip_state():
    clips = [load_asset(path) for path in CLIPS]
    lengths = (8., 4., 1.2)
    rows = []
    for clip, seconds in zip(clips, lengths):
        assert abs(clip.get_editor_property("sequence_length") - seconds) < .002
        assert not clip.get_editor_property("enable_root_motion")
        assert clip.get_editor_property("skeleton") == clips[0].get_editor_property("skeleton")
        reference = u.AnimationLibrary.extract_root_track_transform(clip, 0.)
        max_displacement = max((u.AnimationLibrary.extract_root_track_transform(clip, min(i / 60., seconds)).translation
                                - reference.translation).length() for i in range(round(seconds * 60) + 1))
        assert max_displacement <= .05, (clip, max_displacement)
        rows.append({"path": clip.get_path_name(), "seconds": clip.get_editor_property("sequence_length"),
                     "max_root_displacement": max_displacement})
    return rows


def normalized(value):
    return json.loads(json.dumps(value))


def run(mode, baseline_path):
    output = ROOT / "Saved/CinematicPolish20261112/PortalPaw" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "report.json"
    report = {"mode": mode, "pid": os.getpid(), "completed": False, "saved": [], "backups": [], "maps": {},
              "source_sha256": digest(Path(__file__)), "playback_performed": False}

    def persist():
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        assert not ED.get_game_world() and not dirty(), dirty()
        cvars = {name: u.SystemLibrary.get_console_variable_int_value(name) for name in ISOLATED_CVARS}
        report["geometry_cvars"] = cvars
        assert all(value == 0 for value in cvars.values()), cvars
        before = report["before_hashes"] = hashes()
        assert all(before[p] for p in (*PROTECTED, SEQUENCE, PORTAL_MATERIAL, SETTINGS))
        if mode in ("author", "audit"):
            assert baseline_path, "Pass -catrunPortalPawBaseline=<completed report.json>"
            baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
            expected_mode = "probe" if mode == "author" else "author"
            assert baseline["mode"] == expected_mode and baseline["completed"] and baseline["pid"] != os.getpid()
            assert baseline["source_sha256"] == report["source_sha256"], "Source changed after the previous run"
            assert baseline["after_hashes"] == before, "Package bytes changed after the previous run"
        sequence, portal, settings, texture = (load_asset(p) for p in (SEQUENCE, PORTAL_MATERIAL, SETTINGS, PAW_TEXTURE))
        report["before"] = {"sequence": describe_sequence(sequence), "portal": describe_material(portal),
                            "paw": paw_state(settings)[1], "clips": clip_state()}
        report["baseline_shader_statistics"] = shader_statistics(portal)
        persist()
        if mode in ("probe", "author"):
            assert not before[PAW_MATERIAL] and not AS.does_asset_exist(PAW_MATERIAL)
            assert len(report["before"]["sequence"]["animations"]) == 4
            assert portal.get_editor_property("blend_mode") == u.BlendMode.BLEND_MASKED
            assert report["before"]["paw"]["resource"] == texture.get_path_name()
        for package in MAPS:
            report["maps"][package] = verify_map(package)
            persist()
        if mode != "probe":
            assert normalized(report["maps"]) == baseline["maps"], "Fresh map probe differs"
        if mode == "author":
            for package in (SEQUENCE, PORTAL_MATERIAL, SETTINGS):
                source = asset_file(package)
                backup = output / "Before" / source.relative_to(ROOT)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, backup)
                assert digest(backup) == before[package]
                report["backups"].append(str(backup))
            persist()
            patch_sequence(sequence)
            patch_portal_material(portal)
            paw = author_paw(settings, texture)
            report["shader_compile_errors"] = {material.get_name(): list(EDIT.recompile_material(material))
                                                for material in (portal, paw)}
            persist()
            assert not any(report["shader_compile_errors"].values()), report["shader_compile_errors"]
        elif mode == "audit":
            paw = load_asset(PAW_MATERIAL)
        if mode in ("author", "audit"):
            report["after"] = {"sequence": describe_sequence(sequence), "portal": describe_material(portal),
                               "paw": paw_state(settings)[1], "paw_material": describe_material(paw)}
            verify_sequence(report["after"]["sequence"])
            verify_materials(portal, paw, texture)
            report["shader_statistics"] = {material.get_name(): shader_statistics(material) for material in (portal, paw)}
            assert report["after"]["sequence"]["bindings"] == report["before"]["sequence"]["bindings"]
            assert report["after"]["paw"]["resource"] == paw.get_path_name()
            assert report["after"]["paw"]["tint"] == (1., 1., 1., 1.)
            if mode == "audit":
                assert normalized(report["after"]) == baseline["after"], "Reloaded package state differs"
            else:
                assert set(dirty()) <= set(OWNED), dirty()
                for package in OWNED:
                    assert AS.save_asset(package, only_if_is_dirty=False), package
                    report["saved"].append(package)
                    persist()
        report["after_hashes"] = hashes()
        assert not dirty(), dirty()
        assert all(before[p] == report["after_hashes"][p] for p in before if p not in report["saved"])
        assert all(before[p] != report["after_hashes"][p] for p in report["saved"])
        report["completed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
        report["dirty_packages"] = dirty()
        raise
    finally:
        persist()
        print("CATRUN_PORTAL_PAW", mode, report["completed"], str(report_path))


command = u.SystemLibrary.get_command_line()
modes = re.findall(r"(?:^|\s)-catrunPortalPaw(Probe|Author|Audit)(?=\s|$)", command, re.I)
baseline = re.search(r'-catrunPortalPawBaseline=(?:"([^"]+)"|(\S+))', command, re.I)
run(only(modes).lower(), (baseline.group(1) or baseline.group(2)) if baseline else None)
