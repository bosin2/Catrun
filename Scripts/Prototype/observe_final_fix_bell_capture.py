"""Actual Space bell -> checked armor proximity -> native capture; abort and repeat/retry.
The second bell uses the real BP TryBell function as a labeled API input.
No capture initiation API, collision/tick disabling or persistent world wrappers.
"""
import unreal,json,time,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/FinalFix'/('BellCapture-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(); assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'samples':[],'events':[],'state':'wait_physical_bell','shots':[]}
def v(x): return [x.x,x.y,x.z]
def place(w,actor,target):
 c=actor.get_component_by_class(unreal.CapsuleComponent)
 floor=unreal.SystemLibrary.line_trace_single_by_profile(w,target+unreal.Vector(0,0,80),target-unreal.Vector(0,0,160),'Pawn',False,[actor],unreal.DrawDebugTrace.NONE,False)
 assert floor and floor.to_dict()['impact_normal'].z>=.65,'Unsupported checkpoint'
 target.z=floor.to_dict()['impact_point'].z+c.get_scaled_capsule_half_height()+2.25
 hit=unreal.SystemLibrary.capsule_trace_single_by_profile(w,target,target+unreal.Vector(0,0,.1),c.get_scaled_capsule_radius(),c.get_scaled_capsule_half_height(),'Pawn',False,[actor],unreal.DrawDebugTrace.NONE,False)
 assert not hit,('Occupied checkpoint',str(hit))
 actor.set_actor_location(target,False,True)
 s['events'].append({'event':'API supported-clear armor checkpoint','actor':actor.get_name(),'position':v(target)})
def row(w,cat,a):
 mesh=cat.get_component_by_class(unreal.SkeletalMeshComponent); inst=mesh.get_anim_instance(); single=isinstance(inst,unreal.AnimSingleNodeInstance)
 actions=cat.get_component_by_class(unreal.CatrunBasketInteractionComponent); pc=unreal.GameplayStatics.get_player_controller(w,0); cap=a.get_editor_property('CapturePresentation')
 return {'game':unreal.GameplayStatics.get_time_seconds(w),'phase':cap.get_editor_property('Phase').name,'session':cap.get_editor_property('SessionId'),
  'class':inst.get_class().get_name() if inst else None,'mode':str(mesh.get_animation_mode()),'clip':inst.get_animation_asset().get_name() if single and inst.get_animation_asset() else None,
  'clip_pos':mesh.get_position() if single else None,'movement':str(cat.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property('MovementMode')),
  'collision':cat.get_actor_enable_collision(),'busy':actions.get_editor_property('Busy'),'bell_active':actions.get_editor_property('bBellActive'),'bell_session':actions.get_editor_property('BellSessionId'),
  'move_ignored':pc.is_move_input_ignored(),'look_ignored':pc.is_look_input_ignored(),'cat':v(cat.get_actor_location()),'view':pc.get_view_target().get_name(),'state':s['state']}
def shot(w,name):
 if name not in s['shots']:
  s['shots'].append(name); unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')
def finish(error=None):
 unreal.unregister_slate_post_tick_callback(s['handle'])
 (OUT/'observations.json').write_text(json.dumps({k:x for k,x in s.items() if k!='handle'}|{'error':error},indent=2),encoding='utf8')
 print('FINAL_FIX_BELL_CAPTURE_DONE',str(OUT),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if w:
   cat=unreal.GameplayStatics.get_player_pawn(w,0); aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
   if cat and aa:
    a=aa[0]; cap=a.get_editor_property('CapturePresentation'); actions=cat.get_component_by_class(unreal.CatrunBasketInteractionComponent); r=row(w,cat,a); game=r['game']
    if 'baseline' not in s:
     s['baseline']=r; s['armor_original']=v(a.get_actor_location())
    s['samples'].append(r)
    if s['state']=='wait_physical_bell' and r['clip'] and 'BellShake' in r['clip']:
     assert r['bell_active'] and r['busy'] and r['phase']=='INACTIVE'
     s['first_bell']=game; s['events'].append({'event':'Actual OS bell observed before capture','row':r});place(w,a,cat.get_actor_location()+unreal.Vector(-65,0,0));s['state']='first_capture'
    elif s['state']=='first_capture' and game-s['first_bell']>=3.5:
     assert r['phase']=='HOLDING' and 'MOVE_NONE' in r['movement'] and not r['bell_active'],r
     assert r['clip'] and 'CaughtHeld' in r['clip'],r
     actions.call_method('FinishBell');actions.call_method('EmitBell')
     after=row(w,cat,a); assert all(after[k]==r[k] for k in ['phase','movement','class','clip','busy','bell_active']),after
     s['late_legacy_callbacks']=after;shot(w,'holding-after-old-finish-deadline')
     s['state']='abort_next_tick'
    elif s['state']=='abort_next_tick':
     place(w,a,unreal.Vector(*s['armor_original']));cap.abort_capture();after=row(w,cat,a);s['after_abort']=after
     assert after['phase']=='INACTIVE' and 'MOVE_WALKING' in after['movement'] and after['class']==s['baseline']['class'] and after['collision'] and not after['busy'] and not after['move_ignored'] and not after['look_ignored'],after
     s['state']='wait_second_bell';s['abort_game']=game;shot(w,'abort-stable-playable-cat')
    elif s['state']=='wait_second_bell' and game-s['first_bell']>=5.25:
     assert r['phase']=='INACTIVE' and 'MOVE_WALKING' in r['movement'] and r['class']==s['baseline']['class'],r
     actions.call_method('TryBell');after=row(w,cat,a);assert after['bell_active'] and after['clip'] and 'BellShake' in after['clip'],after
     s['second_bell']=game;s['events'].append({'event':'API invokes real BP TryBell for completed capture/retry','row':after})
     place(w,a,cat.get_actor_location()+unreal.Vector(-65,0,0));s['state']='second_capture'
    elif s['state']=='second_capture':
     if r['phase']=='FADING':s['saw_second_fade']=True
     if game<s['second_bell'] and s.get('saw_second_fade'):
      s['state']='restarted';s['restart_observed']=r
    elif s['state']=='restarted' and game>=1:
     assert r['phase']=='INACTIVE' and r['class']==s['baseline']['class'] and 'MOVE_WALKING' in r['movement'] and r['collision'] and not r['move_ignored'] and not r['look_ignored'] and not r['busy'] and not r['bell_active'],r
     assert all(abs(x-y)<1 for x,y in zip(r['cat'],s['baseline']['cat'])),r
     s['retry_restored']=r;shot(w,'same-stage-retry-restored');finish();return
    if time.monotonic()-s.get('last_save',0)>.25:s['last_save']=time.monotonic();(OUT/'progress.json').write_text(json.dumps(r),encoding='utf8')
  if time.monotonic()-s['start']>90:finish('Timeout waiting for physical bell or completed native retry')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('FINAL_FIX_BELL_CAPTURE_ARMED',str(OUT))
