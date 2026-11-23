"""PIE regression: real candle, denied lease, accepted portal, abort, re-mark and qualifying travel.

Run via -ExecutePythonScript in a normal offscreen editor with isolated user saves/settings.
The script moves PIE-only fixtures near the real trigger. It never saves map or content packages.
"""
import datetime
import json
import math
from pathlib import Path
import sys
import time
import traceback

import unreal as u

sys.path.insert(0,str(Path(u.Paths.project_dir()).resolve()/'Scripts/GameplayRepair'))
import stage1_departure_shots as shots

MIRROR='-catrundeparturemirror' in u.SystemLibrary.get_command_line().lower()
MAP='/Game/Maps/SoundTest_Stage1' if MIRROR else '/Game/Maps/Stage1'
RUN_FOLDER='DepartureMirrorRuntime' if MIRROR else 'DepartureRuntime'
OUT=Path(u.Paths.project_saved_dir()).resolve()/'StageRevision20261123'/RUN_FOLDER/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
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
    # The fixture begins outside the corridor, with an unobstructed candle at touch range.
    target=ground(world,cat,101.,52.)
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
    # Retain the map armor and grid. Start its pursuit far enough away that a normal frame
    # can observe the active trip with capture enabled before it reaches the cat.
    armor=min(armors,key=lambda a:(a.get_actor_location()-target).length())
    FIX['armor_name']=armor.get_name()
    if S['pass']==1:
        FIX['armor_pose']=armor.get_actor_transform()
    origin=FIX['armor_pose'].translation
    assert armor.teleport(u.Vector(130.,290.,origin.z),armor.get_actor_rotation())
    start=armor.get_actor_location()
    assert 180.<(start-target).length()<450.,(start,target)
    S.setdefault('fixtures',[]).append({'pass':S['pass'],'candle':candle.get_name(),'armor':armor.get_name(),
                                        'cat_start':str(target),'armor_start':str(start)})


def armor_state(armor):
    movement=armor.get_component_by_class(u.CharacterMovementComponent)
    return dict(actor=armor.get_name(),action=str(armor.get_action()),seeing=armor.is_seeing_cat(),
                destination=armor.has_destination(),maximum_speed=movement.max_walk_speed,
                walk_speed=armor.get_editor_property('WalkSpeed'),speed_xy=math.hypot(armor.get_velocity().x,armor.get_velocity().y),
                position=list(shots.h.tuple3(armor.get_actor_location())))


def hostiles(world):
    by_name=lambda cls,name:next(a for a in u.GameplayStatics.get_all_actors_of_class(world,cls) if a.get_name()==FIX[name])
    return by_name(u.CatrunArmor,'armor_name'),by_name(u.CatrunCandle,'candle_name')


def real_bell(world,cat,armor):
    manager,=u.GameplayStatics.get_all_actors_of_class(world,u.SoundGridManager)
    bell=cat.get_component_by_class(u.CatrunBellComponent)
    assert bell and bell.try_ring(),'Real cat bell did not emit'
    remaining=manager.get_remaining_budget_at(armor.get_actor_location())
    settings=manager.get_editor_property('Settings')
    total=manager.get_editor_property('PlayerBellBudgetOverride') or settings.get_editor_property('LargeBudget')
    travel=(total-remaining)/settings.get_editor_property('SoundSpeed')
    assert 0.<remaining<total and travel>0,(remaining,total,travel)
    return dict(emission=u.GameplayStatics.get_time_seconds(world),remaining=remaining,total=total,travel=travel,
                cat=str(cat.get_actor_location()),armor=str(armor.get_actor_location()))


def device_control(world,armor):
    # At a different emitter outside the corridor, the same armor must still accept real stimuli.
    manager,=u.GameplayStatics.get_all_actors_of_class(world,u.SoundGridManager)
    sound=u.CatrunSoundEvent()
    sound.set_editor_property('source',u.CatrunSoundSource.DEVICE)
    sound.set_editor_property('kind',u.CatrunSoundKind.DEVICE)
    sound.set_editor_property('size',u.CatrunSoundSize.LARGE)
    sound.set_editor_property('target',u.CatrunSoundTarget.MINION)
    sound.set_editor_property('location',u.Vector(175.,250.,0.))
    sound.set_editor_property('instigator',manager)
    assert manager.emit_sound(sound)
    remaining=manager.get_remaining_budget_at(armor.get_actor_location())
    assert remaining>0
    return dict(remaining=remaining,emission=u.GameplayStatics.get_time_seconds(world),origin=[175,250,0])


