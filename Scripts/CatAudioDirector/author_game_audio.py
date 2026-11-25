"""Author and audit the CastleAudio_20261112 assets in a hidden UE commandlet."""

import hashlib
import json
import re
import shutil
import sys
import traceback
from pathlib import Path

import unreal as ue
from editor_toolset.toolsets.blueprint import BlueprintTools


ROOT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
OUT = ROOT / "Saved/CatAudioDirector/Production20261112/Unreal"
RUN_ID = "CastleAudio_20261112"
AUDIO = f"/Game/Audio/CatAudioDirector/{RUN_ID}"
BELL = "/Game/Systems/Player/Interaction/BP_CatActions"
ARMOR = "/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor"
ARMOR_ABP = "/Game/Characters/LivingArmor/Final/Animations/ABP_ArmorPresentation"
PORTAL = "/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit"
TRACK_NAME = "Catrun Armor Footsteps"
NOTIFY_CLASS = "/Script/Catrun.AnimNotify_CatrunArmorFootstep"
DISPLAY = ue.MovieSceneTimeUnit.DISPLAY_RATE
TICKS = ue.MovieSceneTimeUnit.TICK_RESOLUTION
ANIM = ue.AnimationLibrary
ASSETS = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
TOOLS = ue.AssetToolsHelpers.get_asset_tools()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def object_path(obj):
    return obj.get_path_name() if obj else None


def asset(path):
    obj = ASSETS.load_asset(path)
    assert obj, f"Missing asset {path}"
    return obj


def package_path(obj):
    return obj.get_path_name().split(".", 1)[0]


def package_file(package):
    assert package.startswith("/Game/")
    return ROOT / "Content" / (package.removeprefix("/Game/") + ".uasset")


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def content_hashes():
    return {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in sorted((ROOT / "Content").rglob("*"))
        if path.suffix in (".uasset", ".umap", ".uexp", ".ubulk")
        and not path.is_relative_to(package_file(AUDIO).with_suffix(""))
    }


def dirty_packages():
    loading = ue.EditorLoadingAndSavingUtils
    return sorted(
        item.get_path_name()
        for item in [*loading.get_dirty_content_packages(), *loading.get_dirty_map_packages()]
    )


def default_object(blueprint):
    return ue.get_default_object(blueprint.generated_class())


def graph_snapshot(blueprint):
    graphs = {}
    for graph in BlueprintTools.list_graphs(blueprint):
        nodes = BlueprintTools.get_node_infos(BlueprintTools.find_nodes(graph))
        graphs[graph.get_name()] = {
            node.node.get_name(): {
                "type": node.type_id,
                "position": [node.position.x, node.position.y],
                "inputs": [
                    [pin.name, pin.type_id, str(pin.value), sorted(map(str, pin.connected_pins))]
                    for pin in node.input_pins
                ],
                "outputs": [
                    [pin.name, pin.type_id, str(pin.value), sorted(map(str, pin.connected_pins))]
                    for pin in node.output_pins
                ],
            }
            for node in nodes
        }
    return graphs


def serialize(value):
    if isinstance(value, ue.Object):
        return value.get_path_name()
    if hasattr(value, "export_text"):
        return value.export_text()
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    return re.sub(r"0x[0-9A-Fa-f]+", "<address>", str(value))


def channel_snapshot(channel):
    def key_snapshot(key):
        time = key.get_time(TICKS)
        return {
            "time": [time.frame_number.value, time.sub_frame],
            "fields": {
                getter: serialize(getattr(key, getter)())
                for getter in (
                    "get_value", "get_interpolation_mode", "get_tangent_mode",
                    "get_tangent_weight_mode", "get_arrive_tangent", "get_leave_tangent",
                    "get_arrive_tangent_weight", "get_leave_tangent_weight",
                )
                if hasattr(key, getter)
            },
        }

    row = {"class": channel.get_class().get_name(), "keys": [key_snapshot(k) for k in channel.get_keys()]}
    if hasattr(channel, "get_default") and channel.has_default():
        row["default"] = serialize(channel.get_default())
    return row


def section_snapshot(section):
    row = {
        "class": section.get_class().get_name(),
        "range": [section.get_start_frame(), section.get_end_frame()],
        "row": section.get_row_index(),
        "channels": [channel_snapshot(c) for c in section.get_all_channels()],
    }
    if isinstance(section, ue.MovieSceneCameraCutSection):
        row["camera_binding"] = serialize(section.get_camera_binding_id())
    if isinstance(section, ue.MovieSceneSkeletalAnimationSection):
        row["animation_params"] = serialize(section.get_editor_property("params"))
        row["animation"] = object_path(section.get_editor_property("params").get_editor_property("animation"))
    if isinstance(section, ue.MovieSceneAudioSection):
        row.update(
            sound=object_path(section.get_sound()), looping=section.get_looping(),
            play_until_finished=section.get_play_until_finished(),
        )
    return row


def track_snapshot(track):
    return {
        "class": track.get_class().get_name(),
        "object": track.get_name(),
        "display_name": str(track.get_display_name()),
        "sections": [section_snapshot(section) for section in track.get_sections()],
    }


