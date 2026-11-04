"""Rendered capture probe triggered by proximity; teleports are test setup, not a playthrough."""
import unreal, time, json, traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert levels.load_level('/Game/Maps/SoundTest_Stage1')
probe={'start':time.monotonic(),'samples':[]}
def finish(error=None):
    probe['error']=error
    (out/'capture-pie-probe.json').write_text(json.dumps({k:v for k,v in probe.items() if k!='handle'},ensure_ascii=False,indent=2))
    unreal.unregister_slate_post_tick_callback(probe['handle'])
    levels.editor_request_end_play()
def tick(delta):
    try:
        elapsed=time.monotonic()-probe['start']
        world=editor.get_game_world()
        if world:
            cat=unreal.GameplayStatics.get_player_pawn(world,0)
            pc=unreal.GameplayStatics.get_player_controller(world,0)
            armors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor)
            if cat and pc and armors:
                armor=armors[0]
                if elapsed>3 and not probe.get('placed'):
                    at=armor.get_actor_location()+armor.get_actor_forward_vector()*60
                    at.z=cat.get_actor_location().z
                    cat.set_actor_location(at,False,True)
                    probe['placed']=True
                if elapsed-probe.get('last',-10)>0.4:
                    probe['last']=elapsed
                    capture=armor.get_editor_property('CapturePresentation')
                    phase=str(capture.get_editor_property('Phase'))
                    view=pc.get_view_target()
                    cameras=view.get_components_by_class(unreal.CameraComponent) if view else []
                    probe['samples'].append({'elapsed':elapsed,'world':world.get_path_name(),'armor_action':str(armor.get_action()),'phase':phase,'cat':str(cat.get_actor_location()),'view':view.get_name() if view else None,'ignore_move':pc.is_move_input_ignored(),'camera_width':cameras[0].ortho_width if cameras else None})
                    if 'INACTIVE' not in phase and phase not in probe.get('shots',[]):
                        probe.setdefault('shots',[]).append(phase)
                        unreal.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(out/('capture-'+str(len(probe['shots']))+'.png')).replace('\\','/')+'"')
        if elapsed>22:finish()
    except Exception:finish(traceback.format_exc())
probe['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
