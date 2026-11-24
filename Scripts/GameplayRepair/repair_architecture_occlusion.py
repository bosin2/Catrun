"""Audit architectural occlusion coverage; opt in to a bounded material repair.

Run with Unreal Python on an already loaded Stage1/Stage2 (or SoundTest mirror)
editor map. Defaults to audit only. The director may pass globals when using exec:
CATRUN_ARCH_OCCLUSION_APPLY=True, CATRUN_ARCH_OCCLUSION_SAVE=True.
No maps are opened, no PIE is started, and no original material is modified.
Apply refuses a dirty target map. Other dirty packages are never saved.
"""

import datetime
import hashlib
import json
import re
import shutil
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
OUT = ROOT / "Saved/GameplayRepair20261112/ArchitectureOcclusion" / STAMP
AS = u.EditorAssetLibrary
EDIT = u.MaterialEditingLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
STAGE1_MAPS = ("/Game/Maps/Stage1", "/Game/Maps/SoundTest_Stage1")
STAGE2_MAPS = ("/Game/Maps/Stage2", "/Game/Maps/SoundTest_Stage2")
MAPS = STAGE1_MAPS + STAGE2_MAPS
FUNCTION = "/Game/Systems/Camera/Occlusion/Materials/MF_WallOcclusion"
DITHER_FUNCTION = "/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA"
DITHER_FILE = Path(u.Paths.convert_relative_path_to_full(u.Paths.engine_content_dir())) / "Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA.uasset"
DEST = "/Game/Environment/Shared/Castle/Architecture/OcclusionRepairs/Run_" + STAMP.replace("-", "_")
APPLY = bool(globals().get("CATRUN_ARCH_OCCLUSION_APPLY", False))
SAVE = bool(globals().get("CATRUN_ARCH_OCCLUSION_SAVE", False))
FADE_OPACITY = .12
MASK_CLIP = .333333
RECIPES = (
    {"key": "GateFrame", "maps": STAGE2_MAPS, "label": r"S2_Gate_\d{2}_Frame",
     "directory": "/Game/Environment/Stage2/Architecture/Doors/RisingGate/Materials/",
     "material": "M_Stage2_RisingGate", "instance": "MI_Stage2_RisingGate"},
    {"key": "Room1Bookshelf", "maps": STAGE2_MAPS, "label": r"S2_Prop_Room1_Bookshelf_0[1-6]",
     "directory": "/Game/Environment/Stage2/Props/Bookshelf_Open/Materials/",
     "material": "M_Stage2_Bookshelf_Open", "instance": "MI_Stage2_Bookshelf_Open"},
    {"key": "Stage1Door", "maps": STAGE1_MAPS, "label": r"S1_Door_.+",
     "directory": "/Game/Environment/Shared/Castle/Architecture/Doors/BedroomDoor/Materials/",
     "material": "M_BedroomDoor", "instance": None},
)
SURFACE_PROPERTIES = (
    "MP_BASE_COLOR", "MP_METALLIC", "MP_SPECULAR", "MP_ROUGHNESS",
    "MP_ANISOTROPY", "MP_EMISSIVE_COLOR", "MP_NORMAL", "MP_TANGENT",
    "MP_WORLD_POSITION_OFFSET", "MP_AMBIENT_OCCLUSION",
)


def path(obj):
    return obj.get_path_name() if obj else None


def package(obj):
    return obj.get_outermost().get_name()


def dirty():
    utility = u.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in (*utility.get_dirty_map_packages(),
                                        *utility.get_dirty_content_packages()))


def load(name):
    obj = AS.load_asset(name)
    assert obj, name
    return obj


def disk_file(name, is_map=False):
    assert name.startswith("/Game/")
    return ROOT / "Content" / (name[len("/Game/"):] + (".umap" if is_map else ".uasset"))


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest() if file.exists() else None


def backup(name, is_map=False):
    file = disk_file(name, is_map)
    assert file.is_file(), str(file)
    target = OUT / "Before" / file.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, target)
    assert digest(file) == digest(target)
    report["backups"].append({"package": name, "file": str(target), "sha256": digest(file)})


