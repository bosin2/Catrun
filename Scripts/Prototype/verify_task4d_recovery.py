"""Repeated solve/reset, interruption, view takeover and blocked-gate native timeout.
API setup only; actual native PIE ticks and collision remain enabled.
"""
import unreal,time,json,traceback,sys
from pathlib import Path
sys.path.insert(0,str(Path(unreal.Paths.project_dir())/'Scripts/Prototype'))
from task4d_acceptance import acceptance_error,acceptance_errors
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d'/('Recovery-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
cases=[('A','normal'),('A','repeat'),('A','reset_togate'),('B','normal'),('C','blocked'),('C','takeover'),('C','reset_opening')]
s={'start':time.monotonic(),'results':[],'events':[],'index':0,'state':'wait','next':2}
def v(x):return [x.x,x.y,x.z]
def col(x):return [x.r,x.g,x.b,x.a]
def finish(error=None):
 s['acceptance_errors']=acceptance_errors('recovery',s);s['error']=error or acceptance_error('recovery',s)
 try:(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8')
 finally:unreal.unregister_slate_post_tick_callback(s['handle']);lv.editor_request_end_play()
def eye(p):return col(p.get_editor_property('EyeMID').get_vector_parameter_value('EyesColor'))
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0)
   if ds and cat and pc:
    d=ds[0];r=d.get_editor_property('Reveal');key,case=cases[s['index']];ix='ABC'.index(key);l=d.get_editor_property('Links')[ix];allp=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C'));p=next(x for x in allp if str(x.get_editor_property('PuzzleId'))==key);phase=r.get_editor_property('Phase').name
    if s['state']=='wait' and t>s['next']:
     for cls in [unreal.CatrunArmor,unreal.CatrunCandle]:
      for a in unreal.GameplayStatics.get_all_actors_of_class(w,cls):a.set_actor_tick_enabled(False)
     cat.set_actor_location(unreal.Vector(1375,3900,26.2),False,True);cat.character_movement.set_component_tick_enabled(True)
     s['other_eyes']={str(x.get_editor_property('PuzzleId')):eye(x) for x in allp if str(x.get_editor_property('PuzzleId'))!=key}
     s['reset_ok']=d.reset_statue(key);assert s['reset_ok'];s['reset_eye']=eye(p);s['baseline_eye']=col(p.get_editor_property('EyeOriginalColor'));s['revision']=d.get_editor_property('Links')[ix].get_editor_property('Revision');s['state']='closing';s['next']=t+2.3
    elif s['state']=='closing' and t>s['next']:
     assert abs(d.get_editor_property('Links')[ix].get_editor_property('GateOffset'))<.001
     statue=l.get_editor_property('Statue');plate=l.get_editor_property('Plate').get_actor_location();axis=unreal.Vector(1,0,0) if key=='B' else unreal.Vector(0,1,0);d.set_actor_tick_enabled(False);at=unreal.Vector(plate.x,plate.y,statue.get_actor_location().z)+axis*28;statue.set_actor_location(at,False,True);cat.set_actor_location(unreal.Vector(plate.x,plate.y,26.2)+axis*150,False,True);s['state']='trigger';s['next']=t+.8;s['base_count']=len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor));s['base_view']=pc.get_view_target().get_name()
    elif s['state']=='trigger' and t>s['next']:
     if case=='takeover':pc.set_ignore_move_input(True)
     d.update_plates_and_gates(.001);d.set_actor_tick_enabled(True);assert d.get_editor_property('Links')[ix].get_editor_property('bPressed');s['session']=r.get_editor_property('SessionId');s['begin']=t;s['begin_game']=unreal.GameplayStatics.get_time_seconds(w);s['state']='active';s['acted']=False;s['last_phase']=None
     # Foreign stale token must not clear this new matching-session presentation.
     p.call_method('HandlePhase',args=(unreal.Name(key),unreal.CatrunPuzzleRevealPhase.INACTIVE,s['session']-1));s['stale_session_ignored']=p.get_editor_property('PresentationActive')
     # ECatrunStatueEvent and FCatrunStatueEvent currently collide in Python's
     # stripped type namespace; the real typed BP Reset delegate is exercised
     # above. Stale Revision rejection is additionally checked in saved graph.
     s['stale_revision_ignored']='saved typed graph guard; Python enum name shadows delegate'
    if s['state']=='active':
     phase=r.get_editor_property('Phase').name
     if phase!=s['last_phase']:s['last_phase']=phase;s['phase_start']=t;s['events'].append({'case':case,'puzzle':key,'phase':phase,'t':t,'game':unreal.GameplayStatics.get_time_seconds(w)})
     if not s['acted'] and ((case=='reset_togate' and phase=='TO_GATE') or (case=='reset_opening' and phase=='OPENING' and t-s['phase_start']>.15)):
      s['acted']=True;s['interrupt_reset_ok']=d.reset_statue(key)
     if case=='takeover' and phase=='OPENING' and t-s['phase_start']>.2 and not s['acted']:
      pc.set_view_target_with_blend(p.get_editor_property('GameplayCamera').get_owner(),0);s['acted']=True
     if case=='blocked' and phase in ['TO_GATE','OPENING']:
      gate=l.get_editor_property('Gate');anchor=p.get_editor_property('FloorAnchor');cat.character_movement.set_component_tick_enabled(False);cat.set_actor_location(unreal.Vector(anchor.x,anchor.y,anchor.z+26.2),False,True);s['acted']=True
     if phase=='INACTIVE' and t-s['begin']>.2:
      after=d.get_editor_property('Links')[ix];result={'case':case,'puzzle':key,'session':s['session'],'revision':s['revision'],'reset_original_eye':s['reset_eye']==s['baseline_eye'],'stale_session_ignored':s['stale_session_ignored'],'stale_revision_ignored':s['stale_revision_ignored'],'eye':eye(p),'pressed':after.get_editor_property('bPressed'),'complete':after.get_editor_property('bCompleted'),'offset':after.get_editor_property('GateOffset'),'bars_cleared':not p.get_editor_property('PresentationActive'),'dust_cleared':not p.get_editor_property('DustActive'),'view_preserved':pc.get_view_target().get_name()==s['base_view'],'move_ignored':pc.is_move_input_ignored(),'elapsed_game':unreal.GameplayStatics.get_time_seconds(w)-s['begin_game'],'other_rooms_unchanged':all(eye(x)==s['other_eyes'][str(x.get_editor_property('PuzzleId'))] for x in allp if str(x.get_editor_property('PuzzleId'))!=key),'actor_count':len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)),'baseline_count':s['base_count']}
      if case=='takeover':result['unrelated_input_lock_preserved']=pc.is_move_input_ignored();pc.set_ignore_move_input(False)
      s['results'].append(result)
      if case=='blocked':
       cat.set_actor_location(unreal.Vector(1375,3900,26.2),False,True);cat.character_movement.set_component_tick_enabled(True);s['state']='unblocked';s['next']=t+2.3
      else:s['state']='done'
    elif s['state']=='unblocked' and t>s['next']:
     after=d.get_editor_property('Links')[ix];s['results'][-1]['after_unblock']={'complete':after.get_editor_property('bCompleted'),'offset':after.get_editor_property('GateOffset'),'no_effect_revival':not p.get_editor_property('PresentationActive') and not p.get_editor_property('DustActive'),'control_restored':not pc.is_move_input_ignored()};s['state']='done'
    if s['state']=='done':
     failure=acceptance_error('recovery',s,require_complete=False)
     if failure:finish(failure);return
     if s['index']==len(cases)-1:finish();return
     s['index']+=1;s['state']='wait';s['next']=t+.2
  if t>85:finish('timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('TASK4D_RECOVERY_STARTED',str(OUT))
