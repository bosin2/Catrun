"""Repair the Stage 1 wall flags and the shared startup packages.

Load Stage1 or SoundTest_Stage1 separately before running this script. It does
not load levels or start play. Set CATRUN_STARTUP_WARNINGS_MODE to "dry" (the
default), "apply", or "cold". Cold verification requires a fresh editor load.
Set CATRUN_STARTUP_WARNINGS_INCLUDE_ASSETS=False for a map-only pass. A cold
pass can compare with an apply report via CATRUN_STARTUP_WARNINGS_BASELINE.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
CONTENT = ROOT / "Content"
MAPS = ("/Game/Maps/Stage1", "/Game/Maps/SoundTest_Stage1")
MODE_BP = "/Game/Blueprints/GameModes/GM_Cat"
WIDGET = "/Game/Cinematics/Stage1/Portal/WBP_ExitTransition"
WALL_FOLDER = "/Game/Environment/Stage1/Meshes/Walls"
STONE_FOLDER = "/Game/Environment/Shared/Castle/Materials/Stone"
OCCLUSION_FOLDER = "/Game/Systems/Camera/Occlusion/Materials"
WALL_INSTANCE = STONE_FOLDER + "/MI_CastleStone_WallOcclusion"
HUD = "/Script/Engine.HUD"
MODE_PROPERTIES = (
    "hud_class", "default_pawn_class", "player_controller_class",
    "game_state_class", "game_session_class", "player_state_class",
    "spectator_class", "replay_spectator_player_controller_class",
    "server_stat_replicator_class", "start_players_as_spectators",
    "use_seamless_travel", "pauseable",
)
PACKAGE_EXTENSIONS = (".uasset", ".umap", ".uexp", ".ubulk", ".uptnl")
GUID_LINE = re.compile(r"^\s*NodeGuid=([\da-fA-F]{32})\s*$", re.MULTILINE)


def object_path(obj):
    return obj.get_path_name() if obj else None


def file_for(package, suffix=".uasset"):
    assert package == "/Game" or package.startswith("/Game/"), package
    return CONTENT / (package[6:] + suffix)


def file_hash(file):
    with file.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def package_files(package):
    return [file_for(package, ext) for ext in PACKAGE_EXTENSIONS
            if file_for(package, ext).is_file()]


def watched_files():
    files = set()
    for folder, pattern in (
        ("/Game", "Stage[12]*"),
        ("/Game/Maps", "Stage[12]*"),
        ("/Game/Maps", "SoundTest_Stage[12]*"),
        ("/Game/Cinematics/Stage1/Portal", "*"),
        ("/Game/Environment/Stage1/Materials/CastleStone", "MI_CastleStone_WallOcclusion.*"),
        (WALL_FOLDER, "SM_Stage01_Wall_*"),
        (STONE_FOLDER, "*CastleStone_Wall*"),
        (OCCLUSION_FOLDER, "*Wall*"),
    ):
        files.update(f for f in file_for(folder, "").glob(pattern)
                     if f.is_file() and f.suffix in PACKAGE_EXTENSIONS)
    files.update(package_files(MODE_BP))
    return {file.relative_to(CONTENT).as_posix(): file_hash(file) for file in sorted(files)}


def dirty_packages():
    io = u.EditorLoadingAndSavingUtils
    return {p.get_name() for p in (*io.get_dirty_map_packages(), *io.get_dirty_content_packages())}


def inspect_level(world, package):
    actors = {}
    walls = {}
    targets = {}
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        owner = actor.get_outermost().get_name()
        actor_path = object_path(actor)
        actors[actor_path] = {
            "label": actor.get_actor_label(),
            "class": object_path(actor.get_class()),
            "pose": actor.get_actor_transform().export_text(),
        }
        for comp in actor.get_components_by_class(u.StaticMeshComponent):
            mesh = comp.static_mesh
            if not mesh or not mesh.get_name().startswith("SM_Stage01_Wall_"):
                continue
            count = comp.get_num_materials()
            materials = [object_path(comp.get_material(i)) for i in range(count)]
            slots = [i for i, mat in enumerate(materials)
                     if mat and mat.split(".", 1)[0] == WALL_INSTANCE]
            comp_path = object_path(comp)
            disallow = comp.get_editor_property("disallow_nanite")
            walls[comp_path] = {
                "actor": actor_path,
                "owner_package": owner,
                "mesh": object_path(mesh),
                "world_transform": comp.get_world_transform().export_text(),
                "collision_profile": str(comp.get_collision_profile_name()),
                "default_materials": [object_path(mesh.get_material(i)) for i in range(count)],
                "effective_materials": materials,
                "override_materials": [object_path(m) for m in comp.get_editor_property("override_materials")],
                "occlusion_slots": slots,
                "nanite_enabled": mesh.get_editor_property("nanite_settings").get_editor_property("enabled"),
                "disallow_nanite": disallow,
            }
            if slots:
                assert owner == package == comp.get_outermost().get_name(), (package, comp_path, owner)
                targets[comp_path] = comp
    settings = world.get_world_settings()
    return {
        "game_mode": object_path(settings.get_editor_property("default_game_mode")),
        "actors": actors,
        "walls": walls,
        "target_components": sorted(targets),
    }, targets


def inspect_mode(blueprint):
    defaults = u.get_default_object(blueprint.generated_class())
    fields = {}
    for name in MODE_PROPERTIES:
        value = defaults.get_editor_property(name)
        fields[name] = object_path(value) if isinstance(value, u.Object) else value
    return fields, defaults


def inspect_widget(widget, output):
    # NodeGuid is a protected UPROPERTY. The stock T3D exporter can read it.
    graph = u.BlueprintGraphEditor.get_graph_editor_by_name(widget, u.Name("UpdateStatus"))
    assert graph, (WIDGET, "UpdateStatus")
    comments = [node for node in graph.list_comment_nodes()
                if node.get_name() == "EdGraphNode_Comment_0"]
    assert len(comments) <= 1, WIDGET
    if not comments:
        return {"comment": None, "guid": None, "stored": None}
    comment = comments[0]
    task = u.AssetExportTask()
    task.object = comment
    task.exporter = u.ObjectExporterT3D()
    task.filename = str(output)
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    assert u.Exporter.run_asset_export_task(task) and output.is_file(), str(task.errors)
    exported = output.read_bytes()
    encoding = "utf-16" if exported.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    match = GUID_LINE.search(exported.decode(encoding))
    assert match, ("No NodeGuid in the editor export", str(output))
    guid = match.group(1).upper()
    assert int(guid, 16), ("Invalid NodeGuid in memory", object_path(comment))
    payload = struct.pack("<IIII", *(int(guid[i:i + 8], 16) for i in range(0, 32, 8)))
    # PostLoad can generate an in-memory GUID for old bytes. Require its actual
    # serialized representation to distinguish repaired packages on repeat runs.
    stored = any(payload in f.read_bytes() for f in package_files(WIDGET)
                 if f.suffix in (".uasset", ".uexp"))
    return {"comment": object_path(comment), "guid": guid, "stored": stored}


def backup_packages(packages, output, before):
    for package in packages:
        files = package_files(package)
        assert files, package
        for file in files:
            relative = file.relative_to(CONTENT)
            backup = output / "Before" / "Content" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, backup)
            assert file_hash(backup) == before[relative.as_posix()], str(file)


def save_package(obj):
    package = obj.get_outermost()
    assert u.EditorLoadingAndSavingUtils.save_packages([package], False), package.get_name()


def changed_files(before, after):
    return sorted(f for f in before.keys() | after.keys() if before.get(f) != after.get(f))


def package_keys(package):
    return {file_for(package, ext).relative_to(CONTENT).as_posix() for ext in PACKAGE_EXTENSIONS}


def run(mode="dry", *, include_assets=True, baseline=None):
    assert mode in ("dry", "apply", "cold"), mode
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = ROOT / "Saved/StageRevision20261123/StartupWarnings" / stamp
    output.mkdir(parents=True)
    report_file = output / "report.json"
    report = {"mode": mode, "completed": False, "saved": [], "include_assets": include_assets}
    try:
        editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        assert not editor.get_game_world(), "Requires the editor outside PIE"
        world = editor.get_editor_world()
        package = world.get_outermost().get_name()
        assert package in MAPS, ("Load a supported map before running", package)
        before_hashes = watched_files()
        before_dirty = dirty_packages()
        report.update(map=package, before_hashes=before_hashes, dirty_before=sorted(before_dirty))
        if mode == "cold":
            checked = {package, MODE_BP, WIDGET} if include_assets else {package}
            assert not before_dirty & checked, ("Cold audit requires freshly loaded packages", before_dirty & checked)
        level_before, targets = inspect_level(world, package)
        assert targets, ("No matching wall components", package)
        walls_to_change = [key for key in level_before["target_components"]
                           if not level_before["walls"][key]["disallow_nanite"]]
        report.update(level_before=level_before, wall_targets=len(targets),
                      walls_to_change=walls_to_change)

        gm = widget = mode_before = widget_before = None
        if include_assets:
            gm = u.EditorAssetLibrary.load_asset(MODE_BP)
            assert gm, MODE_BP
            mode_before, defaults = inspect_mode(gm)
            widget = u.EditorAssetLibrary.load_asset(WIDGET) if file_for(WIDGET).is_file() else None
            assert widget or not file_for(WIDGET).is_file(), WIDGET
            if widget:
                widget_before = inspect_widget(widget, output / "UpdateStatus-before.t3d")
        fix_hud = mode_before is not None and mode_before["hud_class"] is None
        resave_widget = bool(widget_before and widget_before["stored"] is False)
        report.update(mode_before=mode_before, widget_before=widget_before,
                      hud_needs_default=fix_hud, widget_needs_resave=resave_widget)

        expected = json.loads(json.dumps(level_before))
        expected_mode = dict(mode_before) if mode_before else None
        allow_packages = []
        if mode == "apply":
            if walls_to_change:
                allow_packages.append(package)
            if fix_hud:
                allow_packages.append(MODE_BP)
            if resave_widget:
                allow_packages.append(WIDGET)
        allow_files = {key for target in allow_packages for key in package_keys(target)}
        report.update(allowed_packages=allow_packages, allowed_files=sorted(allow_files))

        if mode == "apply" and allow_packages:
            assert not set(allow_packages) & before_dirty, ("Target already dirty", before_dirty)
            assert watched_files() == before_hashes, "A watched package changed during preflight"
            backup_packages(allow_packages, output, before_hashes)
            try:
                with u.ScopedEditorTransaction("Repair Catrun map startup warnings"):
                    for key in walls_to_change:
                        comp = targets[key]
                        comp.modify()
                        comp.set_editor_property("disallow_nanite", True)
                        expected["walls"][key]["disallow_nanite"] = True
                    if fix_hud:
                        hud_class = u.load_class(None, HUD)
                        assert object_path(hud_class) == HUD, HUD
                        defaults.modify()
                        defaults.set_editor_property("hud_class", hud_class)
                        expected_mode["hud_class"] = HUD
                    assert inspect_level(world, package)[0] == expected, "Unexpected actor, pose, or wall change"
                    if gm:
                        assert inspect_mode(gm)[0] == expected_mode, "Unexpected GameMode default change"
                    assert not (dirty_packages() - before_dirty - set(allow_packages)), "Unexpected dirty package"
            except Exception:
                for key in walls_to_change:
                    targets[key].set_editor_property("disallow_nanite", False)
                if fix_hud:
                    defaults.set_editor_property("hud_class", None)
                raise
            assert watched_files() == before_hashes, "A watched package changed before save"
            for obj, target, enabled in ((world, package, bool(walls_to_change)),
                                         (gm, MODE_BP, fix_hud), (widget, WIDGET, resave_widget)):
                if enabled:
                    save_package(obj)
                    report["saved"].append(target)

        level_after = inspect_level(world, package)[0]
        mode_after = inspect_mode(gm)[0] if gm else None
        widget_after = inspect_widget(widget, output / "UpdateStatus-after.t3d") if resave_widget and mode == "apply" else widget_before
        report.update(level_after=level_after, mode_after=mode_after, widget_after=widget_after)
        assert level_after == expected, "Actor pose, component, or material mismatch"
        assert mode_after == expected_mode, "GameMode default mismatch"
        if mode == "apply" and resave_widget:
            assert widget_after["stored"] and widget_after["guid"] == widget_before["guid"], widget_after
        if mode == "cold":
            assert not walls_to_change and not fix_hud and not resave_widget, "A startup repair is absent on cold load"
            if baseline:
                expected_report = json.loads(Path(baseline).read_text(encoding="utf-8"))
                assert expected_report["completed"] and expected_report["mode"] == "apply"
                assert expected_report["map"] == package and expected_report["level_after"] == level_after
                if include_assets:
                    assert expected_report["mode_after"] == mode_after
                    assert expected_report["widget_after"] == widget_after
        report["completed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
        raise
    finally:
        report["dirty_after"] = sorted(dirty_packages())
        report["after_hashes"] = watched_files()
        if "before_hashes" in report:
            report["changed_files"] = changed_files(report["before_hashes"], report["after_hashes"])
            changed = set(report["changed_files"])
            report["unallowed_file_changes"] = sorted(changed - set(report.get("allowed_files", [])))
            report["saved_without_file_changes"] = [target for target in report["saved"]
                                                    if not changed & package_keys(target)]
            if report["unallowed_file_changes"] or report["saved_without_file_changes"]:
                report["completed"] = False
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("CATRUN_STARTUP_WARNINGS_REPORT", str(report_file))
    assert not report["unallowed_file_changes"], report["unallowed_file_changes"]
    assert not report["saved_without_file_changes"], report["saved_without_file_changes"]
    return report


if __name__ == "__main__":
    run(globals().get("CATRUN_STARTUP_WARNINGS_MODE", "dry"),
        include_assets=globals().get("CATRUN_STARTUP_WARNINGS_INCLUDE_ASSETS", True),
        baseline=globals().get("CATRUN_STARTUP_WARNINGS_BASELINE"))
