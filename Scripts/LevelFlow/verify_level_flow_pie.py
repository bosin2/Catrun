"""Run with -ExecutePythonScript in the full editor. Does not save maps.
Exercises the menu click and existing tutorial completion Blueprint, then real exit overlaps.
Teleports between checkpoints; this is a transition test, not a full walking playthrough.
"""
import json
import time
import traceback
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert levels.load_level('/Game/Maps/MainMenu')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
state = {'phase': 'menu', 'started': time.monotonic(), 'events': []}
output = Path(unreal.Paths.project_saved_dir()) / 'Flow' / 'pie-flow.json'

def finish(success, error=None):
    result = {'success': success, 'events': state['events'], 'phase': state['phase'],
              'rendered': False, 'scope': 'menu event, tutorial CompleteTransition, exit overlaps, restart, return to menu'}
    if error: result['error'] = error
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('CATRUN_FLOW_PIE ' + json.dumps(result, ensure_ascii=False))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)

def advance(phase, event):
    state['phase'] = phase
    state['events'].append(event)
    state['changed'] = time.monotonic()
    unreal.log('FLOW_TEST_STEP ' + event)

def menu_widget(world):
    return next((w for w in unreal.WidgetLibrary.get_all_widgets_of_class(world, unreal.UserWidget, False)
                 if w.get_class().get_name() == 'WBP_MainMenu_C'), None)

def flow_subsystem(world):
    # BlueprintInternalUseOnly functions are omitted from the generated Python API.
    library = unreal.get_default_object(unreal.load_class(None, '/Script/Engine.SubsystemBlueprintLibrary'))
    return library.call_method('GetWorldSubsystem', args=(world, unreal.CatrunLevelFlowSubsystem.static_class()))

def tick(delta):
    try:
        now = time.monotonic()
        if now - state['started'] > 100:
            finish(False, 'Timed out at ' + state['phase']); return
        world = editor.get_game_world()
        if not world: return
        name = world.get_name()
        phase = state['phase']
        cat = unreal.GameplayStatics.get_player_pawn(world, 0)
        if phase == 'menu' and name.endswith('MainMenu'):
            widget = menu_widget(world)
            if not widget: return
            widget.get_editor_property('StartButton').on_clicked.broadcast()
            advance('tutorial', 'Main menu StartButton clicked')
        elif phase == 'tutorial' and name.endswith('SoundTest_Tutorial') and cat:
            exits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_class().get_name() == 'BP_LevelExit_C']
            assert len(exits) == 1
            exits[0].call_method('CompleteTransition')
            advance('stage1', 'Existing tutorial CompleteTransition called')
        elif phase == 'stage1' and name.endswith('SoundTest_Stage1') and cat:
            exits = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunStageExit)
            assert len(exits) == 1
            cat.set_actor_location(unreal.Vector(101, 65, 26.2), False, True)
            advance('stage2', 'Stage1 cat teleported into actual exit trigger')
        elif phase == 'stage2' and name.endswith('SoundTest_Stage2') and cat:
            exits = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunStageExit)
            assert len(exits) == 1
            cat.set_actor_location(unreal.Vector(715, 70, 26.2), False, True)
            advance('complete', 'Stage2 cat teleported into actual completion trigger')
        elif phase == 'complete' and now - state['changed'] > 1:
            assert name.endswith('SoundTest_Stage2'), name
            flow = flow_subsystem(world)
            assert flow.get_editor_property('bStageComplete'), 'Completion flag was not set'
            assert not unreal.CatrunLevelFlowLibrary.complete_current_stage(world), 'Duplicate completion accepted'
            assert unreal.CatrunLevelFlowLibrary.restart_current_stage(world)
            advance('restart', 'Stage2 stayed loaded, completed once, restart requested')
        elif phase == 'restart' and name.endswith('SoundTest_Stage2') and cat and now - state['changed'] > 2:
            flow = flow_subsystem(world)
            if flow.get_editor_property('bStageComplete'): return
            assert cat.get_actor_location().y > 3300, 'Restart did not restore the spawn position'
            assert unreal.CatrunLevelFlowLibrary.return_to_main_menu(world)
            advance('return', 'Restart cleared completion and restored Stage2 spawn; returning to menu')
        elif phase == 'return' and name.endswith('MainMenu') and menu_widget(world):
            menu_widget(world).get_editor_property('StartButton').on_clicked.broadcast()
            advance('replay', 'Main menu restored and StartButton clicked again')
        elif phase == 'replay' and name.endswith('SoundTest_Tutorial') and cat:
            advance('done', 'Second new game reached tutorial')
            finish(True)
    except Exception:
        finish(False, traceback.format_exc())

state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
