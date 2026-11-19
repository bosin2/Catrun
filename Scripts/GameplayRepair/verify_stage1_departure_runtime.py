"""PIE regression: real candle, denied lease, accepted portal, abort, re-mark and qualifying travel.

Run via -ExecutePythonScript in a normal offscreen editor with isolated user saves/settings.
The script moves PIE-only fixtures near the real trigger. It never saves map or content packages.
"""
import datetime
import json
from pathlib import Path
import time
import traceback

import unreal as u

MIRROR='-catrundeparturemirror' in u.SystemLibrary.get_command_line().lower()
MAP='/Game/Maps/SoundTest_Stage1' if MIRROR else '/Game/Maps/Stage1'
RUN_FOLDER='DepartureMirrorRuntime' if MIRROR else 'DepartureRuntime'
OUT=Path(u.Paths.project_saved_dir()).resolve()/'PresentationFix20261119'/RUN_FOLDER/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(parents=True,exist_ok=False)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem)
S={'map':MAP,'mirror':MIRROR,'phase':'ready','events':[],'samples':[],'started':time.monotonic(),'pass':1}
FIX={}


def persist():
    (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},indent=1),encoding='utf-8')


def next_phase(phase):
    S.update(phase=phase,changed=time.monotonic())
    S['events'].append([phase,S['changed']-S['started']])
    persist()


def finish(error=None):
    if 'no_capture_before' in S:
        u.CatrunUserSettings.set_no_armor_capture_enabled(S['no_capture_before'])
        S['no_capture_after']=u.CatrunUserSettings.is_no_armor_capture_enabled()
        if S['no_capture_after']!=S['no_capture_before']:
            error=(error or '')+' Capture debug setting did not restore.'
    S['success']=error is None
    S['error']=error
    FIX.clear()
    next_phase('shutdown')
    LEVEL.editor_request_end_play()
    print('CATRUN_DEPARTURE_PIE_DONE',str(OUT),S['success'])


def ground(world,cat,x,y):
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    ignored=[cat,*u.GameplayStatics.get_all_actors_of_class(world,u.CatrunStageExit)]
    hit=u.SystemLibrary.capsule_trace_single_by_profile(world,u.Vector(x,y,74),u.Vector(x,y,-40),
        capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
    data=hit.to_dict() if hit else {}
    assert hit and not data['initial_overlap'] and data['impact_normal'].z>.65, (
        'Unsupported fixture',x,y,{k:str(v) for k,v in data.items()})
    return u.Vector(x,y,data['location'].z+2.2)


def mark_parts(cat):
    return [c.get_name() for c in cat.get_components_by_class(u.SceneComponent)
            if 'CatrunMarkOrb' in c.get_name() or 'CatrunMarkLight' in c.get_name()]


def set_up_mark(world,cat):
    # Place the pawn outside the qualified half of the trigger. Touch-radius sight still uses actual LOS.
    target=ground(world,cat,101.,-30.)
    cat.set_actor_location_and_rotation(target,u.Rotator(yaw=-90),False,True)
    candles=u.GameplayStatics.get_all_actors_of_class(world,u.CatrunCandle)
    candle=min(candles,key=lambda a:(a.get_actor_location()-target).length())
    if 'candle_pose' not in FIX:
        FIX['candle_pose']=candle.get_actor_transform()
        FIX['candle_name']=candle.get_name()
    else:
        candle=next(a for a in candles if a.get_name()==FIX['candle_name'])
    candle.set_actor_location_and_rotation(u.Vector(target.x+43,target.y,target.z-24),u.Rotator(yaw=180),False,True)
    armors=u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor)
    # The map already places an armor in call range of this checkpoint. Let the actual mark
    # subsystem make its selection before it has a chance to move in response to the call.
    armor=min(armors,key=lambda a:(a.get_actor_location()-target).length())
    FIX['armor_name']=armor.get_name()
    if S['pass']==1:
        FIX['armor_pose']=armor.get_actor_transform()
    start=armor.get_actor_location()
    S.setdefault('fixtures',[]).append({'pass':S['pass'],'candle':candle.get_name(),'armor':armor.get_name(),
                                        'cat_start':str(target),'armor_start':str(start)})


