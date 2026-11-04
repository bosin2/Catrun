"""PIE checks for Stage2 HUD/menu and room-local F interaction.
Uses test teleports, never saves runtime changes. Launch with -ExecutePythonScript.
"""
import json
import time
import traceback
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
recovery_only = True  # Tutorial has its own original presentation and separate regression checks.
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
              'recovery_only': recovery_only, 'rendered': '-nullrhi' not in unreal.SystemLibrary.get_command_line(),
              'scope': 'Stage2 PIE HUD/menu and local recovery using existing F action entry; test teleports'}
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
            assert len(stations) == 3
            # Each room's recovery must work from an unobstructed approach, without teleporting the cat.
            for station in stations:
                key = str(station.get_editor_property('PuzzleId'))
                statue = links[key].get_editor_property('statue')
                original = statue.get_actor_location()
                statue.set_actor_location(original+unreal.Vector(0,-100,0),False,True)
                before_other = {k: xyz(v.get_editor_property('statue').get_actor_location()) for k,v in links.items() if k != key}
                approaches = []
                for dx,dy in [(55,0),(-55,0),(0,55),(0,-55)]:
                    cat.set_actor_location(station.get_actor_location()+unreal.Vector(dx,dy,25.2),False,True)
                    if station.can_interact(cat): break
                    debug_none = next(getattr(unreal.DrawDebugTrace,n) for n in dir(unreal.DrawDebugTrace) if n.upper().endswith('NONE'))
                    trace_type = next(getattr(unreal.TraceTypeQuery,n) for n in dir(unreal.TraceTypeQuery) if n.upper().endswith('QUERY1'))
                    hit = unreal.SystemLibrary.line_trace_single(world,cat.get_actor_location(),station.get_actor_location()+unreal.Vector(0,0,25),trace_type,False,[cat,station],debug_none,True)
                    broken = unreal.get_default_object(unreal.GameplayStatics.static_class()).call_method('BreakHitResult', args=(hit,)) if hit else None
                    blocker = broken[9] if broken else None
                    approaches.append({'offset':[dx,dy],'blocker':blocker.get_actor_label() if blocker else None})
                state['checks'].setdefault('approaches',{})[key] = {'blocked':approaches,'selected_cat_position':xyz(cat.get_actor_location())}
                actions = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
                if not station.can_interact(cat):
                    debug_none = next(getattr(unreal.DrawDebugTrace,n) for n in dir(unreal.DrawDebugTrace) if n.upper().endswith('NONE'))
                    trace_type = next(getattr(unreal.TraceTypeQuery,n) for n in dir(unreal.TraceTypeQuery) if n.upper().endswith('QUERY1'))
                    hit = unreal.SystemLibrary.line_trace_single(world,cat.get_actor_location(),station.get_actor_location()+unreal.Vector(0,0,25),trace_type,False,[cat,station],debug_none,True)
                    state['checks']['blocked_station'] = {'id':key,'station':str(station.get_actor_location()),'cat':str(cat.get_actor_location()),
                        'range':station.get_editor_property('InteractionRange'),'puzzle':str(station.get_editor_property('Puzzle')),
                        'busy':actions.get_editor_property('Busy'),'hidden':actions.get_editor_property('IsHidden'),'trace':str(hit),'approaches':approaches}
                    raise AssertionError('Unreachable station ' + key)
                cat_before = xyz(cat.get_actor_location())
                actions.try_interact()  # Same entry point wired to the existing F input action.
                assert sum((a-b)**2 for a,b in zip(xyz(statue.get_actor_location()),xyz(original))) < 1, 'F did not reset ' + key
                assert xyz(cat.get_actor_location()) == cat_before
                assert all(xyz(links[k].get_editor_property('statue').get_actor_location()) == p for k,p in before_other.items())
                assert not station.try_use(None), 'Non-player interaction accepted'
            state['checks']['room_recovery'] = 'A/B/C restored independently through F action entry; other statues/player unchanged'
            advance('recovery_view','All three local recovery stations passed')
        elif phase == 'recovery_view' and now-state['changed'] > 1:
            shot(world,'stage2-recovery')
            advance('confirm_retry','Recovery prompt captured in Stage2')
        elif phase == 'confirm_retry' and now-state['changed'] > 1:
            subsystem(world).set_pause_menu(True)
            ui.request_restart()
            ui.request_restart()
            advance('restarted','All three local recovery stations passed; confirmed menu restart requested')
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
