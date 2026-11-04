"""Exercise original tutorial intro and stair trigger, never call CompleteTransition directly."""
import json
import time
import traceback
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = Path(unreal.Paths.project_saved_dir()) / 'Restoration'
out.mkdir(parents=True, exist_ok=True)
assert levels.load_level('/Game/Maps/SoundTest_Tutorial')
state = {'phase': 'intro', 'started': time.monotonic(), 'changed': time.monotonic(), 'events': [], 'samples': []}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def finish(ok, error=None):
    state['success'] = ok
    state['error'] = error
    (out / 'tutorial-pie.json').write_text(json.dumps({k:v for k,v in state.items() if k != 'handle'}, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('TUTORIAL_RESTORE_RESULT ' + str(ok) + ' ' + str(error))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)

def advance(phase, event):
    state.update(phase=phase, changed=time.monotonic())
    state['events'].append(event)
    unreal.log('TUTORIAL_RESTORE_STEP ' + event)

def shot(world, name):
    if '-nullrhi' not in unreal.SystemLibrary.get_command_line():
        unreal.SystemLibrary.execute_console_command(world, 'Shot showui filename="' + str(out / (name + '.png')).replace('\\', '/') + '"')

def tick(delta):
    try:
        now = time.monotonic()
        if now - state['started'] > 90:
            finish(False, 'Timeout: ' + state['phase']); return
        world = editor.get_game_world()
        if not world: return
        cat = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not cat: return
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        widgets = unreal.WidgetLibrary.get_all_widgets_of_class(world, unreal.UserWidget, False)
        if state['phase'] == 'intro':
            intros = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.get_class().get_name() == 'BP_TutorialIntro_C']
            player = intros[0].get_editor_property('IntroPlayer') if intros else None
            if now - state.get('intro_sample_time', 0) > 2:
                state['samples'].append({'intro_playing': bool(player and player.is_playing()), 'widgets': [w.get_class().get_name() for w in widgets], 'movement':str(cat.character_movement.movement_mode)})
                state['intro_sample_time'] = now
            if now - state['started'] < 3 or (player and player.is_playing()): return
            if 'intro_stopped' not in state:
                state['intro_stopped'] = now
            if now - state['intro_stopped'] < 1: return  # Original FinishIntro includes a 0.5s delay.
            hints = [w for w in widgets if w.get_class().get_name() == 'WBP_Tutorial_KeyHint_C' and w.is_in_viewport()]
            assert hints, 'Original key hint did not return after intro'
            assert not any(isinstance(w, unreal.CatrunPlayHUD) and w.is_in_viewport() for w in widgets), 'Replacement tutorial HUD still overrides original presentation'
            assert not pc.is_move_input_ignored(), 'Intro did not restore input'
            assert not unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunGuidanceZone), 'Injected tutorial guide zones remain'
            doors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunDoor)
            assert all(not d.is_open() for d in doors), 'Original closed door state was not restored'
            shot(world, 'original-tutorial-hints')
            advance('trigger', 'Original intro, key hints, input and closed doors restored')
        elif state['phase'] == 'trigger':
            cat.set_actor_location(unreal.Vector(-130, 1548, 26.2), False, True)
            advance('stairs', 'Entered the real stair overlap trigger')
        elif state['phase'] == 'stairs':
            if world.get_name().endswith('Stage1'):
                assert state.get('saw_stair_playback'), 'Travel bypassed the stair cinematic'
                advance('arrival', 'Stair cinematic finished and travelled to Stage1')
            else:
                directors = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                             if a.get_class().get_name() == 'BP_StairDescentDirector_C']
                player = directors[0].get_editor_property('SequencePlayer') if directors else None
                playing = [player.get_name()] if player and player.is_playing() else []
                if playing:
                    state['saw_stair_playback'] = True
                    view = pc.get_view_target()
                    state['stair_camera'] = view.get_name() if view else None
                    if not state.get('stair_shot') and now-state['changed']>2:
                        shot(world, 'original-stair-cinematic')
                        state['stair_shot'] = True
                if len(state['samples']) < 15 and now - state.get('sample_time', 0) > .5:
                    state['samples'].append({'world':world.get_name(), 'playing':playing, 'cat':str(cat.get_actor_location())})
                    state['sample_time'] = now
        elif state['phase'] == 'arrival' and now - state['changed'] > 5:
            assert not pc.is_move_input_ignored(), 'Stage1 arrival left input locked'
            advance('done', 'Stage1 arrival restored player input')
            finish(True)
    except Exception:
        finish(False, traceback.format_exc())

state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