def sequence_snapshot(sequence):
    def binding_snapshot(binding):
        parent = binding.get_parent()
        return {
            "id": serialize(binding.get_id()),
            "name": binding.get_name(),
            "parent": serialize(parent.get_id()) if parent.is_valid() else None,
            "tags": sorted(map(str, binding.get_binding_tags())),
            "tracks": [track_snapshot(track) for track in binding.get_tracks()],
        }

    return {
        "display_rate": serialize(sequence.get_display_rate()),
        "tick_resolution": serialize(sequence.get_tick_resolution()),
        "range": [sequence.get_playback_start(), sequence.get_playback_end()],
        "tracks": [track_snapshot(track) for track in sequence.get_tracks()],
        "bindings": [binding_snapshot(binding) for binding in sequence.get_bindings()],
    }


def notify_snapshot(sequence, track):
    return [
        {
            "name": str(event.get_editor_property("notify_name")),
            "time": ANIM.get_anim_notify_event_trigger_time(event),
            "duration": ANIM.get_anim_notify_event_duration(event),
            "notify": object_path(event.get_editor_property("notify")),
            "notify_state": object_path(event.get_editor_property("notify_state_class")),
        }
        for event in ANIM.get_animation_notify_events_for_track(sequence, track)
    ]


def animation_snapshot(sequence):
    length = sequence.get_play_length()
    pose = ue.AnimPoseExtensions
    options = ue.AnimPoseEvaluationOptions()
    first_pose = pose.get_anim_pose_at_frame(sequence, 0, options)
    assert pose.is_valid(first_pose), sequence.get_path_name()
    bones = list(pose.get_bone_names(first_pose))
    feet = [bone for bone in bones if any(word in str(bone).lower() for word in ("foot", "toe", "ankle"))]
    assert len(feet) >= 2, list(map(str, bones))
    sample_count = ANIM.get_num_keys(sequence)
    assert sample_count > 2
    pose_hash = hashlib.sha256()
    samples = []
    for frame in range(sample_count):
        sample_pose = pose.get_anim_pose_at_frame(sequence, frame, options)
        assert pose.is_valid(sample_pose), frame
        for bone in bones:
            local = pose.get_bone_pose(sample_pose, bone, ue.AnimPoseSpaces.LOCAL)
            pose_hash.update(local.export_text().encode("utf-8"))
        row = {}
        for foot in feet:
            world = pose.get_bone_pose(sample_pose, foot, ue.AnimPoseSpaces.WORLD)
            location = world.translation
            row[str(foot)] = [round(location.x, 4), round(location.y, 4), round(location.z, 4)]
        samples.append(row)
    return {
        "duration": length,
        "skeleton": object_path(sequence.get_editor_property("skeleton")),
        "bones": list(map(str, bones)),
        "notify_tracks": {
            str(track): notify_snapshot(sequence, track)
            for track in ANIM.get_animation_notify_track_names(sequence)
        },
        "pose_sha256": pose_hash.hexdigest(),
        "foot_samples": samples,
    }


def existing_state():
    bell = asset(BELL)
    armor = default_object(asset(ARMOR))
    animations = {name: armor.get_editor_property(f"{name}_anim") for name in ("walk", "run")}
    assert all(isinstance(item, ue.AnimSequence) for item in animations.values())
    return {
        "bell_sound": object_path(default_object(bell).get_editor_property("BellSound")),
        "bell_graphs": graph_snapshot(bell),
        "armor_graphs": graph_snapshot(asset(ARMOR)),
        "armor_animation_graphs": graph_snapshot(asset(ARMOR_ABP)),
        "armor_animations": {
            name: {"path": package_path(item), **animation_snapshot(item)}
            for name, item in animations.items()
        },
        "portal": sequence_snapshot(asset(PORTAL)),
    }


def baseline(report):
    destination = OUT / "baseline.json"
    assert not destination.exists(), f"Baseline already recorded at {destination}"
    assert not package_file(AUDIO).with_suffix("").exists(), "New audio run already exists"
    report.update(existing_state())
    packages = [BELL, PORTAL, *(row["path"] for row in report["armor_animations"].values())]
    report["asset_hashes"] = content_hashes()
    report["backups"] = {}
    for package in packages:
        original = package_file(package)
        for source in original.parent.glob(original.stem + ".*"):
            relative = source.relative_to(ROOT)
            backup = OUT / "Before" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
            assert sha256(source) == sha256(backup), source
            report["backups"][relative.as_posix()] = sha256(backup)
    report["dirty_after"] = dirty_packages()
    assert not report["dirty_after"], report["dirty_after"]
    report["status"] = "passed"
    write_json(destination, report)


if __name__ == "__main__":
    report = {"status": "failed"}
    try:
        assert ue.SystemLibrary.get_engine_version().startswith("5.8.")
        assert (ROOT / "Catrun.uproject").is_file()
        assert not dirty_packages(), dirty_packages()
        baseline(report)
    except Exception:
        report["error"] = traceback.format_exc()
        write_json(OUT / "author_error.json", report)
        raise
