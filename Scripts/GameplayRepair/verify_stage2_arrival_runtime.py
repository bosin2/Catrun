"""Offscreen PIE: real Stage1 portal overlap, Stage2 arrival and recovery.

Run in a fresh normal editor process with -RenderOffscreen, not a commandlet.
UE 5.8's editor BoxComponent show-flag proxy currently requires -onethread here.
Disable foreground CPU throttling only for this process via the EditorSettings
command-line override, so readiness does not race the first simulated frame.
The test places the pawn at a clear exit checkpoint; it is not manual traversal.
No map/asset saves. Root must preserve the user's save/settings around this run.
"""
import datetime
import hashlib
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

OUT=Path(u.Paths.project_saved_dir()).resolve()/'PresentationFix20261119/Stage2ArrivalRuntime'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(parents=True,exist_ok=False)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ED.get_game_world()
if ED.get_editor_world().get_path_name().split('.')[0]!='/Game/Maps/Stage1':
    assert LEVEL.load_level('/Game/Maps/Stage1')
STATE={'start':time.monotonic(),'phase':'stage1','samples':[],'events':[],
       'scope':'Offscreen PIE game backbuffer; frame images exclude Slate overlays. Widget visibility is recorded separately.'}
SHOT_WINDOWS=(('portal',0,17),('emergence',23,54),('landing',57,82),('walk',89,199),
              ('face',200,229),('statue',230,239),('pan',258,278),('plate',295,305),
              ('face-return',306,323),('return',350,430),('blend',449,498))


def persist(filename,checkpoint):
    STATE['last_checkpoint']={'name':checkpoint,'elapsed':time.monotonic()-STATE['start']}
    target=OUT/filename
    temporary=target.with_suffix('.partial')
    temporary.write_text(json.dumps({k:v for k,v in STATE.items() if k!='handle'},indent=2),encoding='utf8')
    temporary.replace(target)


def advance(phase):
    STATE.update(phase=phase,changed=time.monotonic())
    STATE['events'].append({'phase':phase,'elapsed':time.monotonic()-STATE['start']})
    persist('progress.json','phase '+phase)


def finish(error=None):
    files=sorted(p.name for p in OUT.glob('View_*.png'))
    STATE['viewport_images']=files
    if error is None:
        missing=[r['shot'] for r in STATE.get('viewport_frames',[]) if not any(
            name.startswith(r['shot']) for name in files)]
        if missing: error='Missing viewport captures: '+str(missing[:20])
    if error is None:
        hashes={}
        for name,_,_ in SHOT_WINDOWS:
            stem=STATE['shot_'+name]['requested_image']
            file=next(OUT/f for f in files if f.startswith(stem))
            with file.open('rb') as source:
                hashes[name]=hashlib.file_digest(source,'sha256').hexdigest()
        STATE['shot_file_hashes']=hashes
        if len({hashes[k] for k in ('portal','walk','face','statue','plate','face-return')})!=6:
            error='Repeated backbuffer at distinct Stage2 camera cuts; inspect viewport source'
    STATE['success']=error is None
    STATE['error']=error
    persist('report.json','finished' if error is None else 'failure')
    LEVEL.editor_request_end_play()
    STATE['phase']='shutdown'; STATE['changed']=time.monotonic()
    print('STAGE2_ARRIVAL_RUNTIME_DONE',error,str(OUT/'report.json'))


def props(actor,*names):
    return {n:actor.get_editor_property(n) for n in names}


