"""Repair the confirmed foreground door without changing its source or collision.

Run on an already loaded Stage1/SoundTest_Stage1. Defaults to read-only audit;
set CATRUN_DOOR_OCCLUSION_MODE='apply' or 'cold'. Load each map in a separate
MCP call. Apply uses the shipped masked material. Edits to that material need
review before its saved package fingerprint can be approved for this migration.
"""
import importlib.util
import json
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
MODE = globals().get("CATRUN_DOOR_OCCLUSION_MODE", "audit")
EXPECTED_MESH = ("/Game/Environment/Shared/Castle/Architecture/Doors/BedroomDoor/"
                 "Meshes/SM_BedroomDoorLeaf_A.SM_BedroomDoorLeaf_A")
VARIANT_PATH = ("/Game/Environment/Shared/Castle/Architecture/OcclusionRepairs/"
                "Stage1Door/M_Stage1Door_MaskedOcclusion")
APPROVED_VARIANT_SHA256 = "f60ab873912f4b14dc5150c6aebf146853565e1273b4225c97909913336f0861"


def object_path(package_path):
    return package_path + "." + package_path.rsplit("/", 1)[1]


def material_state(actor_state, source_path):
    components = actor_state["components"]
    assert len(components) == 1, ("Expected one door StaticMeshComponent", actor_state["path"], len(components))
    component = components[0]
    assert component["mesh"] == EXPECTED_MESH, ("Unexpected door mesh", component["mesh"])
    materials = component["materials"]
    if materials == [object_path(source_path)] * 4:
        return "original"
    if materials == [object_path(VARIANT_PATH)] * 4 and component["override_materials"][:4] == materials:
        return "approved_overrides"
    raise AssertionError(("Expected all four original materials or all four approved overrides", component))


assert MODE in ("audit", "apply", "cold")
spec = importlib.util.spec_from_file_location("catrun_architecture_occlusion",
    ROOT / "Scripts/GameplayRepair/repair_architecture_occlusion.py")
repair = importlib.util.module_from_spec(spec)
repair.CATRUN_ARCH_OCCLUSION_LIBRARY_ONLY = True
spec.loader.exec_module(repair)
world = repair.ED.get_editor_world()
assert world and repair.ED.get_game_world() is None, "Stop PIE first"
map_path = repair.package(world)
assert map_path in repair.STAGE1_MAPS, map_path
assert not repair.dirty(), "Preserve existing unsaved work"
repair.OUT = ROOT / "Saved/PlayFix20261123/Visual" / (map_path.rsplit("/", 1)[1] + "-" + MODE + "-" + repair.STAMP)
recipe = dict(next(r for r in repair.RECIPES if r["key"] == "Stage1Door"))
recipe["label"] = "S1_Door_LowerHall_East_Open"
repair.RECIPES = (recipe,)
source_path = repair.slot_source(recipe)
original_hash = repair.digest(repair.disk_file(source_path))
actors = [a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
          if a.get_actor_label() == recipe["label"]]
assert len(actors) == 1, (map_path, len(actors))
door = actors[0]
assert repair.package(door) == map_path, ("Door belongs to another package", repair.package(door))
before = repair.actor_state(door)
before_state = material_state(before, source_path)
map_file = repair.disk_file(map_path, is_map=True)
map_hash_before = repair.digest(map_file)
variant_file = repair.disk_file(VARIANT_PATH)
variant_hash = repair.digest(variant_file)


def checked_variant():
    # The reviewed saved package covers the full occlusion mask graph, including every connection.
    assert variant_hash == APPROVED_VARIANT_SHA256, ("Approved door material package required", variant_hash)
    variant = repair.load(VARIANT_PATH)
    assert repair.path(variant) == object_path(VARIANT_PATH), ("Unexpected loaded door material", repair.path(variant))
    original = repair.load(source_path)
    assert repair.surface(variant) == repair.surface(original), "Original surface wiring changed"
    return variant


if MODE == "cold":
    assert before_state == "approved_overrides", (map_path, "Door migration has not been applied")

variant = checked_variant() if MODE == "apply" or before_state == "approved_overrides" else None
assigned = MODE == "apply" and before_state == "original"
if assigned:
    repair.make_variant = lambda _: variant
    repair.APPLY = repair.SAVE = True
    repair.main()
elif MODE == "audit" and before_state == "original":
    repair.main()

after = repair.actor_state(door)
after_state = material_state(after, source_path)
map_hash_after = repair.digest(map_file)
if assigned:
    assert after_state == "approved_overrides"
    replacements = {before["components"][0]["path"]: {i: repair.path(variant) for i in range(4)}}
    assert after == repair.expected_assignment_state(before, replacements)
else:
    assert after == before and map_hash_after == map_hash_before, "Verification changed the map"
assert variant_hash == repair.digest(variant_file), "Approved material package modified"
assert original_hash == repair.digest(repair.disk_file(source_path)), "Source material modified"
assert not repair.dirty(), repair.dirty()
repair.OUT.mkdir(parents=True, exist_ok=True)
report = {"map": map_path, "mode": MODE, "source_sha256": original_hash,
          "variant": VARIANT_PATH, "variant_sha256": variant_hash,
          "map_sha256_before": map_hash_before, "map_sha256_after": map_hash_after,
          "before_state": before_state, "after_state": after_state, "assigned": assigned,
          "before": before, "after": after, "complete": True, "dirty": repair.dirty()}
(repair.OUT / "door.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print("CAT_AUDIO_REPORT:" + json.dumps({"complete": True, "map": map_path, "mode": MODE,
                                      "report": str(repair.OUT / "door.json")}))
