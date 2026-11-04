"""Run with UnrealEditor-Cmd -run=pythonscript -script=<absolute path>.
Adds gameplay to the existing Stage2/SoundTest_Stage2 meshes without relocating them.
Back up the maps before running. This script is idempotent and saves only its target assets.
"""
import json
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir())
OUT = ROOT / "Saved" / "Stage2"
OUT.mkdir(parents=True, exist_ok=True)
ASSETS = unreal.EditorAssetLibrary
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SETTINGS_PATH = "/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings"
settings = ASSETS.load_asset(SETTINGS_PATH)
if settings is None:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.CatrunStatuePuzzleSettings)
    settings = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "DA_StatuePuzzleSettings", "/Game/Systems/Interaction/Puzzles", unreal.CatrunStatuePuzzleSettings, factory)
    if settings is None:
        raise RuntimeError("Could not create shared puzzle settings")
ASSETS.save_loaded_asset(settings)

# Actual current map: A -> maze gate, B -> lower room-3 passage, C -> practice-room exit.
GATES = {"A": "S2_Gate_02_Bars", "B": "S2_Gate_05_Bars", "C": "S2_Gate_11_Bars"}
report = []
for map_name in ("Stage2", "SoundTest_Stage2"):
    map_path = "/Game/Maps/" + map_name
    if not LEVELS.load_level(map_path):
        raise RuntimeError("Could not load " + map_path)
    actors = list(ACTORS.get_all_level_actors())
    labels = {a.get_actor_label(): a for a in actors}
    links = []
    for key, gate_label in GATES.items():
        names = ["S2_Prop_Statue_" + key, "S2_Prop_Plate_" + key + "_Plate", gate_label]
        missing = [name for name in names if name not in labels]
        if missing:
            raise RuntimeError(map_name + " missing actors: " + str(missing))
        statue, plate, gate = [labels[name] for name in names]
        for actor in (statue, plate, gate):
            mesh = actor.get_component_by_class(unreal.StaticMeshComponent)
            mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
            mesh.set_simulate_physics(False)
            mesh.set_collision_profile_name("BlockAllDynamic")
            # These obstacles are evaluated dynamically, not frozen into the baked wall grid.
            actor.set_editor_property("tags", [tag for tag in actor.get_editor_property("tags") if str(tag) != "SoundWall"])
        link = unreal.CatrunStatuePuzzleLink()
        link.set_editor_property("puzzle_id", key)
        link.set_editor_property("statue", statue)
        link.set_editor_property("plate", plate)
        link.set_editor_property("gate", gate)
        links.append(link)
    controllers = [a for a in actors if isinstance(a, unreal.CatrunStatuePuzzle)]
    if len(controllers) > 1:
        raise RuntimeError("Duplicate puzzle controllers in " + map_name)
    controller = controllers[0] if controllers else ACTORS.spawn_actor_from_class(unreal.CatrunStatuePuzzle, unreal.Vector(0, 0, 0))
    controller.set_actor_label("S2_StatuePuzzle")
    controller.set_folder_path("Gameplay/Puzzles")
    controller.set_editor_property("settings", settings)
    controller.set_editor_property("links", links)
    for actor in actors:
        if isinstance(actor, unreal.SoundGridManager):
            actor.build_grid()
    if not LEVELS.save_current_level():
        raise RuntimeError("Could not save " + map_name)
    report.append({"map": map_path, "controller": controller.get_path_name(), "links": GATES,
                   "settings": settings.get_path_name()})
(OUT / "setup.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("STAGE2_SETUP_OK " + json.dumps(report))
