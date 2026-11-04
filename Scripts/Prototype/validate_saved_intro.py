"""MainMenu native API route: observe saved intro, completion, and retry.
Never overrides bindings/poses/cameras or changes gameplay state except flow APIs.
"""
import unreal,time,json,traceback
from pathlib import Path
run_label=globals().get('intro_validation_label','saved-intro-api-run1')
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Prototype20261104'/run_label
out.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert levels.load_level('/Game/Maps/MainMenu')
probe={'started':time.monotonic(),'scenario':'PIE MainMenu -> existing native StartNewGame API -> saved BP intro -> RestartCurrentStage API','samples':[],'shots':[]}

def vec(v):return [v.x,v.y,v.z]
def finish(error=None):
    probe['error']=error
    (out/'observations.json').write_text(json.dumps({k:v for k,v in probe.items() if k!='handle'},indent=2),encoding='utf8')
    unreal.unregister_slate_post_tick_callback(probe['handle'])
    levels.editor_request_end_play()
    print('SAVED_INTRO_VALIDATION_FINISHED',run_label,error)

def sample(world,elapsed):
    pc=unreal.GameplayStatics.get_player_controller(world,0)
    cat=unreal.GameplayStatics.get_player_pawn(world,0)
    actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
    intro=next((a for a in actors if a.get_class().get_name()=='BP_TutorialIntro_C'),None)
    player=intro.get_editor_property('IntroPlayer') if intro else None
    view=pc.get_view_target() if pc else None
    cameras=view.get_components_by_class(unreal.CameraComponent) if view else []
    widgets=[w.get_class().get_name() for w in unreal.WidgetLibrary.get_all_widgets_of_class(world,unreal.UserWidget,False) if w.is_in_viewport()]
    row={'elapsed':elapsed,'world':world.get_path_name(),'phase':'retry' if probe.get('restart_requested') else 'initial','view':view.get_name() if view else None,'view_tick':view.is_actor_tick_enabled() if view else None,'camera_width':cameras[0].ortho_width if cameras else None,'move_ignored':pc.is_move_input_ignored() if pc else None,'look_ignored':pc.is_look_input_ignored() if pc else None,'widgets':widgets,'intro_exists':bool(intro),'intro_player':bool(player),'intro_playing':bool(player and player.is_playing())}
    if cat:
        mesh=cat.get_component_by_class(unreal.SkeletalMeshComponent)
        row.update(cat=cat.get_path_name(),location=vec(cat.get_actor_location()),rotation=str(cat.get_actor_rotation()),velocity=vec(cat.get_velocity()),movement=str(cat.get_component_by_class(unreal.CharacterMovementComponent).movement_mode),head=vec(mesh.get_socket_location('head')),head_local=vec(mesh.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_COMPONENT).translation),animation_mode=str(mesh.get_animation_mode()),animation_instance=mesh.get_anim_instance().get_class().get_name() if mesh.get_anim_instance() else None)
    if player:
        seq=player.get_sequence()
        row['sequence_seconds']=player.get_current_time().time.frame_number.value/seq.get_display_rate().numerator
        row['bindings']={b.get_name():[o.get_path_name() for o in player.get_bound_objects(seq.get_binding_id(b))] for b in seq.get_bindings() if b.get_name()!='CameraComponent'}
    return row

def tick(delta):
    try:
        now=time.monotonic();elapsed=now-probe['started']
        world=editor.get_game_world()
        if elapsed>65:finish('timeout');return
        if not world:return
        if now-probe.get('last',0)>.35:
            probe['last']=now
            row=sample(world,elapsed);probe['samples'].append(row)
            if world.get_name().endswith('MainMenu'):
                probe['menu_seen']=True
                if elapsed>2 and not probe.get('start_requested'):
                    probe['start_requested']=unreal.CatrunLevelFlowLibrary.start_new_game(world)
                    probe['start_request_elapsed']=elapsed
            elif 'Tutorial' in world.get_name():
                probe.setdefault('tutorial_entered',now)
                t=now-probe['tutorial_entered']
                row['tutorial_elapsed']=t
                if not probe.get('restart_requested'):
                    for mark in [1,4,7,12,16,18,20,24]:
                        if t>=mark and mark not in probe['shots']:
                            probe['shots'].append(mark)
                            unreal.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(out/('intro-'+str(mark)+'.png')).replace('\\','/')+'"');break
                    if t>26:
                        probe['normal_complete']=bool(not row['intro_playing'] and row['animation_instance']=='ABP_Cat_Final_C' and row['view']=='BP_QuarterViewCamera_C_0' and not row['move_ignored'] and 'WBP_Tutorial_KeyHint_C' in row['widgets'])
                        probe['normal_playable_location']=row['location']
                        probe['authored_playable_transform']={'location':[170,-95,23.5],'yaw':90}
                        probe['restart_requested']=unreal.CatrunLevelFlowLibrary.restart_current_stage(world)
                        probe['restart_at']=now
                elif now-probe['restart_at']>6:
                    probe['retry_complete']=bool(not row['intro_player'] and row['animation_instance']=='ABP_Cat_Final_C' and row['view']=='BP_QuarterViewCamera_C_0' and row['camera_width']==900 and not row['move_ignored'] and 'WBP_Tutorial_KeyHint_C' not in row['widgets'] and abs(row['location'][0]-170)<1 and abs(row['location'][1]+95)<1 and abs(row['location'][2]-probe['normal_playable_location'][2])<1)
                    probe['retry_playable_location']=row['location']
                    probe['floor_note']='Authored Z is 23.5. Character floor/capsule resolution settles normal FinishIntro near26.25 and native collision-safe TeleportTo near26.5.'
                    unreal.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(out/'retry.png').replace('\\','/')+'"')
                    finish(None if probe['normal_complete'] and probe['retry_complete'] else 'normal/retry contract failed')
    except Exception:finish(traceback.format_exc())
probe['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()

