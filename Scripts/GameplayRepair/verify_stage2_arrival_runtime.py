"""Offscreen PIE: real Stage1 portal overlap, Stage2 arrival and recovery.

Run in a fresh normal editor process with -RenderOffscreen, not a commandlet.
UE 5.8's editor BoxComponent show-flag proxy currently requires -onethread here.
Disable foreground CPU throttling only for this process via the EditorSettings
command-line override, so readiness does not race the first simulated frame.
The test places the pawn at a clear exit checkpoint; it is not manual traversal.
No map/asset saves. Root must preserve the user's save/settings around this run.
"""
import datetime
import json
import time
import traceback
from pathlib import Path
import unreal as u

OUT=Path(u.Paths.project_saved_dir()).resolve()/'Stage2Arrival20261116/Runtime'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
OUT.mkdir(parents=True,exist_ok=False)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ED.get_game_world()
assert LEVEL.load_level('/Game/Maps/Stage1')
STATE={'start':time.monotonic(),'phase':'stage1','samples':[],'events':[],
       'scope':'Offscreen PIE with API placement at real portal trigger; no manual traversal.'}


def advance(phase):
    STATE.update(phase=phase,changed=time.monotonic())
    STATE['events'].append({'phase':phase,'elapsed':time.monotonic()-STATE['start']})


def finish(error=None):
    STATE['success']=error is None
    STATE['error']=error
    (OUT/'report.json').write_text(json.dumps({k:v for k,v in STATE.items() if k!='handle'},indent=2),encoding='utf8')
    LEVEL.editor_request_end_play()
    STATE['phase']='shutdown'; STATE['changed']=time.monotonic()
    print('STAGE2_ARRIVAL_RUNTIME_DONE',error,str(OUT/'report.json'))


def props(actor,*names):
    return {n:actor.get_editor_property(n) for n in names}


def verify_spawned_visuals(player):
    sequence=u.load_asset('/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival')
    result={}
    paths=set(STATE.get('spawnable_paths',[]))
    for binding in sequence.get_bindings():
        if not binding.get_object_template(): continue
        actors=player.get_bound_objects(sequence.get_binding_id(binding))
        paths.update(actor.get_path_name() for actor in actors)
        if binding.get_name() not in ('CosmeticCat','ArrivalPortal'): continue
        assert len(actors)==1,('Missing spawned visual',binding.get_name())
        actor=actors[0]
        primitives=actor.get_components_by_class(u.PrimitiveComponent)
        assert primitives,('No primitives on spawned visual',actor.get_name())
        components=[]
        for item in primitives:
            collision=item.get_collision_enabled()
            overlaps=item.get_editor_property('generate_overlap_events')
            assert collision==u.CollisionEnabled.NO_COLLISION and not overlaps,(actor.get_name(),item.get_name(),collision,overlaps)
            components.append({'name':item.get_name(),'collision':str(collision),'overlap_events':overlaps})
        result[binding.get_name()]={'actor_collision_flag':actor.get_actor_enable_collision(),'components':components}
    assert set(result)=={'CosmeticCat','ArrivalPortal'},result
    STATE['spawnable_paths']=sorted(paths)
    return result


def checkpoint(world,cat):
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    exit_actor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunStageExit))
    trigger=exit_actor.get_editor_property('Trigger')
    direction=u.MathLibrary.transform_direction(exit_actor.get_actor_transform(),exit_actor.get_editor_property('InteriorDirectionLocal'))
    target=trigger.get_world_location()+direction*(exit_actor.get_editor_property('MinimumInteriorDepth')+5.)
    target.z+=100.
    STATE['exit_fixture']={'actor':exit_actor.get_path_name(),'center':str(trigger.get_world_location()),
        'extent':str(trigger.get_scaled_box_extent()),'interior_direction':str(direction),
        'minimum_depth':exit_actor.get_editor_property('MinimumInteriorDepth'),
        'use_presentation':exit_actor.get_editor_property('bUseExitTransition')}
    hit=u.SystemLibrary.line_trace_single_by_profile(world,target,target-u.Vector(0,0,500),'Pawn',False,[cat],u.DrawDebugTrace.NONE,False)
    assert hit,'No floor at exit checkpoint'
    target.z=hit.to_dict()['impact_point'].z+capsule.get_scaled_capsule_half_height()+2.2
    blocked=u.SystemLibrary.capsule_trace_single_by_profile(world,target,target+u.Vector(0,0,.01),capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,[cat],u.DrawDebugTrace.NONE,False)
    assert not blocked,('Exit checkpoint is blocked',str(blocked))
    cat.set_actor_location_and_rotation(target,u.Rotator(yaw=-90),False,True)


