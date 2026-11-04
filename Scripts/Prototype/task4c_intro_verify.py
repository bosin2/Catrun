"""Read-only PIE observer for a real UI Start-button test.

This script NEVER starts gameplay, rebinds actors, or alters the sequence.
The controller starts PIE and clicks the existing menu button through the UI.
"""
import unreal,time,json,traceback
from pathlib import Path
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();assert levels.load_level('/Game/Maps/MainMenu')
actual_menu_out=Path(unreal.Paths.project_saved_dir())/'Prototype20261104'/'Task4c'/'FreshMenu'
actual_menu_out.mkdir(parents=True,exist_ok=True)
actual_menu_editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actual_menu_probe={'armed':time.monotonic(),'samples':[],'menu_seen':False,'shots':[]}
def _finish_actual_menu(error=None):
    actual_menu_probe['error']=error
    (actual_menu_out/'observations.json').write_text(json.dumps({k:v for k,v in actual_menu_probe.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
    unreal.unregister_slate_post_tick_callback(actual_menu_probe['handle'])
    print('ACTUAL_MENU_OBSERVATION_FINISHED',str(error))
def _observe_actual_menu(delta):
    try:
        now=time.monotonic()
        world=actual_menu_editor.get_game_world()
        if now-actual_menu_probe['armed']>100:
            _finish_actual_menu('Timed out before completed tutorial observation');return
        if not world or now-actual_menu_probe.get('last',0)<.3:return
        actual_menu_probe['last']=now
        world_name=world.get_name()
        if world_name.endswith('MainMenu'):actual_menu_probe['menu_seen']=True
        pc=unreal.GameplayStatics.get_player_controller(world,0)
        cat=unreal.GameplayStatics.get_player_pawn(world,0) if pc else None
        widgets=[w.get_class().get_name() for w in unreal.WidgetLibrary.get_all_widgets_of_class(world,unreal.UserWidget,False) if w.is_in_viewport()]
        view=pc.get_view_target() if pc else None
        sample={'wall_elapsed':now-actual_menu_probe['armed'],'world':world_name,'view':view.get_name() if view else None,'move_ignored':pc.is_move_input_ignored() if pc else None,'widgets':widgets}
        if cat:
            at=cat.get_actor_location()
            sample['cat_location']=[at.x,at.y,at.z]
            movement=cat.get_component_by_class(unreal.CharacterMovementComponent)
            sample['movement_mode']=str(movement.movement_mode) if movement else None
            mesh=cat.get_component_by_class(unreal.SkeletalMeshComponent)
            if mesh:
                head=mesh.get_socket_location('head')
                sample['head']=[head.x,head.y,head.z]
                sample['animation_mode']=str(mesh.get_animation_mode())
                sample['animation_instance']=mesh.get_anim_instance().get_class().get_name() if mesh.get_anim_instance() else None
        if 'Tutorial' in world_name:
            actual_menu_probe['saw_hint']=actual_menu_probe.get('saw_hint',False) or 'WBP_Tutorial_KeyHint_C' in widgets
            actual_menu_probe.setdefault('tutorial_entered',now)
            elapsed=now-actual_menu_probe['tutorial_entered']
            sample['tutorial_elapsed']=elapsed
            intro=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if a.get_class().get_name()=='BP_TutorialIntro_C'),None)
            player=intro.get_editor_property('IntroPlayer') if intro else None
            sample['intro_playing']=bool(player and player.is_playing())
            if player:
                seq=player.get_sequence()
                binding=next((b for b in seq.get_possessables() if b.get_name()=='BP_Cat_Player'),None)
                sample['bound_cat_count']=len(player.get_bound_objects(seq.get_binding_id(binding))) if binding else 0
            for mark in [1,4,7,12,16,19,24]:
                if elapsed>=mark and mark not in actual_menu_probe['shots']:
                    actual_menu_probe['shots'].append(mark)
                    unreal.SystemLibrary.execute_console_command(world,'Shot showui filename="'+str(actual_menu_out/('intro-'+str(mark)+'.png')).replace('\\','/')+'"')
                    break
            if elapsed>26:
                actual_menu_probe['completed']=bool(actual_menu_probe['menu_seen'] and not sample['intro_playing'] and not sample['move_ignored'] and actual_menu_probe.get('saw_hint') and 'WALKING' in str(sample.get('movement_mode')) and str(sample.get('view')).startswith('BP_QuarterViewCamera'))
                actual_menu_probe['samples'].append(sample)
                _finish_actual_menu(None if actual_menu_probe['completed'] else 'Tutorial completion/input/hints contract not met');return
        actual_menu_probe['samples'].append(sample)
    except Exception:_finish_actual_menu(traceback.format_exc())
actual_menu_probe['handle']=unreal.register_slate_post_tick_callback(_observe_actual_menu)
print('ACTUAL_MENU_OBSERVER_ARMED')

levels.editor_request_begin_play()