def release_candle(world):
    candle=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunCandle) if a.get_name()==FIX['candle_name'])
    candle.set_actor_transform(FIX['candle_pose'],False,True)


def enter(world,cat):
    target=ground(world,cat,101.,-85.)
    cat.set_actor_location_and_rotation(target,u.Rotator(yaw=-90),False,True)


def check_local_door(player,door,pc):
    seq=player.get_sequence()
    bindings=seq.get_bindings()
    original,=[b for b in bindings if 'CatrunDepartureRearDoor' in map(str,b.get_binding_tags())]
    proxy,=[b for b in bindings if b.get_name()=='DepartureRearDoorProxy']
    assert list(player.get_bound_objects(seq.get_binding_id(original)))==[door]
    clone,=player.get_bound_objects(seq.get_binding_id(proxy))
    local=pc.get_path_name().split(':')[0]
    assert door.get_path_name().split(':')[0]==local and clone.get_path_name().split(':')[0]==local,(
        pc.get_path_name(),door.get_path_name(),clone.get_path_name())
    assert str(door.static_mesh_component.get_collision_profile_name())==S['door_collision']
    assert str(clone.static_mesh_component.get_collision_profile_name())=='NoCollision'
    return {'original':door.get_path_name(),'proxy':clone.get_path_name(),'proxy_yaw':clone.get_actor_rotation().yaw}


