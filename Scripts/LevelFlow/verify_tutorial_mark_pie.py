"""Real tutorial candle -> mark -> armor -> bedroom door. Test teleport, no direct AI calls."""
import json
import time
import traceback
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert levels.load_level('/Game/Maps/SoundTest_Tutorial')
out = Path(unreal.Paths.project_saved_dir()) / 'Restoration'
entry_only = '-MarkEntryOnly' in unreal.SystemLibrary.get_command_line()
state = {'phase':'intro', 'scenario':'entry' if entry_only else 'capture_interrupt', 'start':time.monotonic(), 'samples':[], 'open_doors':[]}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def finish(ok, error=None):
    state.update(success=ok, error=error)
    result_name = 'mark-entry-pie.json' if entry_only else 'mark-pie.json'
    (out / result_name).write_text(json.dumps({k:v for k,v in state.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('TUTORIAL_MARK_RESULT ' + str(ok) + ' ' + str(error))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)

def tick(delta):
    try:
        now = time.monotonic()
        if now-state['start'] > 80: finish(False,'Timed out in '+state['phase']); return
        world = editor.get_game_world()
        if not world: return
        cat = unreal.GameplayStatics.get_player_pawn(world,0)
        if not cat: return
        if state['phase']=='intro':
            actors = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
            intro = next(a for a in actors if a.get_class().get_name()=='BP_TutorialIntro_C')
            player = intro.get_editor_property('IntroPlayer')
            if now-state['start']<3 or (player and player.is_playing()): return
            state.setdefault('intro_stopped',now)
            if now-state['intro_stopped']<1: return
            doors = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunDoor)
            assert all(not d.is_open() for d in doors), 'Doors must begin closed'
            armor = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor)[0]
            scale = armor.get_editor_property('Mesh').get_editor_property('RelativeScale3D')
            state['original_mesh_scale'] = [scale.x, scale.y, scale.z]
            cat.set_actor_location(unreal.Vector(-20,350,26.2),False,True)
            state.update(phase='pursuit',changed=now)
        else:
            armor = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor)[0]
            doors = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunDoor)
            for door in doors:
                if door.is_open() and door.get_name() not in state['open_doors']:
                    state['open_doors'].append(door.get_name())
            marked = any(c.get_name().startswith('CatrunMarkOrb') for c in cat.get_components_by_class(unreal.StaticMeshComponent))
            state['saw_mark'] = state.get('saw_mark',False) or marked
            if entry_only and marked and not state.get('retreated'):
                # Let the armor finish entering instead of catching a cat beside the doorway.
                # This is the original intro's known-valid player start position.
                cat.set_actor_location(unreal.Vector(170,-95,26.2),False,True)
                state['retreated'] = True
            if now-state.get('sample_time',0)>.5:
                state['samples'].append({'elapsed':now-state['changed'],'armor':str(armor.get_actor_location()),'action':str(armor.get_action()),'marked':marked,'doors':[d.is_open() for d in doors]})
                state['sample_time']=now
            bedroom = next(d for d in doors if d.get_name() == 'CatrunDoor_0')
            corridor = next(d for d in doors if d.get_name() == 'CatrunDoor_1')
            if bedroom.is_open():
                state.setdefault('hand_open_y',armor.get_actor_location().y)
            captured_during_opening = 'CATCHING' in str(armor.get_action()) and armor.get_actor_location().y < state.get('hand_open_y',0)-40
            reached_target = armor.get_actor_location().y<450 if entry_only else captured_during_opening
            if reached_target and bedroom.is_open():
                assert state['saw_mark'], 'Candle never marked cat'
                assert not corridor.is_open(), 'Armor opened an unrelated door outside its path'
                state.setdefault('entered',now)
                leaf = bedroom.get_editor_property('DoorMesh')
                yaw = leaf.get_editor_property('RelativeRotation').yaw
                target = bedroom.get_editor_property('OpenYaw')
                scale = armor.get_editor_property('Mesh').get_editor_property('RelativeScale3D')
                state['final_door_yaw'] = yaw
                state['final_mesh_scale'] = [scale.x, scale.y, scale.z]
                if abs(yaw-target)<1 and now-state['entered']>1:
                    assert all(abs(a-b)<.001 for a,b in zip(state['final_mesh_scale'],state['original_mesh_scale'])), 'Door animation left armor mirrored after capture'
                    finish(True); return
                if now-state['entered']>4:
                    finish(False,'Door did not finish opening after capture interrupted its animation'); return
            if now-state['changed']>30:
                finish(False,'Candle mark scenario did not finish: '+state['scenario'])
    except Exception:
        finish(False,traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
