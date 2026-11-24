"""Offscreen real-map input/animation integration. All placements are transient fixtures."""
import unreal as u,json,math,time,traceback,hashlib,re
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();OUT=ROOT/'Saved/BasketIntegration20261125/PIE';OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem);GS=u.GameplayStatics
APPLY=json.loads((ROOT/'Saved/BasketIntegration20261125/apply_report.json').read_text(encoding='utf8'));assert APPLY['success']
S={'phase':'setup','started':time.monotonic(),'map_index':0,'maps':['Stage1','Stage2'],'cases':[],'events':[],'screenshots':[],'scope':'Real saved Stage1/Stage2 in PIE, real F/WASD input injection; cat start positions are transient test fixtures. Armor capture disabled only in this isolated process.'}
KEYS=['W','A','S','D'];DIRS=['F','FR','R','BR','B','BL','L','FL']
def xyz(v):return [round(v.x,4),round(v.y,4),round(v.z,4)]
def persist(file='progress.json'):
    (OUT/file).write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},indent=2,ensure_ascii=False),encoding='utf8')
def phase(name):
    S['phase']=name;S['changed']=time.monotonic();S['events'].append({'phase':name,'wall':S['changed']-S['started']});persist()
def finish(error=None):
    S['success']=not error;S['error']=error;S['final_phase']=S['phase'];phase('shutdown');persist('report.json')
    if ED.get_game_world():LEVEL.editor_request_end_play()
def key(world,key,down):u.SystemLibrary.execute_console_command(world,'Catrun.Basket.TestKey '+key+(' down' if down else ' up'))
def send_interact(world):key(world,'F',True);S['release_f']=time.monotonic()+.08
def namephase(a):return str(a.get_editor_property('BasketPhase')).split('.')[-1].split(':')[0]
def baskets(world):return {a.get_actor_label():a for a in GS.get_all_actors_of_class(world,u.CatrunHideBasket)}
def cloth(a):return a.get_editor_property('ExternalCloth') or next(c for c in a.get_components_by_class(u.SkeletalMeshComponent) if c.get_name()=='BasketCloth')
def asset_name(c):
    anim=c.get_anim_instance()
    return anim.get_animation_asset().get_name() if isinstance(anim,u.AnimSingleNodeInstance) and anim.get_animation_asset() else None
def axes(pc):
    yaw=GS.get_player_camera_manager(pc,0).get_camera_rotation().yaw;r=math.radians(yaw)
    return yaw,{'W':[math.cos(r),math.sin(r),0],'S':[-math.cos(r),-math.sin(r),0],'D':[-math.sin(r),math.cos(r),0],'A':[math.sin(r),-math.cos(r),0]}
def screenshot(world,label):
    path=OUT/(S['maps'][S['map_index']]+'_'+label+'.png')
    # Queue the game viewport capture without the editor helper's synchronous shader wait.
    u.SystemLibrary.execute_console_command(world,'HighResShot 1280x720 filename="'+str(path)+'"');S['screenshots'].append(str(path))
def sample(cat,basket):
    c=cloth(basket);mesh=cat.get_component_by_class(u.SkeletalMeshComponent);head=next((str(n) for n in mesh.get_all_socket_names() if str(n).lower()=='head'),'root')
    return {'game':GS.get_time_seconds(cat),'cat_actor':xyz(cat.get_actor_location()),'cat_root':xyz(mesh.get_socket_location('root')),'cat_head':xyz(mesh.get_socket_location(head)),'cat_anim':asset_name(mesh),'cloth_anim':asset_name(c),'cat_time':mesh.get_position(),'cloth_time':c.get_position(),'cloth_tick':c.is_component_tick_enabled()}
def expected_clip(basket,outward,kind):
    c=cloth(basket);origin=c.get_world_location();f=c.get_socket_location('Edge_F')-origin;r=c.get_socket_location('Edge_R')-origin
    a=math.atan2(f.x*outward.y-f.y*outward.x,f.x*outward.x+f.y*outward.y)
    if f.x*r.y-f.y*r.x<0:a=-a
    idx=int(math.floor(math.degrees(a)/45+.5))%8
    return 'AN_Cloth_'+kind+'_'+DIRS[idx]
def begin_case(world,cat):
    label,keyname=S['queue'][S['case_index']];S['case']={'map':S['maps'][S['map_index']],'basket':label,'key':keyname,'approaches':[],'entry_samples':[],'exit_samples':[]};S['angle_index']=0
    phase('position')
def next_case(world,cat):
    S['cases'].append(S.pop('case'));S['case_index']+=1;persist()
    if S['case_index']>=len(S['queue']):
        for k in KEYS+['F']:key(world,k,False)
        LEVEL.editor_request_end_play();phase('end_map')
    else:begin_case(world,cat)
