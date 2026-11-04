"""Actual PIE reset settling, restart and menu travel during Opening; API setup."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d'/('Lifecycle-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'state':'wait','next':2,'index':0,'results':[],'setup':'API placement; actual native PIE reset/restart/travel'}
def finish(error=None):
 s['error']=error;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);lv.editor_request_end_play()
def color(c):return [c.r,c.g,c.b,c.a]
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   ps=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C'));ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);pc=unreal.GameplayStatics.get_player_controller(w,0);game=unreal.GameplayStatics.get_time_seconds(w)
   if s['state']=='menu' and 'MainMenu' in w.get_name() and t>s['next']:
    result={'case':'menu_travel','world':w.get_path_name(),'presentation_count':len(ps),'director_count':len(ds),'view':pc.get_view_target().get_name(),'reveal_cameras':[a.get_name() for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CameraActor) if 'Reveal' in a.get_name()]};assert not ps and not ds and not result['reveal_cameras'];s['results'].append(result);finish();return
   if ds and pc and ps:
    d=ds[0];r=d.get_editor_property('Reveal');p=next(a for a in ps if str(a.get_editor_property('PuzzleId'))=='C');l=d.get_editor_property('Links')[2];cat=unreal.GameplayStatics.get_player_pawn(w,0);phase=r.get_editor_property('Phase').name
    if s['state']=='restart' and t>s['next'] and game<s['old_game']:
     result={'case':'restart','world':w.get_path_name(),'game_time':game,'pressed':l.get_editor_property('bPressed'),'offset':l.get_editor_property('GateOffset'),'phase':phase,'camera':str(r.get_reveal_camera()),'move_ignored':pc.is_move_input_ignored(),'effects':any(a.get_editor_property('PresentationActive') or a.get_editor_property('DustActive') for a in ps),'eye_original':color(p.get_editor_property('EyeMID').get_vector_parameter_value('EyesColor'))==color(p.get_editor_property('EyeOriginalColor'))};assert not result['pressed'] and abs(result['offset'])<.001 and phase=='INACTIVE' and not result['move_ignored'] and not result['effects'] and result['eye_original'];s['results'].append(result);s['index']=2;s['state']='wait';s['next']=t+1
    if s['state']=='wait' and t>s['next'] and cat:
     for cls in [unreal.CatrunArmor,unreal.CatrunCandle]:
      for a in unreal.GameplayStatics.get_all_actors_of_class(w,cls):a.set_actor_tick_enabled(False)
     d.set_actor_tick_enabled(False);plate=l.get_editor_property('Plate').get_actor_location();statue=l.get_editor_property('Statue');statue.set_actor_location(unreal.Vector(plate.x,plate.y+28,statue.get_actor_location().z),False,True);cat.set_actor_location(unreal.Vector(plate.x,plate.y+150,26.2),False,True);s['state']='trigger';s['next']=t+.8
    elif s['state']=='trigger' and t>s['next']:
     d.update_plates_and_gates(.001);d.set_actor_tick_enabled(True);s['state']='opening';s['opening_start']=None
    elif s['state']=='opening' and phase=='OPENING':
     if s['opening_start'] is None:s['opening_start']=t
     if t-s['opening_start']>.3:
      if s['index']==0:
       assert d.reset_statue('C');s['state']='reset_settle';s['next']=t+1.5
      elif s['index']==1:
       s['old_game']=game;assert unreal.CatrunLevelFlowLibrary.restart_current_stage(w);s['state']='restart';s['next']=t+1.5
      else:
       assert unreal.CatrunLevelFlowLibrary.return_to_main_menu(w);s['state']='menu';s['next']=t+1.5
    elif s['state']=='reset_settle' and t>s['next']:
     result={'case':'reset_settled','offset':l.get_editor_property('GateOffset'),'pressed':l.get_editor_property('bPressed'),'phase':phase,'move_ignored':pc.is_move_input_ignored(),'effects':p.get_editor_property('PresentationActive') or p.get_editor_property('DustActive'),'eye_original':color(p.get_editor_property('EyeMID').get_vector_parameter_value('EyesColor'))==color(p.get_editor_property('EyeOriginalColor'))};assert abs(result['offset'])<.001 and not result['pressed'] and phase=='INACTIVE' and not result['move_ignored'] and not result['effects'] and result['eye_original'];s['results'].append(result);s['index']=1;s['state']='wait';s['next']=t+.3
  if t>35:finish('timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('TASK4D_LIFECYCLE_STARTED',str(OUT))
