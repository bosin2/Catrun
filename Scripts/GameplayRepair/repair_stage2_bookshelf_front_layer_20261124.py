"""Apply or verify the Stage2 shelf-only nearest-depth alpha fade.

Run on an already loaded Stage2/SoundTest_Stage2 editor world outside PIE.
CATRUN_BOOKSHELF_FRONT_LAYER_MODE is audit (default), apply, or cold.
The fully clear shelf keeps its depth-writing lighting pass. Intermediate
opacity uses nearest-depth alpha. Previous trial materials are accepted as
migration inputs and are never selected as outputs.
"""

import importlib.util
import json
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
MODE = globals().get("CATRUN_BOOKSHELF_FRONT_LAYER_MODE", "audit")
SPEC = importlib.util.spec_from_file_location(
    "catrun_bookshelf_fade", ROOT / "Scripts/GameplayRepair/repair_stage2_bookshelf_fade_20261124.py"
)
shelves = importlib.util.module_from_spec(SPEC)
shelves.CATRUN_BOOKSHELF_FADE_LIBRARY_ONLY = True
SPEC.loader.exec_module(shelves)
repair, AS, EDIT = shelves.repair, shelves.AS, shelves.EDIT

DEST = shelves.REPAIRS + "/BookshelfWallFade/"
MASTER = DEST + "M_Room1Bookshelf_WallFade_FrontLayerHandoff"
INSTANCE = DEST + "MI_Room1Bookshelf_WallFade_FrontLayerHandoff"
TRIAL_LAYER_MASTER = DEST + "M_Room1Bookshelf_WallFade_FrontLayer"
TRIAL_LAYER_MI = DEST + "MI_Room1Bookshelf_WallFade_FrontLayer"
CLEAR_MASTER = DEST + "M_Room1Bookshelf_WallFade_Clear"
CLEAR_INSTANCE = DEST + "MI_Room1Bookshelf_WallFade_Clear"
ACCEPTED = (shelves.ORIGINAL_MI, shelves.MASKED_MI, shelves.TRIAL_MI, shelves.VARIANT_MI, TRIAL_LAYER_MI, CLEAR_INSTANCE)
PROXY_TAG = "CatrunShelfDepthProxy20261124"
PROXY_PREFIX = "S2_Render_ShelfDepth_"
LAYER_TAG = "CatrunShelfTranslucentLayer20261124"
LAYER_PREFIX = "S2_Render_ShelfFade_"
DEPTH_BIAS_CM = 0.25
CLEAR_THRESHOLD = 0.9999
DEPTH_CODE = (
    f"if (SurfaceOpacity >= {CLEAR_THRESHOLD}f) return 0.0f;\n"
    f"return MeshDepth <= DepthSample.r + {DEPTH_BIAS_CM}f ? SurfaceOpacity : 0.0f;"
)
CLEAR_CODE = f"return SurfaceOpacity >= {CLEAR_THRESHOLD}f ? 1.0f : 0.0f;"
PROXY_FLAGS = {
    "render_in_main_pass": False,
    "render_in_depth_pass": False,
    "render_custom_depth": True,
    "cast_shadow": False,
    "affect_dynamic_indirect_lighting": False,
    "affect_distance_field_lighting": False,
    "visible_in_ray_tracing": False,
    "visible_in_reflection_captures": False,
    "visible_in_real_time_sky_captures": False,
    "hidden_in_scene_capture": False,
    "use_as_occluder": False,
    "can_ever_affect_navigation": False,
    "generate_overlap_events": False,
}
LAYER_FLAGS = dict(PROXY_FLAGS, render_in_main_pass=True, render_custom_depth=False)
REQUIRED_SOURCES = (shelves.ORIGINAL, shelves.ORIGINAL_MI, shelves.MESH, shelves.WALL, shelves.WALL_MI, repair.FUNCTION)
OPTIONAL_SOURCES = (shelves.MASKED, shelves.MASKED_MI, DEST + "M_Room1Bookshelf_WallFade",
                    shelves.TRIAL_MI, shelves.VARIANT, shelves.VARIANT_MI, TRIAL_LAYER_MASTER, TRIAL_LAYER_MI)


def shelf_component(actor):
    component, = actor.get_components_by_class(u.StaticMeshComponent)
    mesh = component.static_mesh
    assert mesh and repair.package(mesh) == shelves.MESH and component.get_num_materials() == 1, repair.path(actor)
    return component


