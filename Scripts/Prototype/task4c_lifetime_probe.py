"""Slow-rate lifespan and actual owner-destruction cleanup, after final BP hardening."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/Lifetime01';OUT.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
s={'start':time.monotonic(),'state':'waiting','results':[]}
CtxClass=unreal.load_class(None,'/Game/Characters/LivingArmor/Blueprints/BP_CapturePlayback.BP_CapturePlayback_C')
def finish(err=None):
 s['error']=err;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def result(cat,pc,world):
 return {'cat_class':cat.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_class().get_name(),'view_restored':pc.get_view_target().get_name()==s['base_view'],'move_restored':not pc.is_move_input_ignored(),'look_restored':not pc.is_look_input_ignored(),'collision':cat.get_actor_enable_collision(),'contexts':len(unreal.GameplayStatics.get_all_actors_of_class(world,CtxClass))}
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=editor.get_game_world()
  if w:
   game=unreal.GameplayStatics.get_time_seconds(w);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0);aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
   if cat and pc:
    if 'armor_name' not in s and aa:
     s['armor_name']=aa[0].get_name();s['base_cat']=[cat.get_actor_location().x,cat.get_actor_location().y,cat.get_actor_location().z];s['base_view']=pc.get_view_target().get_name()
     for other in aa[1:]:other.set_actor_tick_enabled(False)
    a=next((a for a in aa if a.get_name()==s.get('armor_name')),None)
    if s['state']=='destroyed' and game>s['destroy_game']+.4:
     s['results'].append({'case':'owner_destroy',**result(cat,pc,w)});finish();return
    if a:
     cap=a.get_editor_property('CapturePresentation');ctx=a.get_editor_property('CapturePlaybackContext')
     if s['state']=='waiting' and game>1:
      cap.set_editor_property('PickupPlayRate',.25);at=a.get_actor_location()+a.get_actor_forward_vector()*65;at.z=s['base_cat'][2];cat.set_actor_location(at,False,True);s['state']='slow'
     if s['state']=='slow':
      if ctx and 'context_game' not in s:s['context_game']=game
      if ctx and game>s['context_game']+16:
       s['results'].append({'case':'slow_context_survives','observed_lifetime':game-s['context_game'],'session':cap.get_editor_property('SessionId'),'origin':ctx.get_editor_property('OriginSessionId'),'phase':cap.get_editor_property('Phase').name,'canceled':ctx.get_editor_property('Canceled'),'montage_position':a.get_editor_property('Mesh').get_anim_instance().montage_get_position(a.get_editor_property('Mesh').get_anim_instance().get_current_active_montage())})
       unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/'slow-hold.png').replace('\\','/')+'"')
       a.set_actor_tick_enabled(False);cap.abort_capture();cat.set_actor_location(unreal.Vector(*s['base_cat']),False,True);s['results'].append({'case':'slow_abort',**result(cat,pc,w)});s['state']='between';s['again_game']=game+1;a.set_actor_tick_enabled(True)
     elif s['state']=='between' and game>s['again_game']:
      cap.set_editor_property('PickupPlayRate',1);at=a.get_actor_location()+a.get_actor_forward_vector()*65;at.z=s['base_cat'][2];cat.set_actor_location(at,False,True);s['state']='owner'
     elif s['state']=='owner' and ctx and cap.get_editor_property('Phase')==unreal.CatrunCapturePhase.PICKUP:
      s.setdefault('owner_context_game',game)
      if game>s['owner_context_game']+.4:a.destroy_actor();s['destroy_game']=game;s['state']='destroyed'
  if t>40:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('LIFETIME01_STARTED')