def step(world):
    pc=GS.get_player_controller(world,0);cat=GS.get_player_character(world,0)
    if not pc or not cat:return
    action=cat.get_component_by_class(u.CatrunBasketInteractionComponent)
    if not action:return
    now=time.monotonic()
    if S.get('release_f') and now>=S['release_f']:key(world,'F',False);S.pop('release_f')
    p=S['phase'];bs=baskets(world)
    if p=='start_map':
        S['startup_runtime']={'game_seconds':GS.get_time_seconds(world),'paused':GS.is_game_paused(world),'real_seconds':GS.get_real_time_seconds(world)}
        if GS.get_time_seconds(world)<.2:return
        if pc.is_move_input_ignored() or pc.is_look_input_ignored():return
        if now-S['changed']<1.5:return
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        S['queue']=[(label,k) for label in sorted(bs) for k in KEYS];S['case_index']=0;S['map_entry_shot']=False;S['map_exit_shot']=False
        assert len(bs)==len(APPLY['maps'][S['maps'][S['map_index']]]['baskets'])
        begin_case(world,cat);return
    case=S.get('case')
    if not case:return
    basket=bs[case['basket']];center=basket.get_hidden_location()
    if p=='position':
        assert namephase(action)=='OUTSIDE',namephase(action)
        assert S['angle_index']<8,('No reachable approach',case)
        for k in KEYS+['F']:key(world,k,False)
        angle=(S['angle_index']+KEYS.index(case['key'])*2)*math.pi/4;pos=center+u.Vector(math.cos(angle)*100,math.sin(angle)*100,0)
        cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately();cat.set_actor_location(pos,False,True);cat.get_component_by_class(u.CharacterMovementComponent).set_movement_mode(u.MovementMode.MOVE_WALKING)
        case['fixture']=xyz(pos);phase('settle');return
    if p=='settle':
        if now-S['changed']<.35:return
        available=action.can_enter_nearby_basket();case['approaches'].append({'position':xyz(cat.get_actor_location()),'available':available})
        if not available:S['angle_index']+=1;phase('position');return
        case['idle_tick_before']={n:cloth(b).is_component_tick_enabled() for n,b in bs.items()}
        assert not any(case['idle_tick_before'].values()),case['idle_tick_before']
        before=cat.get_actor_location();hit=cat.set_actor_location(center,True,False)
        case['body_sweep']={'hit':str(hit),'stopped':xyz(cat.get_actor_location()),'distance_from_center':(cat.get_actor_location()-center).length()}
        cat.set_actor_location(before,False,True)
        assert case['body_sweep']['distance_from_center']>45.,'Outside capsule passed through basket body'
        outward=cat.get_actor_location()-center;case['expected_entry_clip']=expected_clip(basket,outward,'Enter');case['entry_start']=GS.get_time_seconds(world)
        send_interact(world);phase('entering');return
    if p=='entering':
        bp=namephase(action)
        if bp=='OUTSIDE':
            assert now-S['changed']<.6,('F input did not enter',case);return
        assert action.get_editor_property('ActiveBasket')==basket
        if bp=='ENTERING':
            row=sample(cat,basket)
            if not case['entry_samples'] or row['cat_time']-case['entry_samples'][-1]['cat_time']>.08:case['entry_samples'].append(row)
            assert row['cloth_anim']==case['expected_entry_clip'],row
            assert abs(row['cat_time']-row['cloth_time'])<.08,row
            assert row['cloth_tick']
            if not S['map_entry_shot'] and row['cat_time']>.85:screenshot(world,'enter');S['map_entry_shot']=True
            return
        assert bp=='HIDDEN',bp
        assert not cat.get_component_by_class(u.SkeletalMeshComponent).is_visible() and action.get_editor_property('IsHidden') and not action.get_editor_property('Busy')
        assert not cloth(basket).is_component_tick_enabled()
        assert len(case['entry_samples'])>5,case
        roots=case['entry_samples'];assert max(x['cat_head'][2] for x in roots)-min(x['cat_head'][2] for x in roots)>30,'Cat pose did not execute the actual jump'
        yaw,directions=axes(pc);case['camera_yaw']=yaw;case['expected_direction']=directions[case['key']]
        key(world,case['key'],True);phase('select_exit');return
    if p=='select_exit':
        if now-S['changed']<.15:return
        actual=action.get_editor_property('ExitWorldDirection');expected=u.Vector(*case['expected_direction'])
        assert (actual-expected).length()<.002,('Not camera-relative WASD',case['key'],xyz(actual),xyz(expected))
        case['actual_direction']=xyz(actual);case['can_exit']=action.get_editor_property('CanExit');case['landing']=xyz(action.get_editor_property('ExitWorldLocation'));case['expected_exit_clip']=expected_clip(basket,actual,'Exit')
        key(world,case['key'],False)
        if not case['can_exit']:
            send_interact(world);phase('blocked_confirm');return
        send_interact(world);phase('exiting');return
    if p=='blocked_confirm':
        if now-S['changed']<.2:return
        assert namephase(action)=='HIDDEN' and not action.get_editor_property('Busy'),'Blocked F must not start an exit'
        case['blocked_confirmation_preserved_hidden']=True
        # Use a single other camera key to leave for the next independent case.
        S['fallback_index']=0;phase('fallback');return
    if p=='fallback':
        if S.get('fallback_down'):
            if now-S['changed']<.15:return
            k=S.pop('fallback_down');key(world,k,False)
            if action.get_editor_property('CanExit'):
                case['fallback_key']=k;case['landing']=xyz(action.get_editor_property('ExitWorldLocation'));case['expected_exit_clip']=expected_clip(basket,action.get_editor_property('ExitWorldDirection'),'Exit');send_interact(world);phase('exiting');return
            S['fallback_index']+=1
        assert S['fallback_index']<4,('No single-key way out',case)
        S['fallback_down']=KEYS[S['fallback_index']];key(world,S['fallback_down'],True);S['changed']=now;return
    if p=='exiting':
        bp=namephase(action)
        if bp=='HIDDEN':
            # Live patrols can enter a selected path after confirmation. This is
            # the intended final safety recheck, not a failed input operation.
            if case['exit_samples'] or (now-S['changed']>.15 and not action.get_editor_property('CanExit')):
                assert not action.get_editor_property('Busy') and action.get_editor_property('IsHidden')
                assert basket.get_editor_property('Occupied') and not cat.get_actor_enable_collision()
                assert not cat.get_component_by_class(u.SkeletalMeshComponent).is_visible()
                assert not cloth(basket).is_component_tick_enabled()
                case.setdefault('late_safety_returns',[]).append({'landing':case['landing'],'clip':case['expected_exit_clip'],'samples':case['exit_samples'],'game':GS.get_time_seconds(world)})
                assert len(case['late_safety_returns'])<5,'Repeatedly unable to find a safe landing'
                case['exit_samples']=[];S['fallback_index']=0;phase('fallback');return
            assert now-S['changed']<.6,('F input did not exit',case['basket'],case['key']);return
        if bp=='EXITING':
            row=sample(cat,basket)
            if not case['exit_samples'] or row['cat_time']-case['exit_samples'][-1]['cat_time']>.08:case['exit_samples'].append(row)
            assert row['cloth_anim']==case['expected_exit_clip'],row
            assert abs(row['cat_time']-row['cloth_time'])<.08,row
            if not S['map_exit_shot'] and row['cat_time']>1.:screenshot(world,'exit');S['map_exit_shot']=True
            return
        assert bp=='OUTSIDE',bp
        assert not action.get_editor_property('Busy') and not action.get_editor_property('IsHidden') and not basket.get_editor_property('Occupied')
        assert cat.get_component_by_class(u.SkeletalMeshComponent).is_visible() and cat.get_actor_enable_collision()
        assert (cat.get_actor_location()-u.Vector(*case['landing'])).length()<3.,('Unexpected landing',case,xyz(cat.get_actor_location()))
        assert not cloth(basket).is_component_tick_enabled()
        case['restored']={'location':xyz(cat.get_actor_location()),'collision':cat.get_actor_enable_collision(),'movement':str(cat.get_component_by_class(u.CharacterMovementComponent).movement_mode),'cloth_idle':asset_name(cloth(basket))}
        assert len(case['exit_samples'])>5
        next_case(world,cat)
def load_map():
    assert LEVEL.load_level('/Game/Maps/'+S['maps'][S['map_index']]);LEVEL.editor_request_begin_play();phase('start_map')
def tick(_dt):
    if S.get('in_tick'):return
    S['in_tick']=True
    try:
        if S['phase']=='shutdown':
            if not ED.get_game_world() and time.monotonic()-S['changed']>.5:
                u.unregister_slate_post_tick_callback(S['handle']);u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
            return
        assert time.monotonic()-S['started']<900,'Overall timeout'
        assert time.monotonic()-S['changed']<90,('Phase timeout',S['phase'])
        world=ED.get_game_world()
        if S['phase']=='end_map' and not world:
            S['map_index']+=1
            if S['map_index']==len(S['maps']):finish();return
            load_map();return
        if world:step(world)
    except Exception:finish(traceback.format_exc())
    finally:S['in_tick']=False
assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
S['handle']=u.register_slate_post_tick_callback(tick)
try:load_map()
except Exception:finish(traceback.format_exc())
