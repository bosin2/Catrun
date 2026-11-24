"""Shared inspection for the final Stage2 bookshelf fade migration."""

import importlib.util
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
SPEC = importlib.util.spec_from_file_location(
    "catrun_architecture_occlusion", ROOT / "Scripts/GameplayRepair/repair_architecture_occlusion.py"
)
repair = importlib.util.module_from_spec(SPEC)
repair.CATRUN_ARCH_OCCLUSION_LIBRARY_ONLY = True
SPEC.loader.exec_module(repair)
AS, EDIT = repair.AS, repair.EDIT

RECIPE = next(recipe for recipe in repair.RECIPES if recipe["key"] == "Room1Bookshelf")
ORIGINAL = RECIPE["directory"] + RECIPE["material"]
ORIGINAL_MI = repair.slot_source(RECIPE)
MESH = ORIGINAL.rsplit("/Materials/", 1)[0] + "/Meshes/SM_Stage2_Bookshelf_Open"
WALL = "/Game/Environment/Stage2/Architecture/Walls/Materials/M_Stage2_Walls_Occlusion"
WALL_MI = "/Game/Environment/Stage2/Architecture/Layout/Materials/MI_Stage2_LayoutWalls"
REPAIRS = "/Game/Environment/Shared/Castle/Architecture/OcclusionRepairs"
MASKED = REPAIRS + "/Run_20261112_225554_243970/M_Room1Bookshelf_MaskedOcclusion"
MASKED_MI = REPAIRS + "/Run_20261112_225554_243970/MI_Room1Bookshelf_MaskedOcclusion"
TRIAL_MI = REPAIRS + "/BookshelfWallFade/MI_Room1Bookshelf_WallFade"
VARIANT = REPAIRS + "/BookshelfWallFade/M_Room1Bookshelf_WallFade_BlueNoise"
VARIANT_MI = REPAIRS + "/BookshelfWallFade/MI_Room1Bookshelf_WallFade_BlueNoise"
LABELS = {f"S2_Prop_Room1_Bookshelf_{number:02}" for number in range(1, 7)}
TRANSLUCENT = u.BlendMode.BLEND_TRANSLUCENT


def effective_blend(instance):
    overrides = instance.get_editor_property("base_property_overrides")
    if overrides.get_editor_property("override_blend_mode"):
        return overrides.get_editor_property("blend_mode")
    return instance.get_base_material().get_editor_property("blend_mode")


def fade_settings(instance):
    result = {"UseObjectBounds": EDIT.get_material_instance_scalar_parameter_value(instance, "UseObjectBounds")}
    for name in ("WallPlane", "WallFadeSettings"):
        value = EDIT.get_material_instance_vector_parameter_value(instance, name)
        result[name] = [value.r, value.g, value.b, value.a]
    return result


def fade_graph(master, function, lerp):
    assert isinstance(lerp, u.MaterialExpressionLinearInterpolate), repair.path(master)
    a, b, alpha = EDIT.get_inputs_for_material_expression(master, lerp)
    assert isinstance(alpha, u.MaterialExpressionMaterialFunctionCall), repair.path(lerp)
    assert alpha.get_editor_property("material_function") == function, repair.path(alpha)
    assert EDIT.get_input_node_output_name_for_material_expression(lerp, alpha) == "Result", repair.path(alpha)
    assert not any(EDIT.get_inputs_for_material_expression(master, alpha)), "Fade function inputs are customized"
    return tuple(
        node.get_editor_property("r") if isinstance(node, u.MaterialExpressionConstant)
        else lerp.get_editor_property(prop) if node is None
        else None
        for node, prop in ((a, "const_a"), (b, "const_b"))
    )


def actor_state(actor):
    state = repair.actor_state(actor)
    state["tags"] = [str(tag) for tag in actor.tags]
    for component, entry in zip(actor.get_components_by_class(u.StaticMeshComponent), state["components"]):
        for name in ("disallow_nanite", "sort_triangles"):
            entry[name] = component.get_editor_property(name)
        entry["tags"] = [str(tag) for tag in component.component_tags]
    return state


if not globals().get("CATRUN_BOOKSHELF_FADE_LIBRARY_ONLY", False):
    raise RuntimeError("Use repair_stage2_bookshelf_front_layer_20261124.py for the final Stage2 bookshelf fade")
