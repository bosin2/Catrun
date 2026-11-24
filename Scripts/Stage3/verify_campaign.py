"""Exercise real exit overlaps and original stair cinematic in canonical PIE.

API places the cat at checked checkpoints; this is not keyboard traversal.
Never calls CompleteCurrentStage, CompleteTransition, or a sequence Play method.
Run after the asset writer releases the editor. Preserve prior output on reruns.
"""
import json
import time
import traceback
from pathlib import Path

import unreal


OUT = Path(unreal.Paths.project_dir()).resolve() / "Saved/Stage3Integration20261125/Campaign"
OUT.mkdir(parents=True, exist_ok=True)
assert "-SaveToUserDir" in unreal.SystemLibrary.get_command_line()
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not EDITOR.get_game_world()
assert LEVELS.load_level("/Game/Maps/Tutorial")
STATE = {"start": time.monotonic(), "phase": "intro", "events": [], "samples": [],
         "scope": "API checkpoint placement with Pawn-profile clearance; native overlaps/cinematics/travel"}
STATE['renderer']='NullRHI' if '-nullrhi' in unreal.SystemLibrary.get_command_line().lower() else 'D3D11'


def vector(value):
    return [value.x, value.y, value.z]


def event(name, **details):
    STATE["events"].append({"epoch": time.time(), "name": name, **details})


def advance(phase):
    STATE.update(phase=phase, changed=time.monotonic())


def screenshot(world, name):
    filename = str(OUT / (name + ".png")).replace("\\", "/")
    unreal.SystemLibrary.execute_console_command(world, f'Shot showui filename="{filename}"')


def finish(error=None):
    STATE["phase"] = "shutdown"
    STATE["changed"] = time.monotonic()
    data = {key: value for key, value in STATE.items() if key != "handle"}
    data.update(error=error, success=error is None)
    (OUT / "observations.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    LEVELS.editor_request_end_play()
    print("FINAL_EXIT_OVERLAPS_FINISHED", error)


def checkpoint(world, cat, target, label):
    capsule = cat.get_component_by_class(unreal.CapsuleComponent)
    floor = unreal.SystemLibrary.line_trace_single_by_profile(
        world, target, target - unreal.Vector(0, 0, 600),
        "Pawn", False, [cat], unreal.DrawDebugTrace.NONE, False)
    assert floor, (label, "No floor below checkpoint")
    floor_data = floor.to_dict()
    assert floor_data['impact_normal'].z >= .65, (label, "Unwalkable floor")
    # The original staircase landing is 95.9cm below the main tutorial floor.
    # Place onto the measured supporting surface, never float at the main-floor Z.
    target.z = floor_data['impact_point'].z + capsule.get_scaled_capsule_half_height() + 2.25
    hit = unreal.SystemLibrary.capsule_trace_single_by_profile(
        world, target, target + unreal.Vector(0, 0, 0.1),
        capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height(),
        "Pawn", False, [cat], unreal.DrawDebugTrace.NONE, False)
    event("checkpoint-clearance", label=label, target=vector(target),
          blocking_hit=str(hit) if hit else None, floor_point=vector(floor_data['impact_point']))
    assert not hit, (label, "Occupied destination", str(hit))
    cat.set_actor_location(target, False, True)
    event("api-checkpoint-placement", label=label, actual=vector(cat.get_actor_location()))


def actors(world):
    return unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)


