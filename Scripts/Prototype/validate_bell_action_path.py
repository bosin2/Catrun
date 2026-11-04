"""Injected EnhancedInput IA_Bell path; deliberately not physical-key evidence.

Direct action injection bypasses key-priority routing. The active blocker context
and delayed emission guard are inspected separately from this action-path check.
"""
import unreal,time,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Prototype20261104/CanonicalMaps/BellAction2'
out.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
state={'start':time.monotonic(),'phase':'start','samples':[],'scope':'EnhancedInput action injection, not OS key input'}
def finish(error=None):
    state['error']=error
    (out/'observations.json').write_text(json.dumps({k:v for k,v in state.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
    unreal.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play();print('BELL_ACTION_FINISHED',error)
def tick(delta):
    try:
        now=time.monotonic();w=editor.get_game_world();elapsed=now-state['start']
        if elapsed>30:finish('timeout');return
        if not w or elapsed<3:return
        cat=unreal.GameplayStatics.get_player_pawn(w,0)
        sub=next(s for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem) if s.get_world()==w)
        action=unreal.load_asset('/Game/Input/Actions/IA_Bell')
        actions=next(c for c in cat.get_components_by_class(unreal.ActorComponent) if 'CatActions' in c.get_class().get_name())
        row={'elapsed':elapsed,'phase':state['phase'],'last_bell_time':actions.get_editor_property('LastBellTime'),'busy':actions.get_editor_property('Busy'),'bell_keys':[k.export_text() for k in sub.query_keys_mapped_to_action(action)],'block_contexts':[]}
        for ctx in unreal.ObjectIterator(unreal.InputMappingContext):
            if ctx.get_name()=='BellBlockContext' and ctx.get_typed_outer(unreal.CatrunBellComponent) and ctx.get_typed_outer(unreal.CatrunBellComponent).get_world()==w:row['block_contexts'].append({'path':ctx.get_path_name(),'priority':str(sub.has_mapping_context(ctx))})
        state['samples'].append(row)
        if state['phase']=='start':
            state['before_time']=row['last_bell_time'];state['outside_location']=[cat.get_actor_location().x,cat.get_actor_location().y,cat.get_actor_location().z]
            print('BELL_ACTION_OUTSIDE_BEGIN')
            sub.inject_input_vector_for_action(action,unreal.Vector(1,0,0),[],[])
            state['phase']='outside';state['at']=now
        elif state['phase']=='outside' and now-state['at']>4:
            assert row['last_bell_time']>state['before_time'],row
            state['outside_action_fired']=True;print('BELL_ACTION_OUTSIDE_END')
            zone=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunNoBellZone) if a.get_actor_label()=='NoBell_CatHole_Banquet')
            pos=zone.get_actor_location();pos.z=26;cat.set_actor_location(pos,False,True)
            state['phase']='inside_ready';state['at']=now
        elif state['phase']=='inside_ready' and now-state['at']>.7:
            state['inside_context']=row
            assert any(x['priority']=='10000' for x in row['block_contexts']),row
            print('BELL_ACTION_INSIDE_BEGIN')
            sub.inject_input_vector_for_action(action,unreal.Vector(1,0,0),[],[])
            state['phase']='inside';state['at']=now
        elif state['phase']=='inside' and now-state['at']>2:
            assert row['last_bell_time']==state['inside_context']['last_bell_time'],row
            state['original_bell_action_suppressed']=True
            blocker=next(a for a in unreal.ObjectIterator(unreal.InputAction) if a.get_name()=='BellBlockAction' and a.get_typed_outer(unreal.CatrunBellComponent) and a.get_typed_outer(unreal.CatrunBellComponent).get_world()==w)
            state['blocked_action_keys']=[k.export_text() for k in sub.query_keys_mapped_to_action(blocker)]
            assert state['blocked_action_keys']==['SpaceBar'],state['blocked_action_keys']
            sub.inject_input_vector_for_action(blocker,unreal.Vector(1,0,0),[],[])
            state['phase']='blocked_feedback';state['at']=now
        elif state['phase']=='blocked_feedback' and now-state['at']>.7:
            notices=list(unreal.WidgetLibrary.get_all_widgets_of_class(w,unreal.CatrunNoticeWidget,False))
            state['notice_texts']=[str(t.get_text()) for t in unreal.ObjectIterator(unreal.TextBlock) if any(t.get_typed_outer(unreal.CatrunNoticeWidget)==n for n in notices)]
            print('BELL_ACTION_INSIDE_END',state['notice_texts'])
            assert '방울을 울릴수없습니다' in state['notice_texts'],state['notice_texts']
            unreal.SystemLibrary.execute_console_command(w,'Shot showui filename="'+str(out/'inside-action-denied.png').replace('\\','/')+'"')
            state['phase']='finish';state['at']=now
        elif state['phase']=='finish' and now-state['at']>1:finish()
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play()