def surface(material):
    result = {}
    for name in SURFACE_PROPERTIES:
        prop = getattr(u.MaterialProperty, name)
        node = EDIT.get_material_property_input_node(material, prop)
        result[name] = {"node": node.get_name() if node else None,
                        "output": EDIT.get_material_property_input_node_output_name(material, prop) if node else None}
    return result


def overrides(instance):
    # Export the authored override arrays, including texture references and GUIDs.
    return {name: [item.export_text() for item in instance.get_editor_property(name)] for name in (
        "scalar_parameter_values", "vector_parameter_values", "texture_parameter_values")}


def slot_source(recipe):
    return recipe["directory"] + (recipe["instance"] or recipe["material"])


def source_state(recipe):
    master = load(recipe["directory"] + recipe["material"])
    instance = load(slot_source(recipe)) if recipe["instance"] else None
    return {"recipe": recipe["key"], "master": path(master), "instance": path(instance),
            "slot_source": slot_source(recipe), "parent": path(instance.get_editor_property("parent")) if instance else None,
            "blend_mode": str(master.get_editor_property("blend_mode")),
            "instance_overrides": overrides(instance) if instance else None, "surface": surface(master)}


def actor_state(actor):
    components = []
    for component in actor.get_components_by_class(u.StaticMeshComponent):
        components.append({
            "path": path(component), "mesh": path(component.static_mesh),
            "transform": component.get_world_transform().export_text(),
            "collision_profile": str(component.get_collision_profile_name()),
            "collision_enabled": str(component.get_collision_enabled()),
            "collision_object_type": str(component.get_collision_object_type()),
            "materials": [path(component.get_material(i)) for i in range(component.get_num_materials())],
            "override_materials": [path(material) for material in component.get_editor_property("override_materials")],
        })
    return {"label": actor.get_actor_label(), "path": path(actor),
            "transform": actor.get_actor_transform().export_text(),
            "collision": actor.get_actor_enable_collision(), "components": components}


def expected_assignment_state(before, replacements):
    """Keep every field/slot, changing only explicitly selected material slots."""
    expected = json.loads(json.dumps(before))
    for component in expected["components"]:
        for index, material_path in replacements.get(component["path"], {}).items():
            component["materials"][index] = material_path
            # SetMaterial extends OverrideMaterials with nulls up to this slot.
            raw = component["override_materials"]
            raw.extend([None] * max(0, index + 1 - len(raw)))
            raw[index] = material_path
    return expected


def scan(world, recipes):
    candidates, protected, unexpected = [], [], []
    for actor in u.GameplayStatics.get_all_actors_of_class(world, u.Actor):
        label = actor.get_actor_label()
        recipe = next((r for r in recipes if re.fullmatch(r["label"], label)), None)
        # Record bars and every other source-material user to prove they stay unchanged.
        source_user = any(package(component.get_material(i)) == slot_source(r)
                          for component in actor.get_components_by_class(u.StaticMeshComponent)
                          for i in range(component.get_num_materials()) if component.get_material(i)
                          for r in recipes)
        if recipe is None:
            if source_user or re.fullmatch(r"S2_Gate_\d{2}_Bars", label) or label.startswith("S1_ArrivalStair_"):
                protected.append((actor, actor_state(actor)))
            continue
        slots = [(component, i) for component in actor.get_components_by_class(u.StaticMeshComponent)
                 for i in range(component.get_num_materials()) if component.get_material(i)
                 and package(component.get_material(i)) == slot_source(recipe)]
        if slots:
            candidates.append({"actor": actor, "recipe": recipe, "slots": slots, "before": actor_state(actor)})
        else:
            unexpected.append(actor_state(actor))
    return candidates, protected, unexpected


