"""Focused native API PIE route/intro/retry/collision/bell evidence, not manual play."""
import unreal,time,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Prototype20261104/CanonicalMaps/Runtime2'
out.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert levels.load_level('/Game/Maps/MainMenu')
probe={'start':time.monotonic(),'phase':'menu','maps':{},'samples':[],'scope':'Native flow APIs and teleports/capsule traces; not OS-key traversal'}
def vec(v):return [v.x,v.y,v.z]
def actors(w):return unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)
def shot(w,name):unreal.SystemLibrary.execute_console_command(w,'Shot showui filename="'+str(out/(name+'.png')).replace('\\','/')+'"')
def finish(error=None):
    probe['error']=error
    (out/'observations.json').write_text(json.dumps({k:v for k,v in probe.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
    unreal.unregister_slate_post_tick_callback(probe['handle']);levels.editor_request_end_play()
    print('CANONICAL_RUNTIME_FINISHED',error)
def sample(w):
    pc=unreal.GameplayStatics.get_player_controller(w,0);cat=unreal.GameplayStatics.get_player_pawn(w,0)
    view=pc.get_view_target();camera=view.get_component_by_class(unreal.CameraComponent)
    intro=next((a for a in actors(w) if a.get_class().get_name()=='BP_TutorialIntro_C'),None)
    player=intro.get_editor_property('IntroPlayer') if intro else None
    return {'world':w.get_path_name(),'cat':cat.get_path_name() if cat else None,'location':vec(cat.get_actor_location()) if cat else None,'view':view.get_name(),'width':camera.ortho_width if camera else None,'move_ignored':pc.is_move_input_ignored(),'intro_player':bool(player),'intro_playing':bool(player and player.is_playing()),'widgets':[v.get_class().get_name() for v in unreal.WidgetLibrary.get_all_widgets_of_class(w,unreal.UserWidget,False) if v.is_in_viewport()]}
def inspect(w,stage):
    aa=actors(w);cat=unreal.GameplayStatics.get_player_pawn(w,0)
    rows={'sample':sample(w),'dependencies':[],'capsules':[]}
    for a in aa:
        cls=a.get_class().get_name()
        if any(x in cls for x in ['Sound','Armor','Candle','StatuePuzzle','PuzzleReset','NoBell','Door']):rows['dependencies'].append({'label':a.get_actor_label(),'class':cls})
        if a==cat or any(x in cls for x in ['LivingArmor','Candle']):
            for c in a.get_components_by_class(unreal.CapsuleComponent):rows['capsules'].append({'actor':a.get_actor_label(),'class':cls,'radius':c.get_scaled_capsule_radius(),'half_height':c.get_scaled_capsule_half_height(),'relative_location':vec(c.get_editor_property('relative_location')),'collision':str(c.get_collision_enabled()),'object_type':str(c.get_collision_object_type()),'world_dynamic_response':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_DYNAMIC)),'pawn_response':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))})
    manager=next(a for a in aa if a.get_class().get_name()=='SoundGridManager')
    rows['has_grid']=manager.has_grid()
    rows['sound_settings']=manager.get_editor_property('Settings').get_path_name()
    rows['active_input']=[]
    for sub in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem):
        if sub.get_world()!=w:continue
        rows['active_input'].append({'contexts':{p:str(sub.has_mapping_context(unreal.load_asset(p))) for p in ['/Game/Input/Contexts/IMC_Default','/Game/Input/Contexts/IMC_CatInteraction']},'keys':{name:[key.export_text() for key in sub.query_keys_mapped_to_action(unreal.load_asset('/Game/Input/Actions/'+name))] for name in ['IA_Move','IA_Run','IA_Sneak','IA_Bell','IA_Interact']}})
    probe['maps'][stage]=rows
    shot(w,stage+'-gameplay')
