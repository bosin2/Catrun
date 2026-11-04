"""Read-only observer for final OS-input checks; does not move or trigger actors.

Run only after the asset writer releases the editor. Main owns control.json:
{ "checkpoint": "basket-entry", "shot": 1, "finish": false }.
Replace control.json atomically. Input provenance is recorded separately by main;
a checkpoint is not an input. This observer is not a frame-performance benchmark.
"""
import json
import time
import traceback
from pathlib import Path

import unreal


OUT = Path(unreal.Paths.project_saved_dir()).resolve() / "Prototype20261104/Task5/ManualInputs01"
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / "observations.json").exists(), "Preserve the previous run; choose a fresh folder"
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
STATE = {"started_epoch": time.time(), "started_clock": time.monotonic(),
         "samples": [], "shots": [], "scope": "Read-only PIE observer; actual inputs logged separately"}


def vector(value):
    return [value.x, value.y, value.z]


def actor_name(actor):
    return actor.get_name() if actor else None


def save(final=False, error=None):
    data = {key: value for key, value in STATE.items() if key not in ("handle", "samples")}
    data.update(final=final, error=error, sample_count=len(STATE["samples"]),
                progress_is_tail=not final,
                samples=STATE["samples"] if final else STATE["samples"][-30:])
    (OUT / ("observations.json" if final else "progress.json")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def finish(error=None):
    unreal.unregister_slate_post_tick_callback(STATE["handle"])
    save(final=True, error=error)
    print("FINAL_INTERACTION_OBSERVER_FINISHED", error)


def snapshot(world, checkpoint):
    # All UObject references remain local to this tick, including during travel.
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    cat = unreal.GameplayStatics.get_player_pawn(world, 0)
    row = {"epoch": time.time(), "game_time": unreal.GameplayStatics.get_time_seconds(world),
           "world": world.get_path_name(), "checkpoint": checkpoint}
    if not pc:
        return row
    view = pc.get_view_target()
    row.update(view=actor_name(view), move_ignored=pc.is_move_input_ignored(),
               look_ignored=pc.is_look_input_ignored())
    camera = view.get_component_by_class(unreal.CameraComponent) if view else None
    if camera:
        row["camera"] = {"projection": str(camera.get_editor_property("ProjectionMode")),
                         "ortho_width": camera.get_editor_property("OrthoWidth"),
                         "fov": camera.get_editor_property("FieldOfView")}
    if cat:
        row.update(cat=actor_name(cat), position=vector(cat.get_actor_location()),
                   collision=cat.get_actor_enable_collision())
        mesh = cat.get_component_by_class(unreal.SkeletalMeshComponent)
        if mesh:
            instance = mesh.get_anim_instance()
            row["animation"] = {"mode": str(mesh.get_animation_mode()),
                                "class": instance.get_class().get_name() if instance else None}
            # SingleNode-only getters must never be called on AnimBP instances.
            if isinstance(instance, unreal.AnimSingleNodeInstance):
                asset = instance.get_animation_asset()
                row["animation"].update(asset=asset.get_path_name() if asset else None,
                                         position=mesh.get_position(), rate=mesh.get_play_rate())
        movement = cat.get_component_by_class(unreal.CharacterMovementComponent)
        if movement:
            row["movement"] = str(movement.get_editor_property("MovementMode"))
        actions = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
        if actions:
            basket = actions.get_editor_property("ActiveBasket")
            row["basket"] = {"phase": str(actions.get_editor_property("BasketPhase")),
                             "busy": actions.get_editor_property("Busy"),
                             "hidden": actions.get_editor_property("IsHidden"),
                             "active": actor_name(basket),
                             "can_exit": actions.get_editor_property("CanExit"),
                             "exit_location": vector(actions.get_editor_property("ExitWorldLocation")),
                             "occupied": basket.get_editor_property("Occupied") if basket else None}
    row["armor"] = []
    for armor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunArmor):
        capture = armor.get_editor_property("CapturePresentation")
        row["armor"].append({"name": armor.get_name(), "action": str(armor.get_action()),
                             "position": vector(armor.get_actor_location()),
                             "phase": str(capture.get_editor_property("Phase")),
                             "session": capture.get_editor_property("SessionId")})
    return row


def tick(delta):
    try:
        now = time.monotonic()
        control_path = OUT / "control.json"
        control = json.loads(control_path.read_text(encoding="utf-8-sig")) if control_path.exists() else {}
        if control.get("finish"):
            finish()
            return
        if now - STATE["started_clock"] > 1800:
            finish("Observer timeout; retain samples but do not claim clean completion")
            return
        if now - STATE.get("last_sample", 0) < 0.1:
            return
        STATE["last_sample"] = now
        world = EDITOR.get_game_world()
        if world:
            checkpoint = str(control.get("checkpoint", "unlabelled"))
            STATE["samples"].append(snapshot(world, checkpoint))
            shot_id = int(control.get("shot", 0))
            if shot_id and shot_id not in STATE["shots"]:
                STATE["shots"].append(shot_id)
                name = "".join(c if c.isalnum() or c in "-_" else "_" for c in checkpoint)[:60]
                destination = str(OUT / f"{shot_id:03d}-{name}.png").replace("\\", "/")
                unreal.SystemLibrary.execute_console_command(world, f'Shot showui filename="{destination}"')
        if now - STATE.get("last_save", 0) >= 2:
            STATE["last_save"] = now
            save()
    except Exception:
        finish(traceback.format_exc())


STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
print("FINAL_INTERACTION_OBSERVER_ARMED", str(OUT))
