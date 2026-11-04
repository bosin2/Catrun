import unreal, time, json, traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels.load_level('/Game/Maps/SoundTest_Tutorial')
state={'started':time.monotonic(),'samples':[]}
def tick(delta):
    try:
        world=editor.get_game_world()
        elapsed=time.monotonic()-state['started']
        if world and elapsed-state.get('last',-10)>2:
            state['last']=elapsed
            cat=unreal.GameplayStatics.get_player_pawn(world,0)
            actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
            intro=next((a for a in actors if a.get_class().get_name()=='BP_TutorialIntro_C'),None)
            player=intro.get_editor_property('IntroPlayer') if intro else None
            row={'time':elapsed,'cat':cat.get_path_name() if cat else None,'location':str(cat.get_actor_location()) if cat else None}
            if cat:
                mesh=cat.get_component_by_class(unreal.SkeletalMeshComponent)
                row.update(mode=str(mesh.get_animation_mode()),anim=str(mesh.get_anim_instance()),head=str(mesh.get_socket_location('head')))
            if player:
                row['playing']=player.is_playing()
                row['bindings']={}
                for b in player.get_sequence().get_bindings():
                    binding=unreal.MovieSceneObjectBindingID()
                    binding.set_editor_property('guid',b.get_id())
                    row['bindings'][b.get_name()]=[o.get_path_name() for o in player.get_bound_objects(binding)]
            state['samples'].append(row)
        if elapsed>26:
            (out/'intro-pie-baseline.json').write_text(json.dumps({k:v for k,v in state.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
            unreal.unregister_slate_post_tick_callback(state['handle']); levels.editor_request_end_play()
            print('INTRO_BASELINE_FINISHED')
    except Exception:
        (out/'intro-pie-error.txt').write_text(traceback.format_exc()); unreal.unregister_slate_post_tick_callback(state['handle']); levels.editor_request_end_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