def validate_instance(instance, master, original_mi, blend_mode, settings):
    assert instance.get_editor_property("parent") == master and shelves.effective_blend(instance) == blend_mode
    expected_base = original_mi.get_editor_property("base_property_overrides").copy()
    expected_base.set_editor_property("blend_mode", blend_mode)
    assert instance.get_editor_property("base_property_overrides").export_text() == expected_base.export_text()
    assert repair.overrides(instance) == repair.overrides(original_mi), "Original shelf texture or constants changed"
    assert shelves.fade_settings(instance) == settings, "Wall function settings changed"


def validate_variant(master, instance, original, original_mi, wall, function, endpoints, settings):
    assert master.get_editor_property("blend_mode") == shelves.TRANSLUCENT
    assert master.get_editor_property("translucency_pass") == u.MaterialTranslucencyPass.MTP_BEFORE_DOF
    for prop, source in (("two_sided", original), ("translucency_lighting_mode", wall)):
        assert master.get_editor_property(prop) == source.get_editor_property(prop), prop
    assert repair.surface(master) == repair.surface(original), "Original shelf surface outputs changed"
    gate = EDIT.get_material_property_input_node(master, u.MaterialProperty.MP_OPACITY)
    assert isinstance(gate, u.MaterialExpressionCustom) and gate.get_editor_property("code") == DEPTH_CODE
    lerp, custom_depth, pixel_depth = EDIT.get_inputs_for_material_expression(master, gate)
    assert shelves.fade_graph(master, function, lerp) == endpoints, "Original wall opacity curve changed"
    assert isinstance(pixel_depth, u.MaterialExpressionPixelDepth)
    assert isinstance(custom_depth, u.MaterialExpressionSceneTexture)
    assert custom_depth.get_editor_property("scene_texture_id") == u.SceneTextureId.PPI_CUSTOM_DEPTH
    assert not custom_depth.get_editor_property("filtered")
    validate_instance(instance, master, original_mi, shelves.TRANSLUCENT, settings)


def validate_clear(master, instance, original, original_mi, function, endpoints, settings):
    assert master.get_editor_property("blend_mode") == u.BlendMode.BLEND_MASKED
    assert not master.get_editor_property("dither_opacity_mask")
    assert master.get_editor_property("two_sided") == original.get_editor_property("two_sided")
    assert repair.surface(master) == repair.surface(original), "Original shelf surface outputs changed"
    gate = EDIT.get_material_property_input_node(master, u.MaterialProperty.MP_OPACITY_MASK)
    assert isinstance(gate, u.MaterialExpressionCustom) and gate.get_editor_property("code") == CLEAR_CODE
    lerp, = EDIT.get_inputs_for_material_expression(master, gate)
    assert shelves.fade_graph(master, function, lerp) == endpoints
    validate_instance(instance, master, original_mi, u.BlendMode.BLEND_MASKED, settings)


def make_wall_opacity(master, function, endpoints):
    call = EDIT.create_material_expression(master, u.MaterialExpressionMaterialFunctionCall, -620, 720)
    assert call.set_material_function(function)
    lerp = EDIT.create_material_expression(master, u.MaterialExpressionLinearInterpolate, -300, 720)
    lerp.set_editor_property("const_a", endpoints[0])
    lerp.set_editor_property("const_b", endpoints[1])
    assert EDIT.connect_material_expressions(call, "Result", lerp, "Alpha")
    return lerp


def make_gate(master, description, code, bindings, output):
    gate = EDIT.create_material_expression(master, u.MaterialExpressionCustom, 0, 760)
    gate.set_editor_property("description", description)
    gate.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT1)
    gate.set_editor_property("code", code)
    inputs = []
    for name, _, _ in bindings:
        entry = u.CustomInput()
        entry.set_editor_property("input_name", name)
        inputs.append(entry)
    gate.set_editor_property("inputs", inputs)
    for name, node, node_output in bindings:
        assert EDIT.connect_material_expressions(node, node_output, gate, name)
    assert EDIT.connect_material_property(gate, "", output)


def make_instance(path, master, report):
    if AS.does_asset_exist(path):
        return repair.load(path)
    instance = AS.duplicate_asset(shelves.ORIGINAL_MI, path)
    assert instance
    report["created"].append(path)
    EDIT.set_material_instance_parent(instance, master)
    EDIT.update_material_instance(instance)
    return instance


