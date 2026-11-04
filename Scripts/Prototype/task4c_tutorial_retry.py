"""Actual tutorial intro, capture/retry, then prove intro skips and locomotion restores."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/TutorialRetry';OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert levels.load_level('/Game/Maps/Tutorial')
s={'start':time.monotonic(),'samples':[],'shots':[]}
def finish(err=None):
 s['error']=err;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   g=unreal.GameplayStatics.get_time_seconds(w);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0);aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
   if cat and pc and aa:
    a=aa[0];cap=a.get_editor_property('CapturePresentation');phase=cap.get_editor_property('Phase').name;intro=next((x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor) if x.get_class().get_name()=='BP_TutorialIntro_C'),None);player=intro.get_editor_property('IntroPlayer') if intro else None;playing=bool(player and player.is_playing());s['intro_seen']=s.get('intro_seen',False) or playing
    if not s.get('placed') and g>26 and not playing:
     at=a.get_actor_location()+a.get_actor_forward_vector()*65;at.z=cat.get_actor_location().z;cat.set_actor_location(at,False,True);s['placed']=True
    if phase=='FADING':s['fade_seen']=True
    if s.get('fade_seen') and g<5:s['retry_seen']=True
    if t-s.get('last',-10)>.1:
     s['last']=t;s['samples'].append({'wall':t,'game':g,'phase':phase,'intro_playing':playing,'cat_class':cat.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_class().get_name(),'input':not pc.is_move_input_ignored(),'collision':cat.get_actor_enable_collision(),'view':pc.get_view_target().get_name()})
    if s.get('retry_seen') and g>2 and not s.get('done_at'):
     s['passed']=not playing and phase=='INACTIVE' and not pc.is_move_input_ignored() and cat.get_actor_enable_collision() and cat.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_class().get_name()=='ABP_Cat_Final_C';unreal.SystemLibrary.execute_console_command(w,'Shot showui filename="'+str(OUT/'retry-restored.png').replace('\\','/')+'"');s['done_at']=t
    if s.get('done_at') and t>s['done_at']+.5:finish(None if s['passed'] else 'Retry contract failed');return
  if t>55:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('TUTORIAL_RETRY_STARTED')