def assert_playable(world,pc,cat,row):
    assert not row['input_ignored'] and not row['look_ignored'],row
    assert not row['hidden'] and not row['suspended'] and not row['hud_hidden'],row
    assert 'QuarterView' in row['view'],row
    assert cat.get_component_by_class(u.CharacterMovementComponent).movement_mode==u.MovementMode.MOVE_WALKING,row
    assert abs(cat.get_actor_location().x-1375)<2 and abs(cat.get_actor_location().y-3700)<2,row
    camera=pc.get_view_target().get_component_by_class(u.CameraComponent)
    assert abs(camera.ortho_width-1170)<1,('Stage2 camera profile/handoff mismatch',camera.ortho_width)
    live={a.get_path_name() for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor)}
    assert not live.intersection(STATE.get('spawnable_paths',[])),('Sequence spawnables survived cleanup',live.intersection(STATE['spawnable_paths']))
    STATE['runtime_spawnables_removed']=True


def tick(delta):
    try:
        now=time.monotonic()
        if STATE['phase']=='shutdown':
            if not ED.get_game_world() and now-STATE['changed']>1:
                u.unregister_slate_post_tick_callback(STATE['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        if now-STATE['start']>160:
            finish('Timeout in '+STATE['phase']); return
        if now-STATE.get('last',0)<.08: return
        STATE['last']=now
        world=ED.get_game_world()
        if not world:return
        pc=u.GameplayStatics.get_player_controller(world,0); cat=u.GameplayStatics.get_player_pawn(world,0)
        if not pc or not cat:return
        phase=STATE['phase']; stage=world.get_name(); view=pc.get_view_target()
        row={'elapsed':now-STATE['start'],'world':world.get_path_name(),'phase':phase,
             'input_ignored':pc.is_move_input_ignored(),'look_ignored':pc.is_look_input_ignored(),
             'hidden':cat.get_editor_property('hidden'),'view':view.get_name() if view else '',
             'cat':[cat.get_actor_location().x,cat.get_actor_location().y,cat.get_actor_location().z],
             'suspended':u.CatrunPuzzleSuspension.is_suspended(world),
             'hud_hidden':u.CatrunLevelFlowLibrary.should_hide_gameplay_hud(world)}
        STATE['samples'].append(row)
        pcm=u.GameplayStatics.get_player_camera_manager(world,0)
        if pcm:
            camera_location=pcm.get_camera_location(); camera_rotation=pcm.get_camera_rotation()
            row['camera_position']=[camera_location.x,camera_location.y,camera_location.z]
            row['camera_rotation']=[camera_rotation.pitch,camera_rotation.yaw,camera_rotation.roll]
        if (phase=='stage1' and now-STATE['start']>5 and not row['input_ignored']
                and u.GameplayStatics.get_time_seconds(world)>1.
                and cat.get_component_by_class(u.CharacterMovementComponent).movement_mode==u.MovementMode.MOVE_WALKING):
            assert stage.endswith('Stage1'),stage
            checkpoint(world,cat); advance('portal')
        elif phase=='portal':
            if stage.endswith('Stage1'):
                directors=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_class().get_name()=='BP_Stage1PortalExit_C']
                if directors and directors[0].get_editor_property('Playing'): STATE['departure_played']=True
                if now-STATE['changed']>20 and not STATE.get('departure_played'):
                    exit_actor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunStageExit))
                    trigger=exit_actor.get_editor_property('Trigger')
                    STATE['exit_fixture']['overlapping']=trigger.is_overlapping_actor(cat)
                    lease=exit_actor.get_editor_property('ExitTransition')
                    diagnostic=lease.acquire_exit_lease(cat)
                    STATE['exit_fixture']['diagnostic_lease']=str(diagnostic)
                    if lease.has_exit_lease(): lease.release_exit_lease(False)
                    finish('Portal did not start; see exit_fixture diagnostic'); return
            elif stage.endswith('Stage2'):
                assert STATE.get('departure_played'),'Departure sequence was bypassed'
                advance('arrival')
        elif stage.endswith('Stage2'):
            director=next((a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_class().get_name()=='BP_Stage2PortalArrival_C'),None)
            if director: row.update(props(director,'Playing','Started','Finished'))
            player=director.get_editor_property('SequencePlayer') if director else None
            row['sequence_time']=player.get_current_time().time.frame_number.value/30. if player else None
            row['arrival_route']=u.CatrunLevelFlowLibrary.is_stage2_portal_arrival(world)
            if phase=='arrival':
                if row['Playing']:
                    STATE['arrival_played']=True
                    assert row['input_ignored'] and row['suspended'] and row['hidden'],row
                    for shot,threshold in (('arrival-title',.8),('arrival-room',3.6),('arrival-gate',7.5),('arrival-blend',10.8)):
                        key='shot_'+shot
                        if row['sequence_time']>=threshold and not STATE.get(key):
                            STATE.setdefault('visual_collision_checks',[]).append({'time':row['sequence_time'],'visuals':verify_spawned_visuals(player)})
                            STATE[key]=True
                            filename=str(OUT/(shot+'.png')).replace('\\','/')
                            u.SystemLibrary.execute_console_command(world,f'Shot showui filename="{filename}"')
                if row['Finished'] and now-STATE['changed']>13:
                    assert STATE.get('arrival_played'),'Arrival never played automatically'
                    assert_playable(world,pc,cat,row)
                    director.call_method('TryStartArrival')
                    advance('one-shot')
            elif phase=='one-shot' and now-STATE['changed']>1:
                assert row['Finished'] and not row['Playing'],row
                assert_playable(world,pc,cat,row)
                assert u.CatrunLevelFlowLibrary.restart_current_stage(world)
                advance('restart')
            elif phase=='restart' and now-STATE['changed']>4:
                assert not row['Started'] and not row['arrival_route'],row
                assert_playable(world,pc,cat,row)
                # Preview a second explicit portal load, then interrupt its sequence.
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'FromStage1Portal')
                advance('interrupt')
            elif phase=='interrupt' and row['Playing'] and row['sequence_time']>2:
                director.call_method('AbortArrival')
                advance('interrupted')
            elif phase=='interrupted' and now-STATE['changed']>1:
                assert not row['Playing'],row
                assert_playable(world,pc,cat,row)
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'')
                advance('direct')
            elif phase=='direct' and now-STATE['changed']>3:
                assert not row['Started'] and not row['arrival_route'],row
                assert_playable(world,pc,cat,row)
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'FromStage1Portal')
                advance('remove-owner')
            elif phase=='remove-owner' and row.get('Playing') and row['sequence_time']>1:
                # Cut and destroy in the same callback, before the 50ms view monitor.
                position=u.MovieSceneSequencePlaybackParams()
                position.set_editor_property('frame',u.FrameTime(u.FrameNumber(95),0.))
                position.set_editor_property('position_type',u.MovieScenePositionType.FRAME)
                position.set_editor_property('update_method',u.UpdatePositionMethod.JUMP)
                player.set_playback_position(position)
                director.destroy_actor()
                advance('removed')
            elif phase=='removed' and now-STATE['changed']>1:
                assert director is None,'Destroyed director still exists'
                assert_playable(world,pc,cat,row)
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'FromStage1Portal')
                advance('external-view')
            elif phase=='external-view' and row.get('Playing') and row['sequence_time']>1:
                other=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if isinstance(a,u.CatrunStageExit))
                gameplay=director.get_editor_property('GameplayViewTarget')
                pc.set_view_target_with_blend(other,0.)
                director.call_method('AbortArrival')
                assert pc.get_view_target()==other,'Stopping the sequence replaced an external view owner'
                STATE['external_view_preserved']=True
                pc.set_view_target_with_blend(gameplay,0.)
                advance('external-restored')
            elif phase=='external-restored' and now-STATE['changed']>1:
                assert_playable(world,pc,cat,row)
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'FromStage1Portal')
                advance('external-stop')
            elif phase=='external-stop' and row.get('Playing') and row['sequence_time']>1:
                other=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if isinstance(a,u.CatrunStageExit))
                gameplay=director.get_editor_property('GameplayViewTarget')
                pc.set_view_target_with_blend(other,0.)
                player.stop()
                assert pc.get_view_target()==other,'External Sequence.Stop replaced an external view owner'
                STATE['external_stop_view_preserved']=True
                pc.set_view_target_with_blend(gameplay,0.)
                advance('external-stopped')
            elif phase=='external-stopped' and now-STATE['changed']>1:
                assert_playable(world,pc,cat,row)
                u.GameplayStatics.open_level(world,'/Game/Maps/Stage2',True,'FromStage1Portal')
                advance('possession')
            elif phase=='possession' and row.get('Playing') and row['sequence_time']>1:
                pc.un_possess()
                pc.possess(cat)
                STATE['repossessed_view']=pc.get_view_target().get_name()
                advance('repossessed')
            elif phase=='repossessed' and now-STATE['changed']>1:
                assert not row['Playing'],row
                assert not row['input_ignored'] and not row['look_ignored'] and not row['hidden'] and not row['suspended'],row
                assert row['view']==STATE['repossessed_view'],'Cleanup replaced the new possession view owner'
                assert cat.get_component_by_class(u.CharacterMovementComponent).movement_mode==u.MovementMode.MOVE_WALKING,row
                finish()
        if len(STATE['samples'])%30==0:
            (OUT/'progress.json').write_text(json.dumps({k:v for k,v in STATE.items() if k!='handle'},indent=2),encoding='utf8')
    except Exception:
        finish(traceback.format_exc())

STATE['handle']=u.register_slate_post_tick_callback(tick)
LEVEL.editor_request_begin_play()
print('STAGE2_ARRIVAL_RUNTIME_STARTED',str(OUT))