def make_variant(original, original_mi, wall, function, endpoints, settings, report):
    if AS.does_asset_exist(MASTER):
        master = repair.load(MASTER)
    else:
        master = AS.duplicate_asset(shelves.ORIGINAL, MASTER)
        assert master
        report["created"].append(MASTER)
        master.set_editor_property("blend_mode", shelves.TRANSLUCENT)
        master.set_editor_property("translucency_lighting_mode", wall.get_editor_property("translucency_lighting_mode"))
        master.set_editor_property("translucency_pass", u.MaterialTranslucencyPass.MTP_BEFORE_DOF)
        lerp = make_wall_opacity(master, function, endpoints)
        custom_depth = EDIT.create_material_expression(master, u.MaterialExpressionSceneTexture, -300, 900)
        custom_depth.set_editor_property("scene_texture_id", u.SceneTextureId.PPI_CUSTOM_DEPTH)
        pixel_depth = EDIT.create_material_expression(master, u.MaterialExpressionPixelDepth, -300, 1080)
        make_gate(master, "Blend only the closest shelf surface", DEPTH_CODE, (
            ("SurfaceOpacity", lerp, ""), ("DepthSample", custom_depth, "Color"), ("MeshDepth", pixel_depth, ""),
        ), u.MaterialProperty.MP_OPACITY)
        EDIT.recompile_material(master)

    instance = make_instance(INSTANCE, master, report)
    validate_variant(master, instance, original, original_mi, wall, function, endpoints, settings)
    return instance


def make_clear(original, original_mi, function, endpoints, settings, report):
    if AS.does_asset_exist(CLEAR_MASTER):
        master = repair.load(CLEAR_MASTER)
    else:
        master = AS.duplicate_asset(shelves.ORIGINAL, CLEAR_MASTER)
        assert master
        report["created"].append(CLEAR_MASTER)
        master.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
        master.set_editor_property("dither_opacity_mask", False)
        lerp = make_wall_opacity(master, function, endpoints)
        make_gate(master, "Restore opaque lighting at the clear end of the fade", CLEAR_CODE, (
            ("SurfaceOpacity", lerp, ""),
        ), u.MaterialProperty.MP_OPACITY_MASK)
        EDIT.recompile_material(master)
    instance = make_instance(CLEAR_INSTANCE, master, report)
    validate_clear(master, instance, original, original_mi, function, endpoints, settings)
    return instance


def replica_label(actor, prefix):
    return prefix + actor.get_actor_label().rsplit("_", 1)[1]


def validate_replica(replica, actor, mesh, material, tag, expected_flags):
    component = shelf_component(replica)
    assert [str(actual) for actual in replica.tags] == [tag], repair.path(replica)
    assert not replica.get_actor_enable_collision(), repair.path(replica)
    assert not replica.get_editor_property("enable_auto_lod_generation"), repair.path(replica)
    assert replica.get_attach_parent_actor() == actor and repair.package(replica) == repair.package(actor), repair.path(replica)
    assert component.get_world_transform().export_text() == shelf_component(actor).get_world_transform().export_text()
    assert component.static_mesh == mesh and component.get_material(0) == material
    assert component.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION
    assert str(component.get_collision_profile_name()) == "NoCollision"
    flags = {name: component.get_editor_property(name) for name in expected_flags}
    assert flags == expected_flags, flags
    return {"path": repair.path(replica), "label": replica.get_actor_label(), "attached_to": repair.path(actor), "flags": flags}


def spawn_replica(actor_subsystem, actor, component, material, prefix, tag, flags, spawned):
    proxy = actor_subsystem.spawn_actor_from_class(u.StaticMeshActor, actor.get_actor_location(), actor.get_actor_rotation())
    assert proxy, repair.path(actor)
    spawned.append(proxy)
    proxy.set_actor_label(replica_label(actor, prefix))
    proxy.set_editor_property("tags", [tag])
    proxy.set_editor_property("enable_auto_lod_generation", False)
    proxy.set_actor_enable_collision(False)
    depth_component = proxy.static_mesh_component
    for name, enabled in flags.items():
        depth_component.set_editor_property(name, enabled)
    depth_component.set_collision_profile_name("NoCollision")
    assert depth_component.set_static_mesh(component.static_mesh)
    depth_component.set_material(0, material)
    proxy.set_actor_transform(component.get_world_transform(), False, True)
    keep = u.AttachmentRule.KEEP_WORLD
    assert proxy.attach_to_actor(actor, "None", keep, keep, keep, False)
    return proxy