def verify_spawned_visuals(player,frame):
    sequence=u.load_asset('/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival')
    result={}
    paths=set(STATE.get('spawnable_paths',[]))
    for binding in sequence.get_bindings():
        if not binding.get_object_template(): continue
        actors=player.get_bound_objects(sequence.get_binding_id(binding))
        paths.update(actor.get_path_name() for actor in actors)
        if binding.get_name() not in ('CosmeticCat','ArrivalPortal'): continue
        expected=int(binding.get_name()!='ArrivalPortal' or frame<91)
        assert len(actors)==expected,('Unexpected spawn count',binding.get_name(),frame,len(actors))
        if not expected:
            result[binding.get_name()]=None
            continue
        actor=actors[0]
        primitives=actor.get_components_by_class(u.PrimitiveComponent)
        assert primitives,('No primitives on spawned visual',actor.get_name())
        components=[]
        for item in primitives:
            collision=item.get_collision_enabled()
            overlaps=item.get_editor_property('generate_overlap_events')
            state={'name':item.get_name(),'collision':str(collision),'overlap_events':overlaps,
                   'profile':str(item.get_collision_profile_name()),'query':item.is_query_collision_enabled(),
                   'physics':item.is_physics_collision_enabled(),'simulating':item.is_simulating_physics()}
            assert collision==u.CollisionEnabled.NO_COLLISION and not any(
                state[k] for k in ('overlap_events','query','physics','simulating')), (binding.get_name(),frame,state)
            components.append(state)
        if binding.get_name()=='ArrivalPortal':
            assert not actor.get_actor_enable_collision(),(binding.get_name(),frame,components)
        entry={'actor_collision_flag':actor.get_actor_enable_collision(),'components':components}
        if binding.get_name()=='CosmeticCat':
            entry.update(cat_image_state(actor))
            assert entry['visible']==(frame>=23), (frame,entry)
        else:
            entry['location']=xyz(actor.get_actor_location())
        result[binding.get_name()]=entry
    assert set(result)=={'CosmeticCat','ArrivalPortal'},result
    STATE['spawnable_paths']=sorted(paths)
    return result


def xyz(v):
    return [v.x,v.y,v.z]


def cat_image_state(cat):
    mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
    return {'visible':not cat.get_editor_property('hidden') and mesh.is_visible() and not mesh.get_editor_property('hidden_in_game'),
            'bones':{str(n):xyz(mesh.get_socket_location(n)) for n in ('pelvis','head','ear_tip_L','ear_tip_R','paw_f_l','paw_f_r')}}


def puzzle_state(world):
    names={'S2_Prop_Statue_C','S2_Prop_Plate_C_Plate','S2_Prop_Plate_C_Frame','S2_Gate_11_Bars'}
    result={a.get_actor_label():{'location':xyz(a.get_actor_location()),'hidden':a.get_editor_property('hidden'),
                                 'collision':a.get_actor_enable_collision()}
            for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_actor_label() in names}
    assert set(result)==names,result
    return result


def viewport_frame(world,pc,cat,phase):
    frames=STATE.setdefault('viewport_frames',[])
    stem=f'View_{len(frames):05d}_'
    location=str(OUT/(stem+'.png')).replace('\\','/')
    u.SystemLibrary.execute_console_command(world,f'Shot filename="{location}"',pc)
    entry={'shot':stem,'world':world.get_path_name(),'world_seconds':u.GameplayStatics.get_time_seconds(world),
           'elapsed':time.monotonic()-STATE['start'],'phase':phase}
    frames.append(entry)
    if not pc or not cat:
        return entry
    entry['real']=cat_image_state(cat)
    manager=u.GameplayStatics.get_player_camera_manager(world,0)
    if manager:
        eye=manager.get_camera_location()
        rotation=manager.get_camera_rotation()
        entry['view_pos']=xyz(eye)
        entry['view_rot']=[rotation.pitch,rotation.yaw,rotation.roll]
        forward=u.MathLibrary.get_forward_vector(rotation)
        right=u.MathLibrary.get_right_vector(rotation)
        center=eye+forward*400.
        a=pc.project_world_location_to_screen(center,True)
        b=pc.project_world_location_to_screen(center+right*20.,True)
        far=eye+forward*800.
        c=pc.project_world_location_to_screen(far,True)
        d=pc.project_world_location_to_screen(far+right*20.,True)
        if a and b and c and d and abs(b.x-a.x)>.01 and abs(d.x-c.x)>.01:
            ratio=abs((b.x-a.x)/(d.x-c.x))
            entry['projection_depth_ratio']=ratio
            width=20.*pc.get_viewport_size()[0]/abs(b.x-a.x)
            if abs(ratio-1.)<.025:
                entry.update(projection='orthographic',projected_ortho_width=width)
            elif abs(ratio-2.)<.025:
                entry.update(projection='perspective',projected_horizontal_fov=math.degrees(2.*math.atan(width/800.)))
    entry['visible_widgets']=[str(w.get_class().get_name()) for w in
        u.WidgetLibrary.get_all_widgets_of_class(world,u.UserWidget,True) if w.is_in_viewport() and w.is_visible()]
    return entry


