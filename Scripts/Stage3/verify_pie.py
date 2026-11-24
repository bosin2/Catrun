"""Actual saved Stage3 in isolated offscreen PIE. Test positions are transient.

NPC motion is observed first, then disabled in this process for deterministic
puzzle fixtures. This is not a manual difficulty or full playthrough assessment.
"""
import json,time,traceback
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3Integration20261125/PIE';OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem);GS=u.GameplayStatics;SL=u.SystemLibrary
SYS=u.load_object(None,'/Script/Engine.Default__SubsystemBlueprintLibrary')
S={'phase':'startup','started':time.monotonic(),'changed':time.monotonic(),'checks':[],'scope':__doc__}
S['command_line']=SL.get_command_line()
def persist(): (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
def phase(name):S['phase']=name;S['changed']=time.monotonic();persist()
def check(name,ok,detail=None):
    S['checks'].append({'name':name,'passed':bool(ok),'detail':detail});persist()
    assert ok,(name,detail)
def finish(error=None):
    S['success']=not error;S['error']=error;phase('shutdown')
    if ED.get_game_world():LE.editor_request_end_play()
def xyz(v):return [v.x,v.y,v.z]
def actors(w,cls):return list(GS.get_all_actors_of_class(w,cls))
def flow(w):return SYS.call_method('GetWorldSubsystem',args=(w,u.CatrunLevelFlowSubsystem.static_class()))
def move(cat,x,y):
    cm=cat.get_component_by_class(u.CharacterMovementComponent);cm.stop_movement_immediately()
    z=cat.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height()+.25
    cat.set_actor_location(u.Vector(x,y,z),False,True);cm.set_movement_mode(u.MovementMode.MOVE_WALKING)
def shot(w,name):SL.execute_console_command(w,'HighResShot 1280x720 filename="'+str(OUT/(name+'.png'))+'"')
def step(w):
    cat=GS.get_player_character(w,0)
    if not cat:return
    p=S['phase'];game=GS.get_time_seconds(w)
    if p=='observe' and game!=S.get('last_perf_game'):
        S.setdefault('observed_frame_ms',[]).append(GS.get_world_delta_seconds(w)*1000)
        S['last_perf_game']=game
    if p=='startup':
        if game<2 or not flow(w):return
        clock=flow(w).get_stage_clock_state()
        check('Stage3 live timer',clock.get_editor_property('bTimed') and clock.get_editor_property('RemainingSeconds')>0)
        S['clock0']=clock.get_editor_property('RemainingSeconds');S['game0']=game
        S['npc0']={a.get_actor_label():xyz(a.get_actor_location()) for a in actors(w,u.CatrunArmor)+actors(w,u.CatrunCandle)}
        S['cat_start']=xyz(cat.get_actor_location());shot(w,'Entrance');phase('observe');return
    if p=='observe':
        if game-S['game0']<6:return
        check('Timer advances in real game time',flow(w).get_stage_clock_state().get_editor_property('RemainingSeconds')<S['clock0']-1)
        moved={a.get_actor_label():(a.get_actor_location()-u.Vector(*S['npc0'][a.get_actor_label()])).length() for a in actors(w,u.CatrunArmor)+actors(w,u.CatrunCandle)}
        check('Patrols move',sum(v>5 for v in moved.values())>=3,moved)
        check('All three patrolling candles move',sum(v>5 for k,v in moved.items() if 'Candle' in k)==3,moved)
        for a in actors(w,u.CatrunArmor)+actors(w,u.CatrunCandle):
            a.set_actor_tick_enabled(False);a.set_actor_enable_collision(False)
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        phase('push1');return
    puzzle=actors(w,u.CatrunStatuePuzzle)[0];director=actors(w,u.CatrunStage3Objectives)[0]
    links=puzzle.get_editor_property('Links')
    if p in ['push1','push2']:
        index=0 if p=='push1' else 1;link=links[index];statue=link.get_editor_property('Statue')
        if link.get_editor_property('bPressed'):
            check(p+' seated through native pushes',True)
            if index==0:phase('wait_d1')
            else:
                check('P2 alone leaves D2 closed',not link.get_editor_property('bCompleted') and abs(link.get_editor_property('GateOffset'))<.1)
                S['device']=0;phase('device_position')
            return
        for _ in range(8):
            pos=statue.get_actor_location();move(cat,pos.x,pos.y-85)
            if not puzzle.try_push_statue(index,cat,u.Vector(0,1,0),.05):break
        return
    if p=='wait_d1':
        if not links[0].get_editor_property('bCompleted') or str(puzzle.get_editor_property('Reveal').get_editor_property('Phase')).find('INACTIVE')<0:return
        check('D1 fully recessed',links[0].get_editor_property('GateOffset')<=-280)
        phase('push2');return
    if p=='device_position':
        i=S['device'];d=director.get_editor_property('Devices')[i];h=d.get_editor_property('Housing').get_actor_location()
        move(cat,h.x,h.y+60);check('Device'+str(i+1)+' rejects rear interaction',not director.can_release(i,cat))
        move(cat,h.x-10,h.y-70);phase('device_release');return
    if p=='device_release':
        if time.monotonic()-S['changed']<.2:return
        i=S['device'];check('Device'+str(i+1)+' reachable from front',director.can_release(i,cat))
        S['original_anim_class']=cat.get_component_by_class(u.SkeletalMeshComponent).get_editor_property('anim_class').get_path_name()
        check('Device'+str(i+1)+' activates',director.try_release(i,cat))
        check('Device'+str(i+1)+' rejects concurrent activation',not director.try_release(i,cat))
        check('Activation waits for physical pull',not director.get_editor_property('Devices')[i].get_editor_property('bReleased'))
        S['animation_samples']=[];phase('device_playing');return
    if p=='device_playing':
        i=S['device'];mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
        if i==0 and not S.get('interruption_checked') and mesh.get_position()>.35:
            mesh.set_anim_instance_class(u.load_object(None,S['original_anim_class']))
            S['interruption_checked']=True;phase('interrupted');return
        if i==0 and S.get('interruption_checked') and not S.get('pause_checked') and mesh.get_position()>.5:
            S['paused_position']=mesh.get_position();GS.set_game_paused(w,True);phase('paused_clip');return
        if director.get_editor_property('ActiveDevice')!=-1:
            single=mesh.get_anim_instance()
            if isinstance(single,u.AnimSingleNodeInstance):
                if i==0 and S.get('pause_checked'):
                    for key,threshold in [('Contact',.85),('Pull',1.5)]:
                        if mesh.get_position()>=threshold and not S.get('shot_'+key):
                            shot(w,key);S['shot_'+key]=True
                S['animation_samples'].append({'time':mesh.get_position(),'head':xyz(mesh.get_socket_location('head')),
                    'ring':xyz(director.get_editor_property('Devices')[i].get_editor_property('Ring').get_actor_location())})
            return
        check('Device'+str(i+1)+' animation sampled',len(S['animation_samples'])>10,len(S['animation_samples']))
        check('Device'+str(i+1)+' pull commits once',director.get_editor_property('Devices')[i].get_editor_property('bReleased'))
        check('Device'+str(i+1)+' cannot activate twice',not director.try_release(i,cat))
        check('Device'+str(i+1)+' restores movement',cat.get_component_by_class(u.CharacterMovementComponent).movement_mode==u.MovementMode.MOVE_WALKING)
        check('Device'+str(i+1)+' restores action availability',not cat.get_component_by_class(u.CatrunBasketInteractionComponent).get_editor_property('Busy'))
        (OUT/f'Device{i+1}_motion.json').write_text(json.dumps(S['animation_samples'],indent=2),encoding='utf8')
        if i<2:
            check('D2 stays locked until all devices',not director.all_released() and abs(links[1].get_editor_property('GateOffset'))<.1)
            S['device']+=1;phase('device_position')
        else:phase('wait_d2')
        return
    if p=='interrupted':
        if director.get_editor_property('ActiveDevice')!=-1:return
        check('Interrupted pull does not commit',not director.get_editor_property('Devices')[0].get_editor_property('bReleased'))
        check('Animation takeover restores movement',cat.get_component_by_class(u.CharacterMovementComponent).movement_mode==u.MovementMode.MOVE_WALKING)
        check('Animation takeover releases input',not GS.get_player_controller(w,0).is_move_input_ignored())
        phase('device_position');return
    if p=='paused_clip':
        if time.monotonic()-S['changed']<.6:return
        mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
        check('Pause freezes interaction animation',abs(mesh.get_position()-S['paused_position'])<.001)
        GS.set_game_paused(w,False);S['pause_checked']=True;phase('device_playing');return
    if p=='wait_d2':
        if not links[1].get_editor_property('bCompleted') or str(puzzle.get_editor_property('Reveal').get_editor_property('Phase')).find('INACTIVE')<0:return
        check('All three releases and P2 open D2',director.all_released() and links[1].get_editor_property('GateOffset')<=-280)
        move(cat,-200,3720);phase('final_gate');return
    if p=='final_gate':
        if time.monotonic()-S['changed']<5:return
        check('Final gate opens',director.get_editor_property('bFinalGateOpen'))
        l=director.get_editor_property('FinalLeafLeft').get_actor_location();r=director.get_editor_property('FinalLeafRight').get_actor_location()
        check('Final gate clears 600 cm passage',abs(r.x-l.x)>=619,{'left':xyz(l),'right':xyz(r)})
        shot(w,'GateHall');phase('finish_wait');return
    if p=='finish_wait' and time.monotonic()-S['changed']>3:
        S['exit_walk_start']=xyz(cat.get_actor_location());phase('walk_exit');return
    if p=='walk_exit':
        if flow(w).get_editor_property('bStageComplete'):
            check('Physical walk through final gate completes Stage3',cat.get_actor_location().y>4090,xyz(cat.get_actor_location()))
            shot(w,'Completion');phase('complete_wait');return
        cat.add_movement_input(u.Vector(0,1,0),1.,False);return
    if p=='complete_wait' and time.monotonic()-S['changed']>2:finish()
def tick(_dt):
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>.5:
                u.unregister_slate_post_tick_callback(S['handle']);SL.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        assert time.monotonic()-S['started']<600,'Total runtime timeout'
        assert time.monotonic()-S['changed']<120,('Phase timeout',S['phase'])
        w=ED.get_game_world()
        if w:step(w)
    except Exception:finish(traceback.format_exc())
assert '-SaveToUserDir' in SL.get_command_line()
S['handle']=u.register_slate_post_tick_callback(tick)
try:
    assert LE.load_level('/Game/Maps/Stage3');LE.editor_request_begin_play()
except Exception:finish(traceback.format_exc())
