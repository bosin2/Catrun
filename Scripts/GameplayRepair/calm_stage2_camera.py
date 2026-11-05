"""Bounded, idempotent Stage2 calm-camera patch, run under the root editor lease.

Requires the rebuilt Catrun module exposing ResolvePresentationOrthoWidth.
Backs up every owned package and current source before any asset mutation.
Native owns camera transform/framing. BP retains bars, floor dust and door art.
"""
import datetime
import gc
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from toolset_registry.helpers import compile_blueprint

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / "Saved/GameplayAudit20261105/CalmStage2Camera" / datetime.datetime.now().strftime("%H%M%S-%f")
PRES = "/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation"
MAPS = ("/Game/Maps/Stage2", "/Game/Maps/SoundTest_Stage2")
BRIDGE = "/Script/Catrun.CatrunPuzzleRevealComponent.ResolvePresentationOrthoWidth"
TUNING = {"bPreserveGameplayFraming": True, "CameraTravelTime": 2.0,
          "CameraReturnTime": 1.6, "MaximumLockTime": 8.0}
AS = unreal.EditorAssetLibrary
AUDIT_ONLY = bool(globals().get("CATRUN_CALM_CAMERA_AUDIT_ONLY", False))


def dirty_packages():
    return [p.get_name() for p in (
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))]


def save_report():
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def backup(relative):
    source = ROOT / relative
    assert source.is_file(), str(source)
    destination = OUT / "Before" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
    report["backups"].append({"file": relative, "sha256": digest})


def pin(node, name, output=False):
    result = node.find_output_pin(name) if output else node.find_input_pin(name)
    assert result and result.is_valid(), (node.get_name(), name)
    return result


def connect(a, ap, b, bp):
    assert pin(a, ap, True).try_create_connection(pin(b, bp)), (a.get_name(), ap, b.get_name(), bp)