def checkpoint(world,cat):
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    exit_actor=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunStageExit))
    trigger=exit_actor.get_editor_property('Trigger')
    target=u.Vector(101.,-85.,74.)
    STATE['exit_fixture']={'actor':exit_actor.get_path_name(),'center':str(trigger.get_world_location()),
        'extent':str(trigger.get_scaled_box_extent()),
        'minimum_depth':exit_actor.get_editor_property('MinimumInteriorDepth'),
        'use_presentation':exit_actor.get_editor_property('bUseExitTransition')}
    ignored=[cat,exit_actor]
    hit=u.SystemLibrary.capsule_trace_single_by_profile(world,target,u.Vector(101.,-85.,-40.),
        capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
    assert hit,'No floor at exit checkpoint'
    target=hit.to_dict()['location']+u.Vector(0,0,2.2)
    blocked=u.SystemLibrary.capsule_trace_single_by_profile(world,target,target+u.Vector(0,0,.01),capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
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


def capture_checkpoint(world,cat):
    capsule=cat.get_component_by_class(u.CapsuleComponent)
    armors=u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor)
    ordered=sorted(armors,key=lambda a:(cat.get_actor_location()-a.get_actor_location()).length())
    for armor in ordered:
        for x,y in ((65,0),(-65,0),(0,65),(0,-65)):
            p=armor.get_actor_location()+u.Vector(x,y,0)
            hit=u.SystemLibrary.capsule_trace_single_by_profile(world,p+u.Vector(0,0,140),p-u.Vector(0,0,200),
                capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),'Pawn',False,[armor,cat],u.DrawDebugTrace.NONE,False)
            if not hit: continue
            data=hit.to_dict()
            if data['initial_overlap'] or data['impact_normal'].z<.7: continue
            target=data['location']+u.Vector(0,0,2.)
            obstruction=u.SystemLibrary.line_trace_single_by_profile(world, target, u.Vector(
                armor.get_actor_location().x,armor.get_actor_location().y,target.z),'Visibility',False,[armor,cat],u.DrawDebugTrace.NONE,False)
            if obstruction: continue
            cat.set_actor_location(target,False,True)
            return {'armor':armor.get_name(),'pawn_position':xyz(target)}
    raise AssertionError('No supported fixture beside a Stage2 armor')


