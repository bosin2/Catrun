"""Fixed-pose paused-PIE dust comparison; explicitly a visual diagnostic."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d'/('DustComparison-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'state':'wait','next':2,'samples':[]}
def finish(error=None):
 s['error']=error;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);w=ed.get_game_world()
 if w:unreal.GameplayStatics.set_game_paused(w,False)
 lv.editor_request_end_play()
def shot(w,name):unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);cat=unreal.GameplayStatics.get_player_pawn(w,0)
   if ds and cat:
    d=ds[0];r=d.get_editor_property('Reveal');l=d.get_editor_property('Links')[1];p=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C')) if str(a.get_editor_property('PuzzleId'))=='B');phase=r.get_editor_property('Phase').name
    if s['state']=='wait' and t>s['next']:
     for cls in [unreal.CatrunArmor,unreal.CatrunCandle]:
      for a in unreal.GameplayStatics.get_all_actors_of_class(w,cls):a.set_actor_tick_enabled(False)
     d.set_actor_tick_enabled(False);plate=l.get_editor_property('Plate').get_actor_location();statue=l.get_editor_property('Statue');statue.set_actor_location(unreal.Vector(plate.x+28,plate.y,statue.get_actor_location().z),False,True);cat.set_actor_location(unreal.Vector(plate.x+150,plate.y,26.2),False,True);s['state']='trigger';s['next']=t+.8
    elif s['state']=='trigger' and t>s['next']:d.update_plates_and_gates(.001);d.set_actor_tick_enabled(True);s['state']='opening';s['opening_start']=None
    elif s['state']=='opening' and phase=='OPENING':
     if s['opening_start'] is None:s['opening_start']=t
     if t-s['opening_start']>.85:
      unreal.GameplayStatics.set_game_paused(w,True);p.get_editor_property('BarsMID').set_scalar_parameter_value('Rumble',0);s['state']='on';s['next']=t+.2
    elif s['state']=='on' and t>s['next']:
     shot(w,'dust-on');s['samples'].append({'dust':True,'gate_offset':l.get_editor_property('GateOffset'),'camera':str(r.get_reveal_camera().get_actor_transform())});s['state']='hide';s['next']=t+.4
    elif s['state']=='hide' and t>s['next']:p.call_method('StopDust');s['state']='off';s['next']=t+.4
    elif s['state']=='off' and t>s['next']:
     shot(w,'dust-off');s['samples'].append({'dust':False,'gate_offset':l.get_editor_property('GateOffset'),'camera':str(r.get_reveal_camera().get_actor_transform())});s['state']='end';s['next']=t+.4
    elif s['state']=='end' and t>s['next']:finish();return
  if t>15:finish('timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('TASK4D_DUST_COMPARISON_STARTED',str(OUT))