def tick(delta):
    try:
        now = time.monotonic()
        if STATE["phase"] == "shutdown":
            if not EDITOR.get_game_world() and now-STATE["changed"]>1:
                unreal.unregister_slate_post_tick_callback(STATE["handle"])
                unreal.SystemLibrary.execute_console_command(EDITOR.get_editor_world(), "QUIT_EDITOR")
            return
        if now - STATE["start"] > 300:
            finish("Timeout in " + STATE["phase"])
            return
        if now - STATE.get("last", 0) < 0.1:
            return
        STATE["last"] = now
        world = EDITOR.get_game_world()
        if not world:
            return
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        cat = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not pc or not cat:
            return
        stage = world.get_name()
        view = pc.get_view_target()
        mesh = cat.get_component_by_class(unreal.SkeletalMeshComponent)
        anim = mesh.get_anim_instance() if mesh else None
        row = {"epoch": time.time(), "world": world.get_path_name(), "phase": STATE["phase"],
               "cat": vector(cat.get_actor_location()), "move_ignored": pc.is_move_input_ignored(),
               "view": view.get_name() if view else None,
               "anim_class": anim.get_class().get_name() if anim else None}
        STATE["samples"].append(row)
        phase = STATE["phase"]
        if phase == "intro" and stage.endswith("Tutorial"):
            intro = next(a for a in actors(world) if a.get_class().get_name() == "BP_TutorialIntro_C")
            player = intro.get_editor_property("IntroPlayer")
            row["intro_playing"] = bool(player and player.is_playing())
            if row["intro_playing"]:
                STATE["saw_intro"] = True
            if now - STATE["start"] > 26 and not row["intro_playing"] and not row["move_ignored"]:
                assert STATE.get("saw_intro"), "Normal tutorial intro was never observed"
                exit_actor = next(a for a in actors(world) if a.get_class().get_name() == "BP_LevelExit_C")
                event("tutorial-playable", exit_waits_for_cinematic=exit_actor.get_editor_property("WaitForCinematic"), **row)
                checkpoint(world, cat, unreal.Vector(-130, 1548, 26.2), "tutorial-stair-overlap")
                advance("stairs")
        elif phase == "stairs":
            if stage.endswith("Stage1"):
                assert STATE.get("saw_stairs"), "Travel bypassed the original stair cinematic"
                event("automatic-stage1-arrival", **row)
                advance("stage1")
            elif stage.endswith("Tutorial"):
                director = next(a for a in actors(world) if a.get_class().get_name() == "BP_StairDescentDirector_C")
                player = director.get_editor_property("SequencePlayer")
                row["stairs_playing"] = bool(player and player.is_playing())
                if row["stairs_playing"]:
                    STATE["saw_stairs"] = True
                    if now - STATE["changed"] > 2 and not STATE.get("stairs_shot"):
                        STATE["stairs_shot"] = True
                        screenshot(world, "tutorial-stair-cinematic")
        elif phase == "stage1" and now - STATE["changed"] > 5:
            assert stage.endswith("Stage1") and not row["move_ignored"], row
            exit_actor = next(a for a in actors(world) if isinstance(a, unreal.CatrunStageExit))
            target = exit_actor.get_editor_property("Trigger").get_world_location()
            target.z = cat.get_actor_location().z
            event("stage1-playable", exit_actor=exit_actor.get_name(), **row)
            checkpoint(world, cat, target, "stage1-native-exit-overlap")
            advance("wait-stage2")
        elif phase == "wait-stage2" and stage.endswith("Stage2"):
            event("automatic-stage2-arrival", **row)
            advance("stage2")
        elif phase == "stage2" and now - STATE["changed"] > 5:
            assert stage.endswith("Stage2"), row
            if row['move_ignored']:
                STATE['saw_stage2_arrival_presentation']=True
                return
            exit_actor = next(a for a in actors(world) if isinstance(a, unreal.CatrunStageExit))
            target = exit_actor.get_editor_property("Trigger").get_world_location()
            target.z = cat.get_actor_location().z
            event("stage2-playable", exit_actor=exit_actor.get_name(), **row)
            checkpoint(world, cat, target, "stage2-completion-overlap")
            advance("complete")
        elif phase == "complete" and stage.endswith("Stage3") and now - STATE["changed"] > 3:
            assert stage.endswith("Stage3"), "Stage2 must travel into Stage3"
            flow = next(s for s in unreal.ObjectIterator(unreal.CatrunLevelFlowSubsystem) if s.get_world() == world)
            assert not flow.get_editor_property("bStageComplete"), "Stage3 should be playable"
            assert not pc.is_move_input_ignored(), "Stage3 control not restored"
            assert flow.get_stage_clock_state().get_editor_property("RemainingSeconds") > 1100, "Fresh Stage3 clock missing"
            event("native-stage1-to-stage2-to-stage3-confirmed", **row)
            screenshot(world, "stage3-arrival")
            advance("finish")
        elif phase == "finish" and now - STATE["changed"] > 1:
            assert stage.endswith("Stage3"), "Late unexpected travel"
            finish()
    except Exception:
        finish(traceback.format_exc())


STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
LEVELS.editor_request_begin_play()
print("FINAL_EXIT_OVERLAPS_ARMED")