def bell_tests(w,stage):
    cat=unreal.GameplayStatics.get_player_pawn(w,0)
    original=cat.get_actor_location()
    bell=cat.get_component_by_class(unreal.CatrunBellComponent)
    zones=[a for a in actors(w) if isinstance(a,unreal.CatrunNoBellZone)]
    rows={'listens_to_actions':bell.is_listening_to_cat_actions(),'zones':[]}
    for zone in zones:
        pos=zone.get_actor_location();pos.z=26
        cat.set_actor_location(pos,False,True)
        print('CANONICAL_BELL_DENIED_BEGIN',stage,zone.get_actor_label())
        denied=bell.try_ring()
        print('CANONICAL_BELL_DENIED_END',denied)
        rows['zones'].append({'zone':zone.get_actor_label(),'position':vec(pos),'try_ring':denied})
        assert not denied,(stage,zone.get_actor_label())
    cat.set_actor_location(original,False,True)
    print('CANONICAL_BELL_ALLOWED_BEGIN',stage)
    rows['allowed_position']=vec(original);rows['allowed']=bell.try_ring()
    print('CANONICAL_BELL_ALLOWED_END',rows['allowed'])
    assert rows['allowed'],stage
    # Simulate the delayed OnBellRung callback crossing into a zone: same reflected
    # handler the native component subscribes to, deliberately bypassing cooldown.
    pos=zones[0].get_actor_location();pos.z=26;cat.set_actor_location(pos,False,True)
    print('CANONICAL_BELL_DELAYED_BEGIN',stage)
    bell.call_method('HandleBellRung')
    print('CANONICAL_BELL_DELAYED_END',stage)
    rows['delayed_handler_called_inside']=True
    notices=unreal.WidgetLibrary.get_all_widgets_of_class(w,unreal.CatrunNoticeWidget,False)
    rows['notice_texts']=[str(t.get_text()) for t in unreal.ObjectIterator(unreal.TextBlock) if any(t.get_typed_outer(unreal.CatrunNoticeWidget)==n and n.is_in_viewport() for n in notices)]
    assert '방울을 울릴수없습니다' in rows['notice_texts'],rows
    probe['maps'][stage]['bell']=rows
    probe['restore_location']=vec(original)
def tick(delta):
    try:
        now=time.monotonic();elapsed=now-probe['start'];w=editor.get_game_world()
        if elapsed>105:finish('timeout');return
        if not w or now-probe.get('last',0)<.2:return
        probe['last']=now;name=w.get_name();phase=probe['phase']
        if phase=='menu' and name.endswith('MainMenu') and elapsed>2:
            probe['menu_seen']=sample(w);assert unreal.CatrunLevelFlowLibrary.start_new_game(w)
            probe['phase']='intro';probe['phase_at']=now
        elif phase=='intro' and name.endswith('Tutorial'):
            probe.setdefault('tutorial_at',now);t=now-probe['tutorial_at']
            row=sample(w);row['t']=t;probe['samples'].append(row)
            if t>5 and not probe.get('intro_shot'):shot(w,'tutorial-intro');probe['intro_shot']=True
            if t>26:
                assert '/SoundTest_' not in row['world'] and not row['intro_playing'] and not row['move_ignored'] and row['width']==900
                probe['normal_intro_complete']=row
                assert unreal.CatrunLevelFlowLibrary.restart_current_stage(w)
                probe['phase']='retry';probe['phase_at']=now
        elif phase=='retry' and now-probe['phase_at']>5 and name.endswith('Tutorial'):
            row=sample(w);assert not row['intro_player'] and not row['move_ignored'] and row['width']==900,row
            assert abs(row['location'][0]-170)<1 and abs(row['location'][1]+95)<1,row
            probe['retry_complete']=row;inspect(w,'Tutorial');probe['phase']='bell_Tutorial';probe['phase_at']=now
        elif phase.startswith('bell_') and now-probe['phase_at']>1:
            stage=phase.removeprefix('bell_');bell_tests(w,stage)
            probe['phase']='notice_'+stage;probe['phase_at']=now
        elif phase.startswith('notice_') and now-probe['phase_at']>.6:
            stage=phase.removeprefix('notice_');shot(w,stage+'-bell-denied')
            cat=unreal.GameplayStatics.get_player_pawn(w,0);cat.set_actor_location(unreal.Vector(*probe['restore_location']),False,True)
            assert unreal.CatrunLevelFlowLibrary.complete_current_stage(w)
            probe['phase']={'Tutorial':'enter_Stage1','Stage1':'enter_Stage2','Stage2':'complete'}[stage];probe['phase_at']=now
        elif phase.startswith('enter_') and now-probe['phase_at']>5:
            stage=phase.removeprefix('enter_');assert name.endswith(stage) and 'SoundTest' not in name,name
            inspect(w,stage);assert probe['maps'][stage]['sample']['width']=={'Stage1':1035,'Stage2':1170}[stage]
            probe['phase']='bell_'+stage;probe['phase_at']=now
        elif phase=='complete' and now-probe['phase_at']>2:
            probe['final_completion']=sample(w);shot(w,'Stage2-complete')
            probe['phase']='finish';probe['phase_at']=now
        elif phase=='finish' and now-probe['phase_at']>1:finish()
    except Exception:finish(traceback.format_exc())
probe['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
