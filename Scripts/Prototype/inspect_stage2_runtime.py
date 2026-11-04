"""Observe the live test-map dependencies and gameplay camera without saving assets."""
import unreal,time,json,traceback
from pathlib import Path
output=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
level_editor=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_api=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor_api.get_game_world()
assert level_editor.load_level('/Game/Maps/SoundTest_Stage2')
inspection={'start':time.monotonic()}
def collect(delta):
    try:
        world=editor_api.get_game_world()
        elapsed=time.monotonic()-inspection['start']
        if world and elapsed>4 and not inspection.get('observed'):
            inspection['observed']=True
            pc=unreal.GameplayStatics.get_player_controller(world,0)
            cat=unreal.GameplayStatics.get_player_pawn(world,0)
            camera=pc.get_view_target().get_component_by_class(unreal.CameraComponent)
            inspection['world']=world.get_path_name()
            inspection['camera']={'owner':pc.get_view_target().get_class().get_name(),'width':camera.ortho_width,'move_input_ignored':pc.is_move_input_ignored()}
            actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
            inspection['dependencies']=[{'label':a.get_actor_label(),'class':a.get_class().get_name()} for a in actors if any(s in a.get_class().get_name() for s in ['Sound','Armor','Candle','NoBell','StatuePuzzle','PuzzleReset'])]
            inspection['widgets']=[w.get_class().get_name() for w in unreal.WidgetLibrary.get_all_widgets_of_class(world,unreal.UserWidget,False) if w.is_in_viewport()]
            unreal.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(output/'stage2-runtime.png').replace('\\','/')+'"')
        if elapsed>6:
            (output/'stage2-runtime.json').write_text(json.dumps({k:v for k,v in inspection.items() if k!='handle'},ensure_ascii=False,indent=2))
            unreal.unregister_slate_post_tick_callback(inspection['handle']);level_editor.editor_request_end_play()
    except Exception:
        (output/'stage2-runtime-error.txt').write_text(traceback.format_exc())
        unreal.unregister_slate_post_tick_callback(inspection['handle']);level_editor.editor_request_end_play()
inspection['handle']=unreal.register_slate_post_tick_callback(collect)
level_editor.editor_request_begin_play()