def make_variant(recipe):
    original = load(recipe["directory"] + recipe["material"])
    original_mi = load(slot_source(recipe)) if recipe["instance"] else None
    if original_mi:
        assert path(original_mi.get_editor_property("parent")) == path(original)
    assert not original.get_editor_property("use_material_attributes"), "Material attributes need a separate adapter"
    assert original.get_editor_property("blend_mode") == u.BlendMode.BLEND_OPAQUE
    master_path = DEST + "/M_" + recipe["key"] + "_MaskedOcclusion"
    instance_path = DEST + "/MI_" + recipe["key"] + "_MaskedOcclusion" if original_mi else None
    assert not AS.does_asset_exist(master_path) and (not instance_path or not AS.does_asset_exist(instance_path))
    master = AS.duplicate_asset(recipe["directory"] + recipe["material"], master_path)
    assert master
    report["created"].append(master_path)
    assert surface(master) == surface(original)
    master.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
    master.set_editor_property("opacity_mask_clip_value", MASK_CLIP)
    call = EDIT.create_material_expression(master, u.MaterialExpressionMaterialFunctionCall, -620, 720)
    assert call.set_material_function(load(FUNCTION)), "Could not bind existing occlusion function"
    opacity = EDIT.create_material_expression(master, u.MaterialExpressionLinearInterpolate, -300, 720)
    opacity.set_editor_property("const_a", 1.)
    opacity.set_editor_property("const_b", FADE_OPACITY)
    assert EDIT.connect_material_expressions(call, "Result", opacity, "Alpha"), "Function output unavailable"
    dither = EDIT.create_material_expression(master, u.MaterialExpressionMaterialFunctionCall, 0, 720)
    assert dither.set_material_function(load(DITHER_FUNCTION)), "Could not bind installed temporal dither function"
    assert EDIT.connect_material_expressions(opacity, "", dither, "Alpha Threshold"), "Dither alpha input unavailable"
    assert EDIT.connect_material_property(dither, "Result", u.MaterialProperty.MP_OPACITY_MASK)
    assert EDIT.get_material_property_input_node(master, u.MaterialProperty.MP_OPACITY_MASK) == dither
    EDIT.recompile_material(master)
    assert surface(master) == surface(original), "Original surface wiring changed"
    instance = None
    if original_mi:
        instance = AS.duplicate_asset(slot_source(recipe), instance_path)
        assert instance
        report["created"].append(instance_path)
        EDIT.set_material_instance_parent(instance, master)
        base = instance.get_editor_property("base_property_overrides")
        base.set_editor_property("override_blend_mode", True)
        base.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
        base.set_editor_property("override_opacity_mask_clip_value", True)
        base.set_editor_property("opacity_mask_clip_value", MASK_CLIP)
        instance.set_editor_property("base_property_overrides", base)
        EDIT.update_material_instance(instance)
        assert overrides(instance) == overrides(original_mi), "Source texture/scalar/vector overrides changed"
    report["variants"].append({"recipe": recipe["key"], "original": path(original),
                               "original_instance": path(original_mi), "master": master_path,
                               "instance": instance_path, "surface": surface(master),
                               "blend_mode": "BLEND_MASKED", "dither_function": DITHER_FUNCTION,
                               "alpha_input": "Alpha Threshold", "mask_output": "Result", "mask_clip": MASK_CLIP})
    return instance if instance else master


