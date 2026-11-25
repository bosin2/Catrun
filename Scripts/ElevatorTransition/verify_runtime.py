"""Real offscreen PIE, isolated save directory, real F/Space input through PC.
Test-only placement is explicit; no authored packages are saved.
"""
import unreal as u
import json,time,traceback,math,re
from pathlib import Path
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/ElevatorTransition/Runtime'
OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
GS=u.GameplayStatics;SYS=u.load_object(None,'/Script/Engine.Default__SubsystemBlueprintLibrary')
S={'phase':'startup','started':time.monotonic(),'samples':[],'checks':[],'shots':[],'success':False,'run':'revision3_isolation_blend_peek_arrival'}
def vec(v):return list(v.to_tuple())
def persist():
    (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
def state(d):return d.get_transition_state().name
def mesh_pose(cat):
    t=cat.mesh.get_relative_transform();q=t.rotation
    return {'position':vec(t.translation),'scale':vec(t.scale3d),'rotation':[q.x,q.y,q.z,q.w]}
def minimaps(w):
    return u.load_object(None,'/Script/UMG.Default__WidgetBlueprintLibrary').call_method('GetAllWidgetsOfClass',args=(w,u.CatrunMinimapWidget.static_class(),True))
def hidden_components(pc):
    # UE keeps this reflected array protected from Python. Its read-only GETALL
    # console command exports the actual local player's array without mutation.
    w=ED.get_game_world()
    match=re.search(r'-abslog=(?:"([^"]+)"|(\S+))',u.SystemLibrary.get_command_line(),re.I)
    assert match,'Isolated runtime must have its own explicit log'
    log=Path(match.group(1) or match.group(2))
    u.SystemLibrary.execute_console_command(w,'flushlog',pc);start=log.stat().st_size
    u.SystemLibrary.execute_console_command(w,'getall PlayerController HiddenPrimitiveComponents NAME='+pc.get_name()+' OUTER='+w.get_path_name(),pc)
    u.SystemLibrary.execute_console_command(w,'flushlog',pc)
    with log.open('rb') as f:f.seek(start);result=f.read().decode('utf8',errors='replace')
    assert pc.get_path_name()+'.HiddenPrimitiveComponents' in result,result
    (OUT/('hidden_components_'+S['phase']+'.txt')).write_text(result,encoding='utf8')
    return result
def map_hidden(w):return bool(minimaps(w)) and all(x.get_visibility()==u.SlateVisibility.COLLAPSED for x in minimaps(w))
def titles(w):
    cls=u.load_class(None,'/Game/UI/Continue/WBP_StageTitle.WBP_StageTitle_C')
    return u.load_object(None,'/Script/UMG.Default__WidgetBlueprintLibrary').call_method('GetAllWidgetsOfClass',args=(w,cls,True))
def clock(w):
    f=SYS.call_method('GetWorldSubsystem',args=(w,u.CatrunLevelFlowSubsystem.static_class()))
    c=f.get_stage_clock_state()
    return {k:c.get_editor_property(k) for k in ['RemainingSeconds','BudgetSeconds','bRunning','bTimed']}
def check(name,value,data=None):
    S['checks'].append({'name':name,'passed':bool(value),'data':data});persist();assert value,(name,data)
def advance(p):S['phase']=p;S['changed']=time.monotonic();persist()
def shot(w,name):
    if name in S['shots']:return
    S['shots'].append(name)
    ui='' if name.startswith('07') else ' showui'
    u.SystemLibrary.execute_console_command(w,'Shot'+ui+' filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"',GS.get_player_controller(w,0))
def key(w,k,down):
    u.SystemLibrary.execute_console_command(w,'Catrun.Basket.TestKey '+k+(' down' if down else ' up'))
def place(cat,p):
    cat.character_movement.stop_movement_immediately();cat.set_actor_location(u.Vector(*p),False,True)
def snap(w,cat,d):
    pc=GS.get_player_controller(w,0);cam=GS.get_player_camera_manager(w,0)
    return {'map':w.get_name(),'phase':S['phase'],'state':state(d),'timeline':d.get_timeline_seconds(),
        'clip':d.get_active_clip_index(),'cat':vec(cat.get_actor_location()),'mesh':vec(cat.mesh.get_world_location()),
        'ignored':pc.is_move_input_ignored(),'view':pc.get_view_target().get_name(),
        'camera':vec(cam.get_camera_location()),'clock':clock(w),'weight':{'offset':d.cabin_weight.get_current_offset(),'target':d.cabin_weight.get_target_offset(),'mass':d.cabin_weight.get_supported_mass_kg()},'title_visible':bool(titles(w))}
def finish(error=None):
    S.update(success=error is None,error=error);advance('shutdown')
    if ED.get_game_world():GS.set_game_paused(ED.get_game_world(),False);LE.editor_request_end_play()
def tick(dt):
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>1:
                u.unregister_slate_post_tick_callback(S['handle'])
                if S['success']:u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
                else:print('E23_TEST_FAILED_RETAINED_EDITOR',S['error'])
            return
        assert time.monotonic()-S['started']<360,'Test timeout'
        w=ED.get_game_world()
        if not w:return
        cat=GS.get_player_character(w,0);pc=GS.get_player_controller(w,0)
        if not cat or not pc:return
        ds=GS.get_all_actors_of_class(w,u.CatrunElevatorTransition)
        if not ds:return
        d=ds[0];phase=S['phase'];game=GS.get_time_seconds(w)
        if phase=='startup':
            if game<6 or pc.is_move_input_ignored():return
            S['initial_mesh_relative']=mesh_pose(cat)
            S['outside_minimap']=[x.get_visibility().name for x in minimaps(w)]
            S['outside_start']=vec(cat.get_actor_location())
            place(cat,(715,-200,26.2));S['at']=game;advance('corridor');return
        if phase=='corridor':
            if game-S['at']<.7:return
            check('corridor_does_not_auto_travel',state(d)=='WAITING' and 'Stage2' in w.get_name())
            check('corridor_walk_input_available',not pc.is_move_input_ignored())
            corridor=[a for a in GS.get_all_actors_of_class(w,u.StaticMeshActor) if a.get_name().startswith('') and 'Stage2ExitCorridor' in map(str,a.tags)]
            check('cat_stays_visible',not cat.get_editor_property('hidden') and cat.mesh.is_visible())
            check('corridor_minimap_hidden_before_F',map_hidden(w))
            shot(w,'01_Corridor');S['at']=game;advance('corridor_capture');return
        if phase=='corridor_capture':
            if game-S['at']<.3:return
            place(cat,(715,-700,26.2));S['at']=game;advance('warehouse');return
        if phase=='warehouse':
            if game-S['at']<1:return
            check('warehouse_free_walk',not pc.is_move_input_ignored() and state(d)=='WAITING')
            check('warehouse_minimap_hidden_before_F',map_hidden(w))
            shot(w,'02_Warehouse');S['at']=game;advance('warehouse_capture');return
        if phase=='warehouse_capture':
            if game-S['at']<.3:return
            place(cat,(715,-1530,26.2));S['at']=game;advance('enter_cabin');return
        if phase=='enter_cabin':
            if game-S['at']<1:return
            check('entry_waits_for_interact',state(d)=='WAITING' and not pc.is_move_input_ignored())
            hidden=hidden_components(pc)
            room=[a for a in d.hide_during_ascent if isinstance(a,u.StaticMeshActor) and not a.get_actor_label().startswith(('E23_Lift_','E23_Guide_'))]
            check('entry_hides_room_before_F',bool(room) and all(a.static_mesh_component.get_path_name() in hidden for a in room))
            check('entry_keeps_cat_and_cabin_visible',cat.mesh.get_path_name() not in hidden and all(a.static_mesh_component.get_path_name() not in hidden for a in d.cabin_actors if isinstance(a,u.StaticMeshActor)))
            check('isolated_floor_retains_collision',all(a.get_actor_enable_collision() for a in room if 'Floor' in a.get_actor_label()))
            check('entry_minimap_hidden_before_F',map_hidden(w));shot(w,'03_CabinBeforeF')
            key(w,'Tab',True);S['at']=game;advance('entry_tab');return
        if phase=='entry_tab':
            if game-S['at']<.35:return
            key(w,'Tab',False);check('PC_Tab_keeps_zone_minimap_collapsed',map_hidden(w))
            place(cat,S['outside_start']);S['at']=game;advance('zone_leave');return
        if phase=='zone_leave':
            if game-S['at']<.7:return
            check('leaving_zone_restores_minimap',[x.get_visibility().name for x in minimaps(w)]==S['outside_minimap'])
            room=[a for a in d.hide_during_ascent if isinstance(a,u.StaticMeshActor)]
            restored=hidden_components(pc)
            check('leaving_cabin_restores_scene',all(a.static_mesh_component.get_path_name() not in restored for a in room))
            place(cat,(715,-1530,26.2));S['at']=game;advance('reenter_for_F');return
        if phase=='reenter_for_F':
            if game-S['at']<.7:return
            S['minimap_before']=[x.get_visibility().name for x in minimaps(w)]
            S['f_camera_start']=vec(GS.get_player_camera_manager(w,0).get_camera_location())
            S['f_blend_positions']=[]
            S['clock_before']=clock(w)['RemainingSeconds'];key(w,'F',True);S['at']=game;advance('cancel_run');return
        if phase=='cancel_run':
            key(w,'F',False)
            if state(d)=='ALIGNING':
                S['f_blend_positions'].append(vec(GS.get_player_camera_manager(w,0).get_camera_location()))
                if game-S['at']>.4 and not S.get('f_blend_checked'):
                    current=vec(GS.get_player_camera_manager(w,0).get_camera_location());target=vec(d.front_camera.get_actor_location())
                    check('F_camera_moves_through_intermediate_view',math.dist(current,S['f_camera_start'])>10 and math.dist(current,target)>10)
                    check('jump_waits_for_camera_blend',d.get_active_clip_index()==-1)
                    check('F_blend_locks_input_immediately',pc.is_move_input_ignored())
                    shot(w,'03b_FCameraBlend');S['f_blend_checked']=True
            if game-S['at']>.7 and not S.get('f_checked'):
                check('F_starts_cinematic',state(d) in ('ALIGNING','DEPARTURE'));S['f_checked']=True
            if d.get_active_clip_index()==2:
                check('F_blend_observed',S.get('f_blend_checked') and len(S['f_blend_positions'])>8)
                check('cinematic_locks_input',pc.is_move_input_ignored())
                check('cinematic_hides_minimap',all(x.get_visibility()==u.SlateVisibility.COLLAPSED for x in minimaps(w)))
                check('cinematic_freezes_stage_clock',abs(clock(w)['RemainingSeconds']-S['clock_before'])<.3)
                d.cancel_transition();S['at']=game;advance('cancel_check')
            return
        if phase=='cancel_check':
            if game-S['at']<.6:return
            check('cancel_returns_waiting',state(d)=='WAITING')
            check('cancel_restores_controls',not pc.is_move_input_ignored())
            check('cancel_restores_minimap',[x.get_visibility().name for x in minimaps(w)]==S['minimap_before'])
            check('cancel_restores_mesh_transform',mesh_pose(cat)==S['initial_mesh_relative'])
            key(w,'F',True);S['at']=game;advance('normal');return
        if phase=='pause_hold':
            if time.monotonic()-S['changed']<.6:return
            check('pause_freezes_cinematic',abs(d.get_timeline_seconds()-S['paused_timeline'])<.001)
            GS.set_game_paused(w,False);advance('normal');return
        if phase=='normal':
            key(w,'F',False)
            if 'Stage3' in w.get_name():
                check('below_face_shot_holds_three_seconds',2.8<S.get('peek_last',0)-S.get('peek_first',0)<3.7)
                check('below_camera_stays_on_floor',S.get('peek_max_lens_drift',999)<.01)
                check('below_shot_tracks_rising_face',S.get('peek_last_eye_z',0)-S.get('peek_first_eye_z',0)>70)
                check('below_camera_keeps_face_centered',S.get('peek_max_aim_error_degrees',999)<6.0,{'max_aim_error_degrees':S.get('peek_max_aim_error_degrees')})
                advance('arrival');return
            row=snap(w,cat,d)
            if not S['samples'] or row['timeline']-S['samples'][-1]['timeline']>.12:S['samples'].append(row)
            idx=d.get_active_clip_index();timeline=d.get_timeline_seconds()
            if idx==1 and not S.get('pause_tested'):
                S['pause_tested']=True;S['paused_timeline']=timeline;GS.set_game_paused(w,True);advance('pause_hold');return
            if idx==0 and timeline>1.45:shot(w,'04_Prepare_Letterbox')
            if idx==2:shot(w,'05_HangPull')
            if idx==4:shot(w,'06_DepartureJolt')
            if idx==5 and 'Below' in pc.get_view_target().get_actor_label():
                lens=vec(d.peek_camera.get_actor_location())
                eye=(cat.mesh.get_socket_location('lid_upper_l_00')+cat.mesh.get_socket_location('lid_upper_r_00'))*.5
                if 'peek_first' not in S:
                    S['peek_first']=game;S['peek_lens']=lens;S['peek_first_eye_z']=eye.z;S['peek_max_lens_drift']=0
                S['peek_last']=game;S['peek_last_eye_z']=eye.z
                S['peek_max_lens_drift']=max(S['peek_max_lens_drift'],math.dist(lens,S['peek_lens']))
                direction=[v-p for v,p in zip(vec(eye),lens)];distance=math.sqrt(sum(v*v for v in direction))
                forward=vec(d.peek_camera.get_actor_forward_vector())
                cosine=sum(v*f for v,f in zip(direction,forward))/max(distance,1e-6)
                S['peek_max_aim_error_degrees']=max(S.get('peek_max_aim_error_degrees',0),math.degrees(math.acos(max(-1,min(1,cosine)))))
                for delay,name in [(.25,'07_PeekFromBelow'),(1.45,'07b_PeekFaceMiddle'),(2.75,'07c_PeekFaceRising')]:
                    if game-S['peek_first']>delay:shot(w,name)
            if idx==6:shot(w,'08_DarkAscent')
            if state(d)=='WAITING' and game-S['at']>2:raise AssertionError('Normal cinematic aborted')
            persist();return
        if phase=='arrival':
            row=snap(w,cat,d);S['samples'].append(row)
            if state(d) in ('ARRIVAL','ARRIVAL_WALK','ARRIVAL_LOOK','ARRIVAL_BLEND'):
                assert not titles(w),'Title shown before cinematic blend completes'
                assert pc.is_move_input_ignored(),'Input released before cinematic completion'
            if state(d)=='ARRIVAL_WALK' and cat.get_actor_location().y<110:shot(w,'12_CarefulStepOff')
            if state(d)=='ARRIVAL_LOOK':
                if 'look_at' not in S:S['look_at']=game
                if game-S['look_at']>.8:shot(w,'13_LookAroundLeft')
                if game-S['look_at']>1.9:shot(w,'13b_LookAroundRight')
            if state(d)=='ARRIVAL_BLEND':shot(w,'14_GameplayBlend')
            if state(d)=='ARRIVAL' and d.get_active_clip_index()==0 and d.get_timeline_seconds()>1.3:shot(w,'09_ArrivalLoaf')
            if state(d)=='ARRIVAL' and d.get_active_clip_index()==1 and d.get_timeline_seconds()>2.9:shot(w,'10_ArrivalStartle')
            if state(d)=='FINISHED':
                check('normal_travel_reaches_Stage3','Stage3' in w.get_name())
                check('arrival_restores_input',not pc.is_move_input_ignored())
                check('arrival_plays_then_finishes',any(x['state']=='ARRIVAL' for x in S['samples']))
                check('arrival_release_position',math.dist(vec(cat.get_actor_location()),vec(d.arrival_release_mark.get_actor_location()))<5)
                check('arrival_walk_look_blend_observed',all(any(x['state']==phase for x in S['samples']) for phase in ['ARRIVAL_WALK','ARRIVAL_LOOK','ARRIVAL_BLEND']))
                walks=[x for x in S['samples'] if x['state']=='ARRIVAL_WALK']
                check('arrival_walk_is_continuous',len(walks)>5 and max(math.dist(a['cat'],b['cat']) for a,b in zip(walks,walks[1:]))<15)
                check('loaded_cabin_sags_during_exit',min(x['weight']['offset'] for x in walks)<-2)
                # Observe the actual support release. At this slow walking speed
                # the first rebound can settle before the cat reaches Y=50.
                first_unloaded=[x for x in walks if x['weight']['mass']==0 and x['weight']['offset']>0]
                check('first_unloading_rebounds',bool(first_unloaded) and max(x['weight']['offset'] for x in first_unloaded)>.05,
                      {'peak':max((x['weight']['offset'] for x in first_unloaded),default=0)})
                S['at']=game;advance('arrival_settle')
            return
        if phase=='arrival_settle':
            if game-S['at']<.65:return
            check('normal_arrival_restores_minimap',bool(minimaps(w)) and [x.get_visibility().name for x in minimaps(w)]==S['outside_minimap'])
            check('stage_title_after_blend',len(titles(w))==1)
            check('stage_title_clears_clock',titles(w)[0].get_editor_property('render_transform').translation.y>=119)
            check('arrival_clock_resumes',clock(w)['bRunning']);shot(w,'11_Stage3Gameplay');S['at']=game;advance('stage3_capture');return
        if phase=='stage3_capture':
            if game-S['at']<.3:return
            S['at']=game;advance('weight_reenter');return
        if phase=='weight_reenter':
            assert game-S['at']<12,'Could not walk back into persistent elevator'
            if cat.get_actor_location().y<155:
                cat.add_movement_input(u.Vector(0,1,0),.3,False);return
            cat.character_movement.stop_movement_immediately();S['at']=game;advance('weight_loaded');return
        if phase=='weight_loaded':
            if game-S['at']<1.5:return
            check('persistent_cabin_accepts_reentry',d.cabin_weight.has_supported_rider(cat))
            check('weight_loaded_sags',d.cabin_weight.get_current_offset()<-2)
            check('loaded_cat_stays_grounded',cat.character_movement.is_moving_on_ground())
            check('moving_floor_carries_cat',abs(cat.get_actor_location().z-26.2-d.cabin_weight.get_current_offset())<.7)
            check('reentry_cutaway_hides',all(a.get_editor_property('hidden') for a in d.cabin_occluders))
            key(w,'F',True);S['at']=game;advance('weight_no_interact');return
        if phase=='weight_no_interact':
            key(w,'F',False)
            if game-S['at']<.2:return
            check('arrival_cabin_has_no_second_interaction',state(d)=='FINISHED' and not pc.is_move_input_ignored())
            shot(w,'15_PersistentCabinLoaded');S['at']=game;S['rebound_peak']=-6;advance('weight_leave');return
        if phase=='weight_leave':
            assert game-S['at']<12,'Could not leave persistent elevator'
            S['rebound_peak']=max(S['rebound_peak'],d.cabin_weight.get_current_offset())
            if cat.get_actor_location().y>20:
                cat.add_movement_input(u.Vector(0,-1,0),.3,False);return
            cat.character_movement.stop_movement_immediately();S['at']=game;advance('weight_empty');return
        if phase=='weight_empty':
            S['rebound_peak']=max(S['rebound_peak'],d.cabin_weight.get_current_offset())
            if game-S['at']<1.8:return
            check('unloaded_cabin_rises_and_settles',abs(d.cabin_weight.get_current_offset())<.15 and S['rebound_peak']>.05,{'offset':d.cabin_weight.get_current_offset(),'peak':S['rebound_peak']})
            check('cabin_floor_persists',all(not a.get_editor_property('hidden') and a.get_actor_enable_collision() for a in d.cabin_weight.support_actors))
            check('weight_does_not_lock_player',not pc.is_move_input_ignored() and cat.character_movement.is_moving_on_ground())
            check('leaving_restores_cabin_panels',all(not a.get_editor_property('hidden') for a in d.cabin_occluders))
            shot(w,'16_PersistentCabinEmpty');S['at']=game;advance('weight_capture');return
        if phase=='weight_capture':
            if game-S['at']<.3:return
            GS.open_level(w,'/Game/Maps/Stage2');advance('skip_setup');return
        if phase=='skip_setup':
            if 'Stage2' not in w.get_name() or game<4 or pc.is_move_input_ignored():return
            place(cat,(715,-1530,26.2));S['at']=game;advance('skip_start');return
        if phase=='skip_start':
            if game-S['at']<1:return
            key(w,'F',True);S['at']=game;advance('skip_run');return
        if phase=='skip_run':
            key(w,'F',False)
            if game-S['at']<1.3:return
            check('reentry_starts',state(d)=='DEPARTURE');key(w,'SpaceBar',True);advance('skip_travel');return
        if phase=='skip_travel':
            key(w,'SpaceBar',False)
            if 'Stage3' not in w.get_name():return
            if state(d) in ('ARRIVAL','ALIGNING'):key(w,'SpaceBar',True);advance('skip_arrival');return
            return
        if phase=='skip_arrival':
            key(w,'SpaceBar',False)
            if state(d)!='FINISHED':return
            check('skip_travel_and_arrival_restore',not pc.is_move_input_ignored());GS.open_level(w,'/Game/Maps/Stage3');advance('direct_stage3');return
        if phase=='direct_stage3':
            if 'Stage3' not in w.get_name() or game<3:return
            check('direct_stage3_does_not_replay',state(d)=='FINISHED' and not pc.is_move_input_ignored())
            check('direct_stage3_keeps_weight_response',d.cabin_weight.is_responding())
            check('direct_stage3_restores_minimap',bool(minimaps(w)) and [x.get_visibility().name for x in minimaps(w)]==S['outside_minimap'])
            finish();return
    except Exception:finish(traceback.format_exc())

assert '-SaveToUserDir' in u.SystemLibrary.get_command_line(),'Use isolated saves'
assert LE.load_level('/Game/Maps/Stage2')
u.SystemLibrary.execute_console_command(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
S['handle']=u.register_slate_post_tick_callback(tick);LE.editor_request_begin_play()
