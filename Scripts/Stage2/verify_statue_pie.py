"""Run with -ExecutePythonScript (full editor, not -run=pythonscript).
Feeds normal movement input to the possessed cat in PIE; never calls TryPushStatue.
"""
import json
import time
import traceback
from pathlib import Path
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert levels.load_level("/Game/Maps/Stage2")
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
state={"started":time.monotonic(),"phase":"wait"}
out=Path(unreal.Paths.project_dir())/"Saved"/"Stage2"/"pie-input.json"

def finish(result):
    out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    unreal.log("STAGE2_PIE_INPUT "+json.dumps(result))
    unreal.unregister_slate_post_tick_callback(state["handle"])
    levels.editor_request_end_play()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)

def tick(delta):
    try:
        now=time.monotonic()
        if now-state["started"]>35:
            finish({"success":False,"error":"PIE timed out","phase":state["phase"]})
            return
        world=editor.get_game_world()
        if world is None: return
        if state["phase"]=="wait":
            cats=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Character)
            cat=next((a for a in cats if a.get_class().get_name()=="BP_Cat_C"),None)
            controller=unreal.GameplayStatics.get_player_controller(world,0)
            puzzles=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunStatuePuzzle)
            if cat is None or controller is None or not puzzles: return
            controller.possess(cat)
            link=next(l for l in puzzles[0].get_editor_property("links") if str(l.get_editor_property("puzzle_id"))=="C")
            statue=link.get_editor_property("statue")
            start=statue.get_actor_location()
            cat.set_actor_location(unreal.Vector(start.x+95,start.y,26.2),False,True)
            state.update(phase="push",cat=cat,statue=statue,start_x=start.x,cat_start_x=cat.get_actor_location().x,push_start=now)
            return
        if state["phase"]=="push":
            state["cat"].add_movement_input(unreal.Vector(-1,0,0),1.,False)
            if now-state["push_start"]<4: return
            moved=state["start_x"]-state["statue"].get_actor_location().x
            cat_moved=state["cat_start_x"]-state["cat"].get_actor_location().x
            cat=state["cat"]
            actions=cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
            finish({"success":moved>100 and cat_moved>100,"statue_distance_cm":moved,"cat_distance_cm":cat_moved,
                    "map":"Stage2","input":"AddMovementInput(-X); runtime puzzle tick","rendered":False,
                    "mode":str(cat.character_movement.movement_mode),"speed":cat.character_movement.max_walk_speed,
                    "ignored":cat.is_move_input_ignored(),"busy":actions.get_editor_property("Busy"),
                    "position":str(cat.get_actor_location()),"input_vector":str(cat.get_last_movement_input_vector())})
    except Exception:
        finish({"success":False,"error":traceback.format_exc()})

state["handle"]=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