def run(world, report):
    assert MODE in ("audit", "apply", "cold"), MODE
    assert world and repair.ED.get_game_world() is None, "Stop PIE first"
    map_path = repair.package(world)
    assert map_path in repair.STAGE2_MAPS, map_path
    report.update(map=map_path, dirty_before=repair.dirty(), depth_bias_cm=DEPTH_BIAS_CM,
                  clear_handoff_threshold=CLEAR_THRESHOLD)
    report["custom_depth_mode"] = u.SystemLibrary.get_console_variable_int_value("r.CustomDepth")
    assert report["custom_depth_mode"] in (1, 2, 3), "CustomDepth pass is disabled"
    original, original_mi, wall, wall_mi, function = map(repair.load, (
        shelves.ORIGINAL, shelves.ORIGINAL_MI, shelves.WALL, shelves.WALL_MI, repair.FUNCTION,
    ))
    assert original_mi.get_editor_property("parent") == original
    assert shelves.effective_blend(original_mi) == u.BlendMode.BLEND_OPAQUE
    assert not original.get_editor_property("use_material_attributes")
    assert wall_mi.get_base_material() == wall and shelves.effective_blend(wall_mi) == shelves.TRANSLUCENT
    wall_lerp = EDIT.get_material_property_input_node(wall, u.MaterialProperty.MP_OPACITY)
    endpoints = shelves.fade_graph(wall, function, wall_lerp)
    settings = shelves.fade_settings(wall_mi)
    report.update(opacity_range=endpoints, fade_settings=settings)
    assert endpoints[0] == 1.0 and endpoints[1] is not None and abs(endpoints[1] - 0.12) < 1e-6, endpoints

    actor_subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    targets = sorted((actor for actor in actors if actor.get_actor_label() in shelves.LABELS), key=lambda a: a.get_actor_label())
    assert len(targets) == len(shelves.LABELS) and {actor.get_actor_label() for actor in targets} == shelves.LABELS
    proxy_labels = {replica_label(actor, PROXY_PREFIX) for actor in targets}
    layer_labels = {replica_label(actor, LAYER_PREFIX) for actor in targets}
    replicas = {}
    report["other_custom_depth_writers"] = []
    for actor in actors:
        label = actor.get_actor_label()
        if label in proxy_labels or actor.actor_has_tag(PROXY_TAG):
            assert label in proxy_labels and label not in replicas and actor.actor_has_tag(PROXY_TAG), label
            replicas[label] = actor
        elif label in layer_labels or actor.actor_has_tag(LAYER_TAG):
            assert label in layer_labels and label not in replicas and actor.actor_has_tag(LAYER_TAG), label
            replicas[label] = actor
        else:
            report["other_custom_depth_writers"].extend(
                repair.path(component) for component in actor.get_components_by_class(u.PrimitiveComponent)
                if component.get_editor_property("render_custom_depth")
            )

    changes = []
    variant_exists = AS.does_asset_exist(INSTANCE)
    instance = repair.load(INSTANCE) if variant_exists else None
    if variant_exists:
        validate_variant(repair.load(MASTER), instance, original, original_mi, wall, function, endpoints, settings)
    clear_exists = AS.does_asset_exist(CLEAR_INSTANCE)
    if clear_exists:
        validate_clear(repair.load(CLEAR_MASTER), repair.load(CLEAR_INSTANCE), original, original_mi,
                       function, endpoints, settings)
    for actor in targets:
        assert repair.package(actor) == map_path, repair.path(actor)
        component = shelf_component(actor)
        assert not component.get_editor_property("render_custom_depth"), repair.path(component)
        before = shelves.actor_state(actor)
        report["before"].append(before)
        source = repair.package(component.get_material(0))
        proxy = replicas.get(replica_label(actor, PROXY_PREFIX))
        layer = replicas.get(replica_label(actor, LAYER_PREFIX))
        assert source in ACCEPTED, before
        old_hidden_flag = False
        if proxy:
            old_hidden_flag = proxy.static_mesh_component.get_editor_property("hidden_in_scene_capture")
            report["proxies"].append(validate_replica(proxy, actor, component.static_mesh, original_mi,
                                                       PROXY_TAG, dict(PROXY_FLAGS, hidden_in_scene_capture=old_hidden_flag)))
        if layer:
            assert instance
            report["translucent_layers"].append(validate_replica(layer, actor, component.static_mesh, instance,
                                                                   LAYER_TAG, LAYER_FLAGS))
        if source != CLEAR_INSTANCE or not proxy or not layer or old_hidden_flag:
            changes.append((actor, component, before, source, proxy, layer, old_hidden_flag))

    report["requires_update"] = [before["label"] for _, _, before, _, _, _, _ in changes]
    if MODE == "cold":
        assert not changes and variant_exists and clear_exists, report["requires_update"]
    if MODE != "apply" or not changes:
        report["after"] = report["before"]
        return

    protected = REQUIRED_SOURCES + tuple(name for name in OPTIONAL_SOURCES if repair.disk_file(name).is_file())
    destinations = (MASTER, INSTANCE, CLEAR_MASTER, CLEAR_INSTANCE)
    assert not set(protected + (map_path,) + destinations).intersection(report["dirty_before"])
    report["source_hashes"] = {name: repair.digest(repair.disk_file(name)) for name in protected}
    assert all(report["source_hashes"][name] for name in REQUIRED_SOURCES), "A required original package is missing"
    repair.backup(map_path, True)
    for name in destinations:
        if repair.disk_file(name).exists():
            repair.backup(name)
    rollback, spawned, migrated_proxies = [], [], []
    try:
        with u.ScopedEditorTransaction("Use nearest-depth wall fade for Stage2 shelves"):
            instance = make_variant(original, original_mi, wall, function, endpoints, settings, report)
            actor_material = make_clear(original, original_mi, function, endpoints, settings, report)
            for actor, component, before, source, proxy, layer, old_hidden_flag in changes:
                previous = before["components"][0]
                if not proxy:
                    proxy = spawn_replica(actor_subsystem, actor, component, original_mi, PROXY_PREFIX,
                                          PROXY_TAG, PROXY_FLAGS, spawned)
                    replicas[replica_label(actor, PROXY_PREFIX)] = proxy
                elif old_hidden_flag:
                    depth_component = proxy.static_mesh_component
                    proxy.modify()
                    depth_component.modify()
                    migrated_proxies.append(depth_component)
                    depth_component.set_editor_property("hidden_in_scene_capture", False)
                if not layer:
                    layer = spawn_replica(actor_subsystem, actor, component, instance, LAYER_PREFIX,
                                          LAYER_TAG, LAYER_FLAGS, spawned)
                    replicas[replica_label(actor, LAYER_PREFIX)] = layer
                actor.modify()
                component.modify()
                rollback.append((component, list(component.get_editor_property("override_materials")), previous["sort_triangles"]))
                component.set_material(0, actor_material)
                expected = repair.expected_assignment_state(before, {previous["path"]: {0: repair.path(actor_material)}})
                if source == shelves.TRIAL_MI and previous["sort_triangles"]:
                    component.set_editor_property("sort_triangles", False)
                    expected["components"][0]["sort_triangles"] = False
                assert shelves.actor_state(actor) == expected, repair.path(actor)
            report["proxies"] = [validate_replica(
                replicas[replica_label(actor, PROXY_PREFIX)], actor, shelf_component(actor).static_mesh,
                original_mi, PROXY_TAG, PROXY_FLAGS,
            ) for actor in targets]
            report["translucent_layers"] = [validate_replica(
                replicas[replica_label(actor, LAYER_PREFIX)], actor, shelf_component(actor).static_mesh,
                instance, LAYER_TAG, LAYER_FLAGS,
            ) for actor in targets]
        for name in report["created"]:
            assert AS.save_asset(name, only_if_is_dirty=False), name
            report["saved"].append(name)
        assert repair.ED.get_editor_world() == world
        assert u.EditorLoadingAndSavingUtils.save_packages([world.get_outermost()], False), map_path
        report["saved"].append(map_path)
    except Exception:
        for component, materials, sort in reversed(rollback):
            component.set_editor_property("override_materials", materials)
            if component.get_editor_property("sort_triangles") != sort:
                component.set_editor_property("sort_triangles", sort)
        for component in migrated_proxies:
            component.set_editor_property("hidden_in_scene_capture", True)
        for proxy in reversed(spawned):
            actor_subsystem.destroy_actor(proxy)
        raise
    assert report["source_hashes"] == {name: repair.digest(repair.disk_file(name)) for name in protected}
    report["after"] = [shelves.actor_state(actor) for actor in targets]


def main():
    world = repair.ED.get_editor_world()
    name = world.get_name() if world else "NoWorld"
    repair.OUT = ROOT / "Saved/VisualRepair20261124/BookshelfFrontLayer" / f"{name}-{MODE}-{repair.STAMP}"
    repair.OUT.mkdir(parents=True, exist_ok=True)
    report = {"mode": MODE, "completed": False, "before": [], "after": [], "backups": [],
              "created": [], "saved": [], "proxies": [], "translucent_layers": []}
    repair.report = report
    try:
        run(world, report)
        report["completed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
        raise
    finally:
        report["dirty_after"] = repair.dirty()
        output = repair.OUT / "report.json"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("CAT_AUDIO_REPORT:" + json.dumps({"completed": report["completed"], "report": str(output)}))


main()
