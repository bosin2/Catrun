"""Actual Space bell with normal path diagnostics off, then explicit console opt-in/off.
Gold ripple, authored detection settings and all normal AI remain enabled.
"""
import unreal,json,time,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/FinalFix'/('DebugBell-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'samples':[],'state':'wait_physical_bell'}
def shot(w,name):unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')
def finish(error=None):
 w=ed.get_game_world()
 if w:
  unreal.SystemLibrary.execute_console_command(w,'catrun.DebugArmorPaths 0')
  aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
  for a,value in zip(aa,s.get('baseline',{}).get('serialized',[])):a.set_editor_property('bDebugDrawPath',value)
  s['flags_restored']=[a.get_editor_property('bDebugDrawPath') for a in aa]
 unreal.unregister_slate_post_tick_callback(s['handle']);(OUT/'observations.json').write_text(json.dumps({k:x for k,x in s.items() if k!='handle'}|{'error':error},indent=2),encoding='utf8');print('FINAL_FIX_DEBUG_BELL_DONE',str(OUT),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if w:
   cat=unreal.GameplayStatics.get_player_pawn(w,0);aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
   if cat and aa:
    game=unreal.GameplayStatics.get_time_seconds(w);actions=cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
    row={'game':game,'switch':unreal.SystemLibrary.get_console_variable_int_value('catrun.DebugArmorPaths'),'effective':[a.is_path_debug_enabled() for a in aa],'serialized':[a.get_editor_property('bDebugDrawPath') for a in aa],'bell_active':actions.get_editor_property('bBellActive'),'busy':actions.get_editor_property('Busy')}
    if 'baseline' not in s:
     assert row['switch']==0 and not any(row['effective']),row;s['baseline']=row
     s['detection_before']=[a.get_editor_property('bShowDetectionDisplay') for a in aa]
    if s['state']=='wait_physical_bell' and row['bell_active']:s['bell_game']=game;s['state']='normal_off'
    elapsed=game-s.get('bell_game',game)
    if s['state']=='normal_off' and elapsed>=.8:
     assert not any(row['effective'])
     ripples=[a.get_class().get_name() for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor) if 'Ripple' in a.get_class().get_name()]
     assert ripples, 'No authored ripple actor after actual bell emission';s['ripples']=ripples;s['normal_off']=row;shot(w,'normal-bell-gold-ripple-debug-off');s['state']='enable'
    elif s['state']=='enable' and elapsed>=1.15:
     # Opt in both per actor and globally; also exercise an old true override under switch=0.
     for a in aa:a.set_editor_property('bDebugDrawPath',True)
     assert not any(a.is_path_debug_enabled() for a in aa)
     s['old_true_overrides_still_off']=True
     unreal.SystemLibrary.execute_console_command(w,'catrun.DebugArmorPaths 1');s['state']='on'
    elif s['state']=='on' and elapsed>=1.4:
     assert row['switch']==1 and any(row['effective']),row;s['intentional_on']=row;shot(w,'intentional-debug-on');s['state']='disable'
    elif s['state']=='disable' and elapsed>=1.85:unreal.SystemLibrary.execute_console_command(w,'catrun.DebugArmorPaths 0');s['state']='off_again'
    elif s['state']=='off_again' and elapsed>=3.1:
     assert row['switch']==0 and not any(row['effective']) and not row['busy'] and not row['bell_active'],row
     assert s['detection_before']==[a.get_editor_property('bShowDetectionDisplay') for a in aa]
     s['off_again']=row;shot(w,'normal-play-restored-debug-off');finish();return
    if time.monotonic()-s.get('last_save',0)>.1:s['last_save']=time.monotonic();s['samples'].append(row);(OUT/'progress.json').write_text(json.dumps(row),encoding='utf8')
  if time.monotonic()-s['start']>70:finish('Timeout waiting for actual Space bell')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('FINAL_FIX_DEBUG_BELL_ARMED',str(OUT))
