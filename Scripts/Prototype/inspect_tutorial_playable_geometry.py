"""Read-only Tutorial diagnosis; execute only under the exclusive editor lease.

Records actual POV, effective settings, door centers, and named collision hits.
Does not relocate actors, change collision/AI/doors, save, start/stop PIE or travel.
"""
import json
from datetime import datetime
from pathlib import Path
import unreal


def vec(p):
    return [p.x, p.y, p.z]


def hit_data(hit):
    if not hit:
        return None
    result = {}
    for key, value in hit.to_dict().items():
        if isinstance(value, unreal.Vector):
            result[key] = vec(value)
        elif isinstance(value, unreal.Object):
            result[key] = value.get_path_name()
        else:
            result[key] = str(value)
    return result


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world() or editor.get_editor_world()
    assert "Tutorial" in world.get_name(), world.get_path_name()
    subjects = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    cat = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not cat:
        cat = next(a for a in subjects if a.get_class().get_name() == "BP_Cat_C")
    shape = cat.get_component_by_class(unreal.CapsuleComponent)
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    manager = next(a for a in subjects if isinstance(a, unreal.SoundGridManager))
    settings = manager.get_editor_property("Settings")
    result = {
        "world": world.get_path_name(), "pie": bool(editor.get_game_world()),
        "cat": vec(cat.get_actor_location()),
        "scope": "Read-only collision/LOS diagnosis; traces are not traversal evidence",
        "settings": {key: settings.get_editor_property(key) for key in (
            "ArmorDetectRadius", "CatSightRadius", "CandleRange", "CandleTotalAngle",
            "CandleConeAngle", "CandleBodyWidth", "CandleSweepSpeed")},
        "actors": [], "legs": [], "los": [],
    }
    if pc and pc.player_camera_manager:
        result["actual_pov"] = {
            "rotation": str(pc.player_camera_manager.get_camera_rotation()),
            "location": vec(pc.player_camera_manager.get_camera_location()),
            "view_target": pc.get_view_target().get_path_name(),
        }
    for actor in subjects:
        if isinstance(actor, (unreal.CatrunArmor, unreal.CatrunCandle, unreal.CatrunDoor)):
            row = {"label": actor.get_actor_label(), "name": actor.get_name(),
                   "location": vec(actor.get_actor_location()), "rotation": str(actor.get_actor_rotation())}
            if isinstance(actor, unreal.CatrunDoor):
                row.update(open=actor.is_open(), gate_center=vec(actor.get_editor_property("GateBox").get_world_location()),
                           leaf_collision=str(actor.get_editor_property("DoorMesh").get_collision_enabled()))
            result["actors"].append(row)
    # Fixed, purpose-specific probes; no random placement loop. Heights are capsule centers.
    legs = [
        ("bedroom-door", (-128, 410, 26.25), (-128, 515, 26.25)),
        ("cat-hole", (-275, 410, 26.25), (-275, 520, 26.25)),
        ("corridor-door", (-360, 662, 26.25), (-170, 662, 26.25)),
        ("annex-north", (-360, 538, 26.25), (-360, 750, 26.25)),
        ("corridor-north", (-170, 730, 26.25), (-170, 1020, 26.25)),
    ]
    for label, start, end in legs:
        hit = unreal.SystemLibrary.capsule_trace_single_by_profile(
            world, unreal.Vector(*start), unreal.Vector(*end),
            shape.get_scaled_capsule_radius(), shape.get_scaled_capsule_half_height(),
            "Pawn", False, [cat], unreal.DrawDebugTrace.NONE, False)
        result["legs"].append({"label": label, "start": start, "end": end, "first_hit": hit_data(hit)})
    # Visibility at the native perception height; a blocked line does not prove all route times safe.
    for label, start, end in [
        ("annex-wait-to-door", (-360,750,100), (-288,662,100)),
        ("annex-wait-to-lure", (-360,750,100), (-288,543,100)),
        ("spawn-to-proposed-candle", (170,-95,102.25), (-15,380,102.25)),
    ]:
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(*start), unreal.Vector(*end), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [cat], unreal.DrawDebugTrace.NONE, False)
        result["los"].append({"label": label, "start": start, "end": end, "first_hit": hit_data(hit)})
    out = Path(unreal.Paths.project_saved_dir()) / "Prototype20261104/TutorialPlayable"
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("geometry-" + datetime.now().strftime("%H%M%S-%f") + ".json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TUTORIAL_GEOMETRY_READ_ONLY", path, json.dumps(result, ensure_ascii=False))


main()
