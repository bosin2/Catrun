"""API establishes a real native capped push below 80%, then actual BP bell.
Subsequent coasting, seating, gate and presentation run on normal PIE ticks.
No direct seat/update/reveal calls, no disabled collision or actor ticks.
"""
import unreal,json,time,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/FinalFix'/('BusySeat-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'samples':[],'phases':[],'shots':[],'state':'wait'}
def v(x):return [x.x,x.y,x.z]
def place_cat(w,cat,target):
 cap=cat.get_component_by_class(unreal.CapsuleComponent)
 floor=unreal.SystemLibrary.line_trace_single_by_profile(w,target+unreal.Vector(0,0,80),target-unreal.Vector(0,0,80),'Pawn',False,[cat],unreal.DrawDebugTrace.NONE,False)
 assert floor and floor.to_dict()['impact_normal'].z>=.65,'Unsupported cat checkpoint';target.z=floor.to_dict()['impact_point'].z+cap.get_scaled_capsule_half_height()+.25
 hit=unreal.SystemLibrary.capsule_trace_single_by_profile(w,target,target+unreal.Vector(0,0,.1),cap.get_scaled_capsule_radius(),cap.get_scaled_capsule_half_height(),'Pawn',False,[cat],unreal.DrawDebugTrace.NONE,False)
 assert not hit,('Occupied cat checkpoint',str(hit));cat.set_actor_location(target,False,True)
def shot(w,name):
 if name not in s['shots']:s['shots'].append(name);unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')
def finish(error=None):
 unreal.unregister_slate_post_tick_callback(s['handle']);(OUT/'observations.json').write_text(json.dumps({k:x for k,x in s.items() if k!='handle'}|{'error':error},indent=2),encoding='utf8');print('FINAL_FIX_BUSY_SEAT_DONE',str(OUT),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if w:
   cat=unreal.GameplayStatics.get_player_pawn(w,0); ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);pc=unreal.GameplayStatics.get_player_controller(w,0)
   if cat and ds and pc:
    game=unreal.GameplayStatics.get_time_seconds(w);d=ds[0];l=d.get_editor_property('Links')[0];r=d.get_editor_property('Reveal');actions=cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
    statue=l.get_editor_property('Statue');plate=l.get_editor_property('Plate').get_actor_location()
    if s['state']=='wait' and game>5.5:
     assert not l.get_editor_property('bPressed') and not pc.is_move_input_ignored()
     pos=unreal.Vector(plate.x,plate.y+60.5,statue.get_actor_location().z);statue.set_actor_location(pos,False,True)
     place_cat(w,cat,pos+unreal.Vector(0,83,26.2))
     assert d.try_push_statue(0,cat,unreal.Vector(0,-1,0),.625),'Native collision-checked push failed'
     assert .75<d.get_seating_overlap(0)<.8,d.get_seating_overlap(0)
     place_cat(w,cat,statue.get_actor_location()+unreal.Vector(0,83,26.2))
     actions.call_method('TryBell');assert actions.get_editor_property('bBellActive') and actions.get_editor_property('Busy')
     settings=d.get_editor_property('Settings');move=cat.get_component_by_class(unreal.CharacterMovementComponent)
     s['setup']={'scope':'API checkpoint + native .625s integrated push capped by real cat speed, real BP TryBell; all following motion uses native Tick','ratio':d.get_seating_overlap(0),'push_speed':settings.get_editor_property('PushSpeed'),'acceleration':settings.get_editor_property('PushAcceleration'),'cat_max_walk_speed':move.get_editor_property('MaxWalkSpeed'),'statue':v(statue.get_actor_location()),'cat':v(cat.get_actor_location()),'game':game,'session':r.get_editor_property('SessionId'),'view':pc.get_view_target().get_name()};s['state']='observing'
    if s['state']=='observing':
     l=d.get_editor_property('Links')[0];phase=r.get_editor_property('Phase').name
     pp=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C'))
     p=next(x for x in pp if str(x.get_editor_property('PuzzleId'))=='A')
     row={'game':game,'phase':phase,'session':r.get_editor_property('SessionId'),'ratio':d.get_seating_overlap(0),'pressed':l.get_editor_property('bPressed'),'pending':l.get_editor_property('bRevealPending'),'complete':l.get_editor_property('bCompleted'),'gate_offset':l.get_editor_property('GateOffset'),'busy':actions.get_editor_property('Busy'),'bell_active':actions.get_editor_property('bBellActive'),'statue':v(l.get_editor_property('Statue').get_actor_location()),'move_ignored':pc.is_move_input_ignored(),'look_ignored':pc.is_look_input_ignored(),'view':pc.get_view_target().get_name(),'presentation_active':p.get_editor_property('PresentationActive'),'dust_active':p.get_editor_property('DustActive')}
     s['samples'].append(row)
     if not s['phases'] or s['phases'][-1]!=phase:s['phases'].append(phase)
     if row['pending']:
      assert row['gate_offset']==0 and phase=='INACTIVE',row
      if row['busy']:s['pending_observed']=True;shot(w,'pending-seat-during-bell')
      else:
       s.setdefault('busy_release_game',game)
       assert game-s['busy_release_game']<.1,'Pending acquisition did not run on the following native tick'
     elif phase!='INACTIVE':shot(w,phase)
     if row['complete'] and phase=='INACTIVE':
      assert s.get('pending_observed') and row['session']==s['setup']['session']+1 and s['phases']==['INACTIVE','TO_GATE','OPENING','RETURNING','INACTIVE'],s['phases']
      assert all(abs(a-b)<.01 for a,b in zip(row['statue'],[plate.x,plate.y,.1])) and abs(row['gate_offset']+280)<.01,row
      assert not any(row[k] for k in ['pending','busy','bell_active','move_ignored','look_ignored','presentation_active','dust_active']) and row['view']==s['setup']['view'],row
      s['returned']=row;shot(w,'returned-controls');finish();return
     if time.monotonic()-s.get('last_save',0)>.25:s['last_save']=time.monotonic();(OUT/'progress.json').write_text(json.dumps(row),encoding='utf8')
  if time.monotonic()-s['start']>40:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('FINAL_FIX_BUSY_SEAT_ARMED',str(OUT))