def tick(_dt):
    try:
        now=time.monotonic()
        phase=S['phase']
        if phase=='shutdown':
            if not ED.get_game_world() and now-S['changed']>1:
                u.unregister_slate_post_tick_callback(S['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        if now-S['started']>(75 if MIRROR else 225):
            finish('Timeout in '+phase)
            return
        world=ED.get_game_world()
        if not world:
            return
        pc=u.GameplayStatics.get_player_controller(world,0)
        cat=u.GameplayStatics.get_player_pawn(world,0)
        if not pc or not cat:
            return
        if world.get_name().endswith('Stage2'):
            assert phase=='complete_portal' and S.get('played_to_end') and u.CatrunLevelFlowLibrary.is_stage2_portal_arrival(world)
            finish()
            return
        assert u.GameplayStatics.get_current_level_name(world,True)==MAP.rsplit('/',1)[1],world.get_path_name()
        director=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunStageExit) if 'CatrunAuthoredStage1Exit' in map(str,a.tags))
        lease=director.get_editor_property('ExitTransition')
        playing=director.get_editor_property('Playing')
        player=director.get_editor_property('SequencePlayer')
        frame=player.get_current_time().time.frame_number.value if playing and player else -1
        marked=mark_parts(cat)
        door=director.get_editor_property('DepartureRearDoor')
        row={'phase':phase,'pass':S['pass'],'frame':frame,'cat':str(cat.get_actor_location()),
             'mark_parts':marked,'leased':lease.has_exit_lease(),'playing':playing,
             'door_hidden':door.get_editor_property('hidden'),'move_ignored':pc.is_move_input_ignored(),
             'look_ignored':pc.is_look_input_ignored(),'suspended':u.CatrunPuzzleSuspension.is_suspended(world),
             'view':pc.get_view_target().get_name() if pc.get_view_target() else None}
        if playing or now-S.get('last_sample',0)>.15:
            S['samples'].append(row)
            S['last_sample']=now
        if phase=='ready':
            if now-S['started']<4 or row['move_ignored'] or row['suspended'] or cat.get_component_by_class(u.CharacterMovementComponent).movement_mode!=u.MovementMode.MOVE_WALKING:
                return
            S['gameplay_view']=row['view']
            S['door_collision']=str(door.static_mesh_component.get_collision_profile_name())
            # Keep real candle LOS, mark calls and armor pursuit active across rejected entry.
            # The nearby follower can start its independent capture camera during rearm.
            S['no_capture_before']=u.CatrunUserSettings.is_no_armor_capture_enabled()
            u.CatrunUserSettings.set_no_armor_capture_enabled(True)
            assert u.CatrunUserSettings.is_no_armor_capture_enabled()
            set_up_mark(world,cat)
            next_phase('detect')
        elif phase=='detect':
            armor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor) if a.get_name()==FIX['armor_name'])
            candle=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunCandle) if a.get_name()==FIX['candle_name'])
            if len(marked)!=2 or not candle.is_tracking_cat() or (not MIRROR and not armor.has_destination()):
                return
            S['fixtures'][-1].update(confirmed_parts=marked,armor_action=str(armor.get_action()),armor_has_destination=armor.has_destination())
            release_candle(world)
            S['released_candle_at']=u.GameplayStatics.get_time_seconds(world)
            next_phase('relocated_candle')
        elif phase=='relocated_candle':
            # Allow normal candle ticks to move its sight fan back before hostile suspension begins.
            if u.GameplayStatics.get_time_seconds(world)-S['released_candle_at']<.15:
                return
            assert len(marked)==2,row
            if MIRROR:
                enter(world,cat)
                next_phase('abort_portal')
            elif S['pass']==1:
                pc.set_ignore_move_input(True)
                enter(world,cat)
                next_phase('denied')
            else:
                enter(world,cat)
                next_phase('complete_portal')
        elif phase=='denied' and now-S['changed']>.12:
            assert len(marked)==2 and not playing and not row['leased'],row
            pc.set_ignore_move_input(False)
            # Move past the outer overlap, then walk the short seam-free interior checkpoint on re-entry.
            cat.set_actor_location(ground(world,cat,101.,-20.),False,True)
            next_phase('rearm')
        elif phase=='rearm' and now-S['changed']>.16:
            assert len(marked)==2 and not row['move_ignored'],row
            enter(world,cat)
            next_phase('abort_portal')
        elif phase in ('abort_portal','complete_portal') and playing:
            assert not marked and row['leased'] and row['suspended'] and row['move_ignored'] and row['look_ignored'],row
            if frame>=2:
                assert row['door_hidden'] and player.get_active_camera_component(),row
            if phase=='abort_portal' and frame>=65:
                S['evaluated_map_door']=check_local_door(player,door,pc)
                director.call_method('AbortPortal')
                next_phase('aborted')
            elif phase=='complete_portal' and frame>=551:
                S['played_to_end']=True
        elif phase=='aborted' and now-S['changed']>.25:
            assert not marked and not playing and not row['leased'] and not row['suspended'],row
            assert not row['move_ignored'] and not row['look_ignored'] and not row['door_hidden'] and row['view']==S['gameplay_view'],row
            assert str(door.static_mesh_component.get_collision_profile_name())==S['door_collision']
            if MIRROR:
                finish()
                return
            armor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor) if a.get_name()==FIX['armor_name'])
            pose=FIX['armor_pose']
            S['between_scenarios']={'armor':armor.get_name(),'from':str(armor.get_actor_location()),'original':str(pose.translation)}
            assert armor.teleport(pose.translation,pose.rotation.rotator()),S['between_scenarios']
            S['between_scenarios']['restored']=str(armor.get_actor_location())
            assert (armor.get_actor_location()-pose.translation).length()<1.,S['between_scenarios']
            S['pass']=2
            set_up_mark(world,cat)
            next_phase('detect')
        if now-S.get('last_persist',0)>2:
            persist()
            S['last_persist']=now
    except Exception:
        finish(traceback.format_exc())


assert not ED.get_game_world() and LEVEL.load_level(MAP)
S['handle']=u.register_slate_post_tick_callback(tick)
LEVEL.editor_request_begin_play()
print('CATRUN_DEPARTURE_PIE_START',str(OUT))