def tick(delta):
    try:
        now=time.monotonic()
        if STATE['phase']=='shutdown':
            if not ED.get_game_world() and now-STATE['changed']>1:
                u.unregister_slate_post_tick_callback(STATE['handle'])
                u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        if now-STATE['start']>350:
            finish('Timeout in '+STATE['phase']); return
        world=ED.get_game_world()
        if not world:return
        phase=STATE['phase']; stage=world.get_name()
        capture=stage.endswith('Stage2') and phase in ('portal','arrival','one-shot')
        if not capture and now-STATE.get('last',0)<.08: return
        STATE['last']=now
        pc=u.GameplayStatics.get_player_controller(world,0); cat=u.GameplayStatics.get_player_pawn(world,0)
        image=viewport_frame(world,pc,cat,phase) if capture else None
        if not pc or not cat:return
        view=pc.get_view_target()
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
                if directors and directors[0].get_editor_property('Playing'):
                    STATE['departure_played']=True
                    departure=directors[0].get_editor_property('SequencePlayer')
                    if departure and departure.get_current_time().time.frame_number.value>=550:
                        viewport_frame(world,pc,cat,'departure-end')
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
                STATE['initial_puzzle']=puzzle_state(world)
                advance('arrival')
        elif stage.endswith('Stage2'):
            director=next((a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_class().get_name()=='BP_Stage2PortalArrival_C'),None)
            if director: row.update(props(director,'Playing','Started','Finished'))
            player=director.get_editor_property('SequencePlayer') if director else None
            row['sequence_time']=player.get_current_time().time.frame_number.value/30. if player else None
            row['arrival_route']=u.CatrunLevelFlowLibrary.is_stage2_portal_arrival(world)
            if phase=='arrival':
                if row.get('Playing'):
                    STATE['arrival_played']=True
                    assert all(row[k] for k in ('input_ignored','look_ignored','hud_hidden','suspended','hidden')),row
                    f=player.get_current_time().time.frame_number.value
                    image['frame']=f
                    sequence=player.get_sequence()
                    visual_binding=next(b for b in sequence.get_bindings() if b.get_name()=='CosmeticCat')
                    visuals=player.get_bound_objects(sequence.get_binding_id(visual_binding))
                    if visuals:
                        image['visual']=cat_image_state(visuals[0])
                    if 230<=f<=305:
                        assert image.get('projection')=='perspective' and math.dist(image['view_pos'],(1374.7266,3680.1402,33.6515))<.1,(f,image)
                        assert image['visual']['visible'] and not image['real']['visible'],(f,image)
                        pitch,yaw,roll=image['view_rot']
                        fov=image['projected_horizontal_fov']
                        gaze=STATE.setdefault('actual_pov_gaze',[])
                        if gaze:
                            assert yaw<=gaze[-1]['yaw']+.1 and fov<=gaze[-1]['fov']+.1,(f,yaw,fov,gaze[-1])
                        if f<=238 or f>=295:
                            expected=(12.,3.,94.) if f<=238 else (-5.6,-126.7,55.)
                            assert all(abs(v-w)<.3 for v,w in zip((pitch,yaw,fov),expected)),(f,pitch,yaw,fov)
                        gaze.append({'frame':f,'pitch':pitch,'yaw':yaw,'roll':roll,'fov':fov,'image':image['shot']})
                    for shot,first,last in SHOT_WINDOWS:
                        key='shot_'+shot
                        if first<=f<=last and not STATE.get(key):
                            STATE.setdefault('visual_collision_checks',[]).append({'time':row['sequence_time'],'visuals':verify_spawned_visuals(player,f)})
                            STATE[key]={'requested_image':image['shot'],'evaluated_frame':f,'range':[first,last],
                                        'world_seconds':image['world_seconds'],'elapsed':image['elapsed']}
                            persist('progress.json','frame '+shot)
                if row.get('Finished') and now-STATE['changed']>13:
                    assert STATE.get('arrival_played'),'Arrival never played automatically'
                    missed=[(name,a,b) for name,a,b in SHOT_WINDOWS if 'shot_'+name not in STATE]
                    assert not missed,('Missed actual Stage2 viewport windows',missed)
                    assert_playable(world,pc,cat,row)
                    STATE['restored_puzzle']=puzzle_state(world)
                    assert STATE['restored_puzzle']==STATE['initial_puzzle']
                    director.call_method('TryStartArrival')
                    advance('one-shot')
            elif phase=='one-shot' and now-STATE['changed']>1:
                assert row['Finished'] and not row['Playing'],row
                assert_playable(world,pc,cat,row)
                STATE['move_start']=xyz(cat.get_actor_location())
                cat.add_movement_input(u.Vector(0,-1,0),1.,False)
                advance('movement')
            elif phase=='movement':
                if cat.get_actor_location().y>STATE['move_start'][1]-2:
                    cat.add_movement_input(u.Vector(0,-1,0),1.,False)
                    assert now-STATE['changed']<3,'Pawn did not move on restored movement input'
                    return
                STATE['move_end']=xyz(cat.get_actor_location())
                assert u.CatrunLevelFlowLibrary.restart_current_stage(world)
                advance('restart')
            elif phase=='restart' and now-STATE['changed']>4:
                assert not row['Started'] and not row['arrival_route'],row
                assert_playable(world,pc,cat,row)
                assert u.CatrunLevelFlowLibrary.continue_stage(world,'Stage2')
                advance('continue')
            elif phase=='continue' and now-STATE['changed']>4:
                assert not row['Started'] and not row['arrival_route'],row
                assert_playable(world,pc,cat,row)
                STATE['capture_checkpoint']=capture_checkpoint(world,cat)
                advance('capture')
            elif phase=='capture':
                active=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CatrunArmor)
                        if a.get_editor_property('CapturePresentation').is_capturing()]
                if active:
                    STATE['actual_captor']=active[0].get_name()
                    STATE['capture_world_time']=u.GameplayStatics.get_time_seconds(world)
                    advance('capture-reload')
            elif phase=='capture-reload':
                if u.GameplayStatics.get_time_seconds(world)<STATE['capture_world_time']:
                    advance('capture-returned')
            elif phase=='capture-returned' and now-STATE['changed']>4:
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
        if now-STATE.get('last_periodic_write',0)>2.:
            STATE['last_periodic_write']=now
            persist('progress.json','sampling '+STATE['phase'])
    except Exception:
        finish(traceback.format_exc())

STATE['handle']=u.register_slate_post_tick_callback(tick)
LEVEL.editor_request_begin_play()
print('STAGE2_ARRIVAL_RUNTIME_STARTED',str(OUT))