def run():
    world = ED.get_editor_world()
    assert world and u.EditorLevelLibrary.get_game_world() is None, "Stop PIE before auditing/authoring editor packages"
    map_path = package(world)
    assert map_path in MAPS, ("This repair only handles confirmed Stage1/Stage2 architecture", map_path)
    recipes = tuple(r for r in RECIPES if map_path in r["maps"])
    report.update(world=map_path, dirty_before=dirty())
    assert DITHER_FILE.is_file(), str(DITHER_FILE)
    report["dither_reference"] = {"asset": path(load(DITHER_FUNCTION)), "file": str(DITHER_FILE), "sha256": digest(DITHER_FILE)}
    candidates, protected, unexpected = scan(world, recipes)
    report["candidates"] = [{"recipe": c["recipe"]["key"], "before": c["before"],
                              "slots": [{"component": path(comp), "index": i} for comp, i in c["slots"]]}
                             for c in candidates]
    report["protected"] = [state for _, state in protected]
    report["unexpected_target_materials"] = unexpected
    report["sources"] = [source_state(r) for r in recipes]
    if not APPLY:
        return
    assert not SAVE or APPLY
    assert map_path not in report["dirty_before"], "Target map is already dirty; preserving existing unsaved work"
    assert not unexpected, "Target labels have unexpected materials; inspect report before applying"
    assert candidates, "No unpatched target slots"
    assert all(package(c["actor"]) == map_path for c in candidates), "Target actor belongs to another map package"
    assert hasattr(u.MaterialExpressionMaterialFunctionCall, "set_material_function"), "Missing function-call authoring API"
    # Source materials/function must be clean so the duplicate matches backed-up bytes.
    source_packages = [FUNCTION] + [r["directory"] + key for r in recipes
                                   for key in (r["material"], r["instance"]) if key]
    assert not set(source_packages).intersection(report["dirty_before"]), "A source material has unsaved edits"
    assert DITHER_FUNCTION not in dirty(), "The shared engine dither function has unsaved edits"
    backup(map_path, True)
    for name in source_packages:
        backup(name)
    source_hashes = {name: digest(disk_file(name)) for name in source_packages}
    original_overrides = {}
    for candidate in candidates:
        for component, _ in candidate["slots"]:
            original_overrides.setdefault(path(component),
                                          (component, list(component.get_editor_property("override_materials"))))
    touched_components = []
    try:
        with u.ScopedEditorTransaction("Restore foreground architecture readability"):
            variants = {r["key"]: make_variant(r) for r in recipes
                        if any(c["recipe"] is r for c in candidates)}
            for candidate in candidates:
                candidate["actor"].modify()
                variant = variants[candidate["recipe"]["key"]]
                replacements = {}
                for component, index in candidate["slots"]:
                    component.modify()
                    component_path = path(component)
                    if component_path not in touched_components:
                        touched_components.append(component_path)
                    component.set_material(index, variant)
                    assert component.get_material(index) == variant, (component_path, index, "Assignment did not take effect")
                    replacements.setdefault(component_path, {})[index] = path(variant)
                after = actor_state(candidate["actor"])
                assert after == expected_assignment_state(candidate["before"], replacements), \
                    "Target material or an unselected slot/geometry/override changed unexpectedly"
                report["after"].append(after)
            assert all(actor_state(actor) == before for actor, before in protected), "An excluded/bar actor changed"
        assert source_hashes == {name: digest(disk_file(name)) for name in source_packages}
        assert digest(DITHER_FILE) == report["dither_reference"]["sha256"], "Engine dither asset changed"
        if SAVE:
            for name in report["created"]:
                assert AS.save_asset(name, only_if_is_dirty=False), name
                report["saved"].append(name)
            assert package(world) == map_path and ED.get_editor_world() == world, "Audited editor world changed"
            # Save only the audited world package; never the editor's current sublevel
            # or its implicit build-data package through SaveCurrentLevel.
            assert u.EditorLoadingAndSavingUtils.save_packages([world.get_outermost()], False), map_path
            report["saved"].append(map_path)
        report["applied"] = True
        report["validation_limit"] = (
            "Bindings and geometry verified; shader compilation and actual gameplay visibility require director validation. "
            "Masked temporal dither avoids translucent triangle sorting, but its clear/restored surface, "
            "shadows, temporal noise/ghosting and occluded coverage still require matched gameplay views before acceptance.")
    except Exception:
        # Restore exact authored arrays, including nulls/length. Effective material
        # restoration with SetMaterial would promote inherited slots to overrides.
        for component_path in reversed(touched_components):
            component, raw = original_overrides[component_path]
            component.set_editor_property("override_materials", raw)
            assert list(component.get_editor_property("override_materials")) == raw, component_path
        report["components_rolled_back"] = len(touched_components)
        raise


def main():
    global report
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"mode": "apply" if APPLY else "audit", "save_requested": SAVE,
              "completed": False, "applied": False, "backups": [], "created": [],
              "saved": [], "variants": [], "after": [], "output": str(OUT)}
    try:
        run()
        report["completed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
        raise
    finally:
        report["dirty_after"] = dirty()
        (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("CATRUN_ARCHITECTURE_OCCLUSION_REPORT", str(OUT / "report.json"))


if not globals().get("CATRUN_ARCH_OCCLUSION_LIBRARY_ONLY", False):
    main()
