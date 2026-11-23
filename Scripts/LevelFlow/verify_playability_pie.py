"""PIE checks for Stage2 HUD/menu, shared interact, and removal of local statue controls.
Uses test teleports, never saves runtime changes. Launch with -ExecutePythonScript.
"""
import json
import time
import traceback
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert levels.load_level('/Game/Maps/SoundTest_Stage2')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
out = Path(unreal.Paths.project_saved_dir()) / 'Flow/Playability'
out.mkdir(parents=True, exist_ok=True)
state = {'phase': 'stage2', 'start': time.monotonic(), 'changed': time.monotonic(), 'events': [], 'checks': {}}
WALKING = next(getattr(unreal.MovementMode,n) for n in dir(unreal.MovementMode) if n.upper().endswith('WALKING') and 'NAV' not in n.upper())

def subsystem(world):
    lib = unreal.get_default_object(unreal.load_class(None, '/Script/Engine.SubsystemBlueprintLibrary'))
    return lib.call_method('GetWorldSubsystem', args=(world, unreal.CatrunLevelFlowSubsystem.static_class()))

def hud(world):
    values = unreal.WidgetLibrary.get_all_widgets_of_class(world, unreal.CatrunPlayHUD, False)
    return values[0] if values else None

def xyz(point):
    return [point.x, point.y, point.z]

def advance(phase, message):
    state.update(phase=phase, changed=time.monotonic())
    state['events'].append(message)
    unreal.log('PLAYABILITY_STEP ' + message)

def shot(world, name):
    unreal.SystemLibrary.execute_console_command(world, 'Shot showui filename="' + str(out / (name + '.png')).replace('\\','/') + '"')

def finish(success, error=None):
    result = {'success': success, 'events': state['events'], 'checks': state['checks'], 'error': error,
              'rendered': '-nullrhi' not in unreal.SystemLibrary.get_command_line(),
              'scope': 'Stage2 PIE HUD controls, shared interaction at former recovery position, confirmed segment restart'}
    (out / 'pie.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('PLAYABILITY_PIE ' + json.dumps(result,ensure_ascii=False))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)

def tick(delta):
    try:
        now = time.monotonic()
        if now-state['start'] > 150:
            finish(False, 'Timeout in ' + state['phase']); return
        world = editor.get_game_world()
        if not world: return
        cat = unreal.GameplayStatics.get_player_pawn(world,0)
        ui = hud(world)
        if not cat or not ui: return
        phase = state['phase']
        if phase == 'stage2' and world.get_name().endswith('SoundTest_Stage2'):
            if cat.is_move_input_ignored() or now-state['changed'] < 1: return
            puzzle = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunStatuePuzzle)[0]
            links = {str(v.get_editor_property('puzzle_id')): v for v in puzzle.get_editor_property('links')}
            stations = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunPuzzleReset)
            assert not stations, 'A local recovery station was still placed in Stage2'
            # Find the real runtime widget tree using the mandatory menu buttons as controls.
            def belongs_to_ui(widget):
                owner = widget.get_outer()
                while owner and owner != ui:
                    owner = owner.get_outer()
                return owner == ui
            names = {w.get_name() for cls in (unreal.Button, unreal.TextBlock)
                     for w in unreal.ObjectIterator(cls) if belongs_to_ui(w)}
            assert {'ResumeButton', 'RestartButton', 'MainMenuButton'}.issubset(names), sorted(names)
            assert 'RecoveryHelp' not in names, sorted(names)
            statue = links['C'].get_editor_property('statue')
            statue.set_actor_location(statue.get_actor_location()+unreal.Vector(0,-40,0),False,True)
            before = {key:xyz(link.get_editor_property('statue').get_actor_location()) for key,link in links.items()}
            cat.set_actor_location(unreal.Vector(1650,3830,26.2), False, True)
            cat.character_movement.set_movement_mode(WALKING)
            cat.get_component_by_class(unreal.CatrunBasketInteractionComponent).try_interact()
            assert all(xyz(link.get_editor_property('statue').get_actor_location()) == before[key]
                       for key,link in links.items()), 'Shared interact reset a statue'
            state['checks'].update(placed_reset_stations=len(stations), recovery_help_visible=False,
                                   menu_buttons=sorted(names & {'ResumeButton','RestartButton','MainMenuButton'}),
                                   shared_interact_preserves_statues=True)
            advance('recovery_view','No placed reset controls; shared interact preserved all three statues')
        elif phase == 'recovery_view' and now-state['changed'] > 1:
            shot(world,'stage2-hud')
            advance('confirm_retry','Stage2 HUD after removal')
        elif phase == 'confirm_retry' and now-state['changed'] > 1:
            subsystem(world).set_pause_menu(True)
            ui.request_restart()
            ui.request_restart()
            advance('restarted','Confirmed menu restart requested')
        elif phase == 'restarted' and now-state['changed'] > 3:
            assert world.get_name().endswith('SoundTest_Stage2')
            assert not unreal.GameplayStatics.is_game_paused(world)
            assert not ui.get_editor_property('bMenuOpen')
            assert cat.get_actor_location().y > 3300
            advance('done','Confirmed restart loaded a fresh Stage2 world and restored input')
            finish(True)
    except Exception:
        finish(False,traceback.format_exc())

state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