def challenge_candle(candle,cat):
    pos=cat.get_actor_location()
    assert candle.set_actor_location_and_rotation(u.Vector(pos.x+43,pos.y,pos.z-24),u.Rotator(yaw=180),False,True)


def assert_forgotten(state,candle,row):
    assert not row['mark_parts'] and not row['suspended'] and not row['leased'] and not row['playing'],row
    assert not u.CatrunUserSettings.is_no_armor_capture_enabled()
    assert not candle.is_tracking_cat() and not state['seeing'] and not state['destination'],(state,row)
    assert abs(state['maximum_speed']-state['walk_speed'])<.05 and state['position'][1]>shots.THRESHOLD_Y,state
    assert state['action'] not in (str(u.ArmorAction.CATCHING),str(u.ArmorAction.WAITING_FOR_CAPTURE)),state


def release_candle(world):
    candle=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunCandle) if a.get_name()==FIX['candle_name'])
    candle.set_actor_transform(FIX['candle_pose'],False,True)


def place(world,cat,x,y):
    cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()
    target=ground(world,cat,x,y)
    assert cat.set_actor_location_and_rotation(target,u.Rotator(yaw=-90),False,True)


def check_local_door(player,door,right,pc,cat):
    seq=player.get_sequence()
    local=pc.get_path_name().split(':')[0]
    for tag,actor in ((shots.DOOR_TAG,door),(shots.RIGHT_TAG,right)):
        binding,=[b for b in seq.get_bindings() if tag in map(str,b.get_binding_tags())]
        assert list(player.get_bound_objects(seq.get_binding_id(binding)))==[actor]
        assert actor.get_path_name().split(':')[0]==local and abs(actor.get_actor_rotation().yaw)<.05
    hits=[]
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    for x in (71.,101.,131.):
        hit=u.SystemLibrary.capsule_trace_single_by_profile(pc,u.Vector(x,65,25.2),u.Vector(x,-75,25.2),
            capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,[cat],u.DrawDebugTrace.NONE,False)
        assert hit and hit.to_dict()['hit_actor'] in (door,right),(x,hit.to_dict() if hit else None)
        hits.append(hit.to_dict()['hit_actor'].get_name())
    return {'left':door.get_path_name(),'right':right.get_path_name(),'capsule_hits':hits}


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
        right=director.get_editor_property('DepartureRearDoorRight')
        row={'leaf_yaws':[a.get_actor_rotation().yaw for a in (door,right)],'phase':phase,'pass':S['pass'],'frame':frame,'cat':str(cat.get_actor_location()),
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
            S['no_capture_before']=u.CatrunUserSettings.is_no_armor_capture_enabled()
            u.CatrunUserSettings.set_no_armor_capture_enabled(False)
            assert not u.CatrunUserSettings.is_no_armor_capture_enabled()
            set_up_mark(world,cat)
            next_phase('detect')
        elif phase=='detect':
            armor,candle=hostiles(world)
            state=armor_state(armor)
            manager,=u.GameplayStatics.get_all_actors_of_class(world,u.SoundGridManager)
            pursues=manager.get_editor_property('bMarkAttractsArmors')
            assert pursues or MIRROR
            if len(marked)!=2 or not candle.is_tracking_cat():
                return
            if pursues:
                if not state['destination'] or abs(state['maximum_speed']-state['walk_speed'])<.05:
                    return
                expected=manager.get_editor_property('Settings').get_editor_property('ArmorRunSpeedMark')
                assert abs(state['maximum_speed']-expected)<.05,state
            assert not row['suspended'] and not u.CatrunUserSettings.is_no_armor_capture_enabled()
            f=S['fixtures'][-1]
            f.update(confirmed_parts=marked,pre_entry=state,mark_attracts=pursues,capture_enabled=True)
            # The wave is emitted outside while real cat recognition is active. Move inside before
            # delayed delivery; a lost event or zero remaining budget fails this fixture.
            f['queued_outside_bell']=real_bell(world,cat,armor)
            place(world,cat,45. if S['pass']==1 else 101.,-91.)
            challenge_candle(candle,cat)
            S['idle_begin']=u.GameplayStatics.get_time_seconds(world)
            next_phase('corridor_idle')
        elif phase in ('corridor_idle','inside_bell','device_control'):
            armor,candle=hostiles(world)
            state=armor_state(armor)
            f=S['fixtures'][-1]
            clock=u.GameplayStatics.get_time_seconds(world)
            elapsed=clock-S['idle_begin']
            if elapsed<.12:
                return
            if phase=='device_control':
                if not state['destination']:
                    return
                assert not state['seeing'] and not marked and not row['suspended'] and not candle.is_tracking_cat(),state
                f['unrelated_device_response']=state
            else:
                assert_forgotten(state,candle,row)
                f.setdefault('post_entry',state)
                if phase=='corridor_idle':
                    wave=f['queued_outside_bell']
                    if elapsed<2.3 or clock<wave['emission']+wave['travel']+.25:
                        return
                    f['after_queued_delivery']=dict(world_time=clock,armor=state)
                    if cat.get_component_by_class(u.CatrunBellComponent).get_cooldown_remaining()>.001:
                        return
                    S.setdefault('idle_without_start',[]).append({'seconds':elapsed,'position':str(cat.get_actor_location())})
                    # Close to the mouth of the physical corridor the baked banquet grid carries
                    # the wave. Both the new bell and the facing candle now have the protected cat as source.
                    place(world,cat,101.,-35.)
                    challenge_candle(candle,cat)
                    f['protected_bell']=real_bell(world,cat,armor)
                    next_phase('inside_bell')
                    return
                wave=f['protected_bell']
                if clock<wave['emission']+wave['travel']+.35:
                    return
                f['after_protected_bell']=dict(world_time=clock,armor=state,candle_tracking=candle.is_tracking_cat())
                if MIRROR or S['pass']==2:
                    f['unrelated_device']=device_control(world,armor)
                    next_phase('device_control')
                    return
            release_candle(world)
            if S['pass']==1 and not MIRROR:
                pc.set_ignore_move_input(True)
                place(world,cat,101.,shots.START_Y-2.)
                next_phase('denied')
            else:
                place(world,cat,101.,shots.THRESHOLD_Y+2.)
                next_phase('walk_to_exit')
        elif phase=='denied' and now-S['changed']>.18:
            assert not marked and not playing and not row['leased'],row
            pc.set_ignore_move_input(False)
            place(world,cat,101.,shots.THRESHOLD_Y+2.)
            next_phase('walk_to_exit')
        elif phase=='walk_to_exit':
            world_time=u.GameplayStatics.get_time_seconds(world)
            y=cat.get_actor_location().y
            if playing:
                assert y<=shots.START_Y+1 and not marked and row['leased'],row
                evidence=S['walk_samples'][-1]
                evidence.update(start_y=y,seconds_threshold_to_presentation=world_time-evidence['threshold_time'])
                assert abs(evidence['seconds_threshold_to_presentation']-2.)<.5,evidence
                next_phase('abort_portal' if S['pass']==1 else 'complete_portal')
            else:
                if y<=shots.THRESHOLD_Y and not S.get('walking_threshold'):
                    S.setdefault('walk_samples',[]).append(dict(threshold_y=y,threshold_time=world_time))
                    S['walking_threshold']=True
                cat.add_movement_input(u.Vector(0,-1,0),1.,False)
                if y<=shots.THRESHOLD_Y-3:
                    assert not marked and not row['suspended'],row
        elif phase in ('abort_portal','complete_portal') and playing:
            assert not marked and row['leased'] and row['suspended'] and row['move_ignored'] and row['look_ignored'],row
            if frame>=2:
                assert not row['door_hidden'] and player.get_active_camera_component(),row
            if phase=='abort_portal' and frame>=65:
                S['evaluated_map_door']=check_local_door(player,door,right,pc,cat)
                director.call_method('AbortPortal')
                next_phase('aborted')
            elif phase=='complete_portal' and frame>=shots.AIR_END:
                S['played_to_end']=True
        elif phase=='aborted' and now-S['changed']>.25:
            assert not marked and not playing and not row['leased'] and not row['suspended'],row
            if not MIRROR and cat.get_component_by_class(u.CatrunBellComponent).get_cooldown_remaining()>.001:
                return
            assert not row['move_ignored'] and not row['look_ignored'] and not row['door_hidden'] and row['view']==S['gameplay_view'],row
            assert str(door.static_mesh_component.get_collision_profile_name())==S['door_collision']
            assert abs(door.get_actor_rotation().yaw+100)<.05 and abs(right.get_actor_rotation().yaw-100)<.05,row
            if MIRROR:
                finish()
                return
            armor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor) if a.get_name()==FIX['armor_name'])
            pose=FIX['armor_pose']
            S['between_scenarios']={'armor':armor.get_name(),'from':str(armor.get_actor_location()),'original':str(pose.translation)}
            assert armor.teleport(pose.translation,pose.rotation.rotator()),S['between_scenarios']
            S['between_scenarios']['restored']=str(armor.get_actor_location())
            assert (armor.get_actor_location()-pose.translation).length()<1.,S['between_scenarios']
            S['walking_threshold']=False
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