def graph_snapshot(bp):
    return [{"name": g.get_name(), "nodes": [
        {"name": i.node.get_name(), "type": i.type_id,
         "inputs": [{"name": p.name, "value": str(p.value), "links": str(p.connected_pins)} for p in i.input_pins],
         "outputs": [{"name": p.name, "links": str(p.connected_pins)} for p in i.output_pins]}
        for i in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]


def patch_graph(bp):
    expected = {"HandlePhase": 1, "UpdateCamera": 2}
    found = {}
    for graph in BP.list_graphs(bp):
        count = sum(str(i.type_id).endswith("|SetOrthoWidth") for i in BP.get_node_infos(BP.find_nodes(graph)))
        if count:
            found[graph.get_name()] = count
    assert found == expected, found  # Validate complete owned graph scope before the first edit.
    patched = []
    for graph in BP.list_graphs(bp):
        infos = BP.get_node_infos(BP.find_nodes(graph))
        setters = [i.node for i in infos if str(i.type_id).endswith("|SetOrthoWidth")]
        if not setters:
            continue
        assert graph.get_name() in ("UpdateCamera", "HandlePhase"), graph.get_name()
        editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
        bridge_names = {i.node.get_name() for i in infos if "ResolvePresentationOrthoWidth" in i.type_id}
        reveal = None
        for setter in setters:
            width = pin(setter, "InOrthoWidth")
            sources = width.list_connected_pins()
            assert len(sources) == 1, setter.get_name()
            source = sources[0]
            if source.get_owning_node().get_name() not in bridge_names:
                if reveal is None:
                    reveal = editor.add_get_member_variable_node("Reveal", "")
                    assert reveal
                resolve = editor.add_call_function_node(BRIDGE)
                assert resolve, "Rebuild Catrun before running this authoring script"
                connect(reveal, "Reveal", resolve, "self")
                assert source.try_create_connection(pin(resolve, "AuthoredWidth"))
                assert source.break_single_pin_link(width)
                connect(resolve, "ReturnValue", setter, "InOrthoWidth")
                bridge_names.add(resolve.get_name())
            assert pin(setter, "InOrthoWidth").list_connected_pins()[0].get_owning_node().get_name() in bridge_names
            patched.append({"graph": graph.get_name(), "setter": setter.get_name(), "captured_width_bridge": True})
    assert len(patched) == 3, patched  # initial, outbound and return endpoints
    return patched


def audit_graph(bp):
    result = []
    for graph in BP.list_graphs(bp):
        infos = BP.get_node_infos(BP.find_nodes(graph))
        bridges = {i.node.get_name() for i in infos if "ResolvePresentationOrthoWidth" in i.type_id}
        for info in infos:
            if str(info.type_id).endswith("|SetOrthoWidth"):
                sources = pin(info.node, "InOrthoWidth").list_connected_pins()
                assert len(sources) == 1 and sources[0].get_owning_node().get_name() in bridges
                result.append({"graph": graph.get_name(), "setter": info.node.get_name()})
    assert len(result) == 3, result
    return result


def vector_values(value):
    return [float(value.x), float(value.y), float(value.z)]


def reference_path(value):
    return value.get_path_name() if value else None


def transform_values(value):
    q = value.rotation
    rotation = [float(q.x), float(q.y), float(q.z), float(q.w)]
    # q and -q encode the same rotation; choose one stable hemisphere.
    sign = next((1 if x > 0 else -1 for x in reversed(rotation) if abs(x) > 1e-12), 1)
    return {"translation": vector_values(value.translation),
            "rotation_xyzw": [x * sign for x in rotation],
            "scale": vector_values(value.scale3d)}


def differences(actual, expected, path=""):
    """Stable, tolerant preservation evidence; never compare struct repr/address."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        result = []
        for key in sorted(set(actual) | set(expected)):
            child = path + "/" + key
            if key not in actual or key not in expected:
                result.append({"path": child, "before": expected.get(key), "after": actual.get(key)})
            else:
                result.extend(differences(actual[key], expected[key], child))
        return result
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)) and len(actual) == len(expected):
        return [item for i, (a, e) in enumerate(zip(actual, expected)) for item in differences(a, e, path + "/" + str(i))]
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        same = math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-4)
    else:
        same = actual == expected
    return [] if same else [{"path": path, "before": expected, "after": actual}]


def inspect_map(expected=None, apply=False, package="", stage="snapshot", verify_tuning=False):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    directors = [a for a in actors if isinstance(a, unreal.CatrunStatuePuzzle)]
    assert len(directors) == 1
    director = directors[0]
    reveal = director.get_editor_property("Reveal")
    presentation_class = AS.load_blueprint_class(PRES)
    presentations = [a for a in actors if a.get_class() == presentation_class]
    assert len(presentations) == 3
    assert {str(a.get_editor_property("PuzzleId")) for a in presentations} == {"A", "B", "C"}
    assert all(a.get_editor_property("Director") == director for a in presentations)
    if apply:
        for name, value in TUNING.items():
            reveal.set_editor_property(name, value)
        for actor in presentations:
            actor.set_editor_property("RumbleStrength", 0.0)
    result = {
        "actors": {a.get_path_name(): {"class": a.get_class().get_path_name(),
                   "transform": transform_values(a.get_actor_transform())} for a in actors},
        "reveal": {name: reveal.get_editor_property(name) for name in TUNING},
        "presentation": {str(a.get_editor_property("PuzzleId")): {
            "RumbleStrength": float(a.get_editor_property("RumbleStrength")),
            "BarHeight": float(a.get_editor_property("BarHeight")),
            "CameraOffset": vector_values(a.get_editor_property("CameraOffset")),
            "RevealOrthoWidth": float(a.get_editor_property("RevealOrthoWidth")),
            "Gate": reference_path(a.get_editor_property("Gate")),
            "Director": reference_path(a.get_editor_property("Director"))}
            for a in presentations},
    }
    issues = []
    if expected is not None:
        issues.extend(differences(result["actors"], expected["actors"], "actors"))
        for key, values in result["presentation"].items():
            for name in ("BarHeight", "CameraOffset", "RevealOrthoWidth", "Gate", "Director"):
                issues.extend(differences(values[name], expected["presentation"][key][name], "presentation/"+key+"/"+name))
    if apply or expected is not None or verify_tuning:
        issues.extend(differences(result["reveal"], TUNING, "reveal"))
        for key, values in result["presentation"].items():
            issues.extend(differences(values["RumbleStrength"], 0.0, "presentation/"+key+"/RumbleStrength"))
    report["maps"].setdefault(package, {})[stage] = result
    report["maps"][package][stage + "_differences"] = issues
    save_report()  # Evidence must survive any assertion below.
    assert not issues, (package, stage, issues)
    return result


assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), "Stop PIE before asset authoring"
assert not dirty_packages(), "Save existing unsaved work before running the owned patch"
assert hasattr(unreal.CatrunPuzzleRevealComponent, "resolve_presentation_ortho_width"), "Rebuild Catrun first"
OUT.mkdir(parents=True, exist_ok=False)
report = {"tuning": TUNING, "rumble": 0.0, "backups": [], "maps": {}, "runtime_verified": False,
          "audit_only": AUDIT_ONLY, "process_id": os.getpid()}
if AUDIT_ONLY:
    # Invoke in a NEW Unreal process after authoring to prove saved-package persistence.
    bp = AS.load_asset(PRES)
    report["graph_audit"] = audit_graph(bp)
    report["default_rumble"] = unreal.get_default_object(bp.generated_class()).get_editor_property("RumbleStrength")
    report["blueprint_status"] = str(bp.get_editor_property("status"))
    save_report()
    assert report["default_rumble"] == 0
    assert bp.get_editor_property("status") == unreal.BlueprintStatus.BS_UP_TO_DATE
    del bp
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    for package in MAPS:
        assert level.load_level(package)
        before = inspect_map(package=package, stage="cold_loaded", verify_tuning=True)
        assert level.load_level("/Game/Maps/MainMenu")
        gc.collect()
        assert level.load_level(package)
        inspect_map(before, package=package, stage="reloaded", verify_tuning=True)
        gc.collect()
    report["saved_asset_audit_complete"] = True
    save_report()
    print("CALM_STAGE2_CAMERA_AUDITED", str(OUT))
else:
    for relative in (
        "Source/Catrun/Interaction/CatrunPuzzleRevealComponent.h",
        "Source/Catrun/Interaction/CatrunPuzzleRevealComponent.cpp",
        "Source/Catrun/Interaction/Tests/CalmPuzzleRevealTests.cpp",
        "Scripts/GameplayRepair/calm_stage2_camera.py",
        "Content/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.uasset",
        "Content/Maps/Stage2.umap", "Content/Maps/SoundTest_Stage2.umap"):
        backup(relative)
    save_report()

    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    original_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    original_map = original_world.get_path_name().split(".")[0]
    del original_world
    bp = AS.load_asset(PRES)
    report["blueprint_before"] = graph_snapshot(bp)
    default = unreal.get_default_object(bp.generated_class())
    report["default_rumble_before"] = default.get_editor_property("RumbleStrength")
    report["bridges"] = patch_graph(bp)
    compile_blueprint(bp, True)
    assert bp.get_editor_property("status") == unreal.BlueprintStatus.BS_UP_TO_DATE
    default = unreal.get_default_object(bp.generated_class())
    default.set_editor_property("RumbleStrength", 0.0)
    assert AS.save_loaded_asset(bp, False)
    report["blueprint_after"] = graph_snapshot(bp)
    report["graph_audit"] = audit_graph(bp)
    assert unreal.get_default_object(bp.generated_class()).get_editor_property("RumbleStrength") == 0
    save_report()
    del default, bp
    gc.collect()

    for package in MAPS:
        assert level.load_level(package)
        before = inspect_map(package=package, stage="before")
        after = inspect_map(before, apply=True, package=package, stage="after")
        assert level.save_current_level()
        gc.collect()
        assert level.load_level("/Game/Maps/MainMenu")
        gc.collect()
        assert level.load_level(package)
        reloaded = inspect_map(before, package=package, stage="reloaded")
        save_report()
        gc.collect()

    assert level.load_level(original_map if original_map.startswith("/Game/") else "/Game/Maps/MainMenu")
    bp = AS.load_asset(PRES)
    compile_blueprint(bp, True)
    assert bp.get_editor_property("status") == unreal.BlueprintStatus.BS_UP_TO_DATE
    report["final_graph_audit"] = audit_graph(bp)
    assert unreal.get_default_object(bp.generated_class()).get_editor_property("RumbleStrength") == 0
    assert AS.save_loaded_asset(bp, False)
    assert not dirty_packages()
    report["asset_authoring_complete"] = True
    save_report()
    print("CALM_STAGE2_CAMERA_SAVED", str(OUT))
