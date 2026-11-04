"""Abort each native capture phase, check owned presentation cleanup and lost-notify fallback."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/Cancel02';OUT.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
s={'start':time.monotonic(),'samples':[],'results':[],'index':0,'next':2,'state':'waiting','last_phase':None}
cases=['FRAMING','PICKUP','HOLDING','FADING','FALLBACK']
def v(x):return [x.x,x.y,x.z]
def finish(err=None):
 s['error']=err;(OUT/'observations.json').write_text(json.dumps({k:x for k,x in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def tick(dt):
 try:
  t=time.monotonic()-s['start'];world=editor.get_game_world()
  if world:
   cat=unreal.GameplayStatics.get_player_pawn(world,0);pc=unreal.GameplayStatics.get_player_controller(world,0);aa=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor)
   if cat and pc and aa:
    armor=aa[0];cap=armor.get_editor_property('CapturePresentation');phase=cap.get_editor_property('Phase');sid=cap.get_editor_property('SessionId');cm=cat.get_component_by_class(unreal.SkeletalMeshComponent);am=armor.get_editor_property('Mesh');ctx=armor.get_editor_property('CapturePlaybackContext')
    if 'base_cat' not in s:s['base_cat']=v(cat.get_actor_location());s['base_view']=pc.get_view_target().get_name()
    case=cases[min(s['index'],4)]
    if s['state']=='waiting' and t>s['next']:
     for other in aa[1:]:other.set_actor_tick_enabled(False)
     armor.set_actor_tick_enabled(True);at=armor.get_actor_location()+armor.get_actor_forward_vector()*65;at.z=s['base_cat'][2];cat.set_actor_location(at,False,True);s['state']='capturing';s['last_phase']=None;s['begin_game_time']=unreal.GameplayStatics.get_time_seconds(world)
    if phase.name!=s['last_phase']:
     s['last_phase']=phase.name;s['phase_wall_start']=t
     s['samples'].append({'t':t,'game':unreal.GameplayStatics.get_time_seconds(world),'case':case,'phase':phase.name,'session':sid,'cat_class':cm.get_anim_instance().get_class().get_name(),'armor_class':am.get_anim_instance().get_class().get_name(),'context':ctx.get_name() if ctx else None,'view':pc.get_view_target().get_name(),'ignore':pc.is_move_input_ignored()})
    if s['state']=='capturing' and case!='FALLBACK' and phase.name==case and t-s['phase_wall_start']>.2:
     armor.set_actor_tick_enabled(False);old=sid;cap.abort_capture();cat.set_actor_location(unreal.Vector(*s['base_cat']),False,True)
     left=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.load_class(None,'/Game/Characters/LivingArmor/Blueprints/BP_CapturePlayback.BP_CapturePlayback_C'))
     result={'case':case,'session':old,'phase_after':cap.get_editor_property('Phase').name,'cat_class_after':cm.get_anim_instance().get_class().get_name(),'armor_class_after':am.get_anim_instance().get_class().get_name(),'view_restored':pc.get_view_target().get_name()==s['base_view'],'move_restored':not pc.is_move_input_ignored(),'look_restored':not pc.is_look_input_ignored(),'collision_restored':cat.get_actor_enable_collision(),'context_cleared':armor.get_editor_property('CapturePlaybackContext') is None,'live_contexts':len(left),'stale_grab_rejected':not cap.notify_grab(old),'stale_finish_rejected':not cap.notify_finished(old)}
     s['results'].append(result);s['old_session']=old;s['index']+=1;s['state']='waiting';s['next']=t+1;armor.set_actor_tick_enabled(True)
    elif s['state']=='capturing' and case=='FALLBACK':
     if phase.name=='PICKUP' and ctx and not s.get('suppressed'):
      am.get_anim_instance().montage_pause(am.get_anim_instance().get_current_active_montage());s['suppressed']=True;s['fallback_session']=sid;s['pickup_game']=unreal.GameplayStatics.get_time_seconds(world)
     if s.get('suppressed') and phase.name=='HOLDING' and 'fallback_grab_game' not in s:
      s['fallback_grab_game']=unreal.GameplayStatics.get_time_seconds(world)-s['pickup_game'];s['fallback_notify_grab']=ctx.get_editor_property('GrabNotifyAccepted')
     if s.get('suppressed') and phase.name=='FADING' and 'fallback_end_game' not in s:
      s['fallback_end_game']=unreal.GameplayStatics.get_time_seconds(world)-s['pickup_game'];s['fallback_notify_end']=ctx.get_editor_property('FinishNotifyAccepted')
     if 'fallback_end_game' in s and phase.name=='INACTIVE':
      s['fallback_recovery']={'cat_class':cm.get_anim_instance().get_class().get_name(),'control':not pc.is_move_input_ignored(),'collision':cat.get_actor_enable_collision()};finish();return
    if s.get('old_session') and ctx and phase.name=='PICKUP' and sid>s['old_session'] and s.get('stale_checked_session')!=sid:
     before=ctx.get_path_name();armor.call_method('HandleCapturePhase',args=(unreal.CatrunCapturePhase.INACTIVE,s['old_session']));s['results'].append({'stale_phase_session':s['old_session'],'current_session':sid,'context_preserved':armor.get_editor_property('CapturePlaybackContext').get_path_name()==before});s['stale_checked_session']=sid
  if t>50:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('CANCEL01_STARTED')
