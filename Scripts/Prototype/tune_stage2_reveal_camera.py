"""Apply the user-requested calmer Stage2 reveal to both authored maps.

Run only after the controller grants this script the editor lease. No native
defaults or connected Blueprint graphs are changed. Each map is inspected,
backed up, saved and reloaded independently so no UWorld wrappers cross travel.
"""
import datetime
import gc
import hashlib
import json
import shutil
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / "Saved/Prototype20261104/CalmerReveal" / datetime.datetime.now().strftime("%H%M%S-%f")
TIMES = {"CameraTravelTime": 2.0, "CameraReturnTime": 1.6}
PRESENTATION = {"RevealOrthoWidth": 1050.0, "RumbleStrength": 0.00015}
PRESENTATION_CLASS = "/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation"


def dirty_packages():
    return [p.get_name() for p in (
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))]


def inspect_map(expected=None, apply=False):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    directors = [a for a in actors if isinstance(a, unreal.CatrunStatuePuzzle)]
    assert len(directors) == 1, "Expected one Stage2 puzzle director"
    director = directors[0]
    reveal = director.get_editor_property("Reveal")
    presentation_class = unreal.EditorAssetLibrary.load_blueprint_class(PRESENTATION_CLASS)
    presentations = [a for a in actors if a.get_class() == presentation_class]
    assert len(presentations) == 3
    assert {str(a.get_editor_property("PuzzleId")) for a in presentations} == {"A", "B", "C"}
    assert all(a.get_editor_property("Director") == director for a in presentations)
    assert abs(reveal.get_editor_property("MaximumLockTime") - 8.0) < 1e-5
    for actor in presentations:
        offset = actor.get_editor_property("CameraOffset")
        assert (offset.x, offset.y, offset.z) == (350.0, 350.0, 1200.0)
    if apply:
        for name, value in TIMES.items():
            reveal.set_editor_property(name, value)
        for actor in presentations:
            for name, value in PRESENTATION.items():
                actor.set_editor_property(name, value)
    result = {
        "actors": sorted((a.get_path_name(), a.get_class().get_path_name(),
                          str(a.get_actor_transform())) for a in actors),
        "times": {name: reveal.get_editor_property(name) for name in TIMES},
        "maximum_lock_time": reveal.get_editor_property("MaximumLockTime"),
        "presentation": {str(a.get_editor_property("PuzzleId")): {
            name: a.get_editor_property(name) for name in PRESENTATION
        } for a in presentations},
    }
    if expected is not None:
        assert result["actors"] == expected["actors"], "Actor identity/transform changed"
    if apply or expected is not None:
        for name, value in TIMES.items():
            assert abs(result["times"][name] - value) < 1e-5
        for values in result["presentation"].values():
            for name, value in PRESENTATION.items():
                assert abs(values[name] - value) < 1e-5
    return result


assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), "Stop PIE first"
assert not dirty_packages(), "Preserve existing unsaved work before tuning"
OUT.mkdir(parents=True, exist_ok=False)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
report = {"tuning": {**TIMES, **PRESENTATION}, "maps": {}}
for map_name in ("Stage2", "SoundTest_Stage2"):
    package = "/Game/Maps/" + map_name
    source = ROOT / "Content/Maps" / (map_name + ".umap")
    backup = OUT / (map_name + "-before.umap")
    shutil.copy2(source, backup)
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == before_hash
    assert level.load_level(package)
    before = inspect_map()
    after = inspect_map(before, apply=True)
    assert level.save_current_level()
    gc.collect()
    assert level.load_level("/Game/Maps/MainMenu")
    gc.collect()
    assert level.load_level(package)
    reloaded = inspect_map(before)
    report["maps"][map_name] = {
        "before_hash": before_hash, "after_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
        "before": before, "after": after, "reloaded": reloaded,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    gc.collect()
assert level.load_level("/Game/Maps/MainMenu")
assert not dirty_packages()
print("CALMER_REVEAL_SAVED", str(OUT))
