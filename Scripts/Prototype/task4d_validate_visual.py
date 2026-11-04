"""Foreground PIE acceptance, API placement setup clearly labelled; never saves moved actors."""
import unreal,time,json,traceback,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(unreal.Paths.project_dir())/'Scripts/Prototype'))
from task4d_acceptance import acceptance_error,acceptance_errors
ROOT=Path(unreal.Paths.project_dir());base=ROOT/'Saved/Prototype20261104/Task4d';OUT=base/('VisualFinal-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'samples':[],'results':[],'shots':[],'index':0,'state':'wait','next':2,'setup':'API placement below/above native seating threshold; timed native PIE gate/reveal'}
def v(x):return [x.x,x.y,x.z]
def color(x):return [x.r,x.g,x.b,x.a]
def pp_hash(camera):return hashlib.sha256(camera.get_editor_property('post_process_settings').export_text().encode()).hexdigest() if camera else None
def finish(error=None):
 s['acceptance_errors']=acceptance_errors('visual',s);s['error']=error or acceptance_error('visual',s)
 try:(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8')
 finally:unreal.unregister_slate_post_tick_callback(s['handle']);lv.editor_request_end_play()
def shot(w,name):
 if name not in s['shots']:s['shots'].append(name);unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(name+'.png')).replace('\\','/')+'"')
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0)
   if ds and cat and pc:
    d=ds[0];r=d.get_editor_property('Reveal');i=s['index'];l=d.get_editor_property('Links')[i];key=str(l.get_editor_property('PuzzleId'));plate=l.get_editor_property('Plate').get_actor_location();statue=l.get_editor_property('Statue');gate=l.get_editor_property('Gate');p=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C')) if str(a.get_editor_property('PuzzleId'))==key)
    if s['state']=='wait' and t>s['next']:
     for cls in [unreal.CatrunArmor,unreal.CatrunCandle]:
      for a in unreal.GameplayStatics.get_all_actors_of_class(w,cls):a.set_actor_tick_enabled(False)
     d.set_actor_tick_enabled(False);axis=unreal.Vector(1,0,0) if key=='B' else unreal.Vector(0,1,0);loc=statue.get_actor_location();statue.set_actor_location(unreal.Vector(plate.x,plate.y,loc.z)+axis*30,False,True);cat.set_actor_location(unreal.Vector(plate.x,plate.y,26.2)+axis*160,False,True);s['state']='below';s['next']=t+1;s['base_count']=len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor));s['base_view']=pc.get_view_target().get_name();s['base_pp']=pp_hash(pc.get_view_target().get_component_by_class(unreal.CameraComponent));s['base_eye']=color(p.get_editor_property('EyeMID').get_vector_parameter_value('EyesColor'))
    elif s['state']=='below' and t>s['next']:
     d.update_plates_and_gates(.01);s['below']={'ratio':d.get_seating_overlap(i),'pressed':d.get_editor_property('Links')[i].get_editor_property('bPressed'),'eye':color(p.get_editor_property('EyeMID').get_vector_parameter_value('EyesColor'))};shot(w,key+'-before')
     s['state']='above';s['next']=t+.2
    elif s['state']=='above' and t>s['next']:
     axis=unreal.Vector(1,0,0) if key=='B' else unreal.Vector(0,1,0);loc=statue.get_actor_location();statue.set_actor_location(unreal.Vector(plate.x,plate.y,loc.z)+axis*28,False,True);s['above_ratio']=d.get_seating_overlap(i);d.update_plates_and_gates(.001);d.set_actor_tick_enabled(True);s['state']='observe';s['begin']=t;s['phase_last']=None;s['last_shot']=t
    phase=r.get_editor_property('Phase').name;cam=r.get_reveal_camera();cc=cam.get_component_by_class(unreal.CameraComponent) if cam else None
    if s['state']=='observe':
     if phase!=s['phase_last']:s['phase_last']=phase;s['phase_start']=t;shot(w,key+'-'+phase);s['last_shot']=t
     if t-s.get('last_sample',0)>.05:
      s['last_sample']=t;l=d.get_editor_property('Links')[i];cc=cam.get_component_by_class(unreal.CameraComponent) if cam else None;mid=p.get_editor_property('EyeMID');s['samples'].append({'t':t,'dt':dt,'puzzle':key,'phase':phase,'session':r.get_editor_property('SessionId'),'presentation_session':p.get_editor_property('OriginSessionId'),'active':p.get_editor_property('PresentationActive'),'camera':v(cam.get_actor_location()) if cam else None,'rotation':str(cam.get_actor_rotation()) if cam else None,'projection':str(cc.get_editor_property('projection_mode')) if cc else None,'width':cc.get_editor_property('ortho_width') if cc else None,'original_width':p.get_editor_property('OriginalOrthoWidth'),'eyes':color(mid.get_vector_parameter_value('EyesColor')),'strength':mid.get_scalar_parameter_value('EyesStrength'),'dust':p.get_editor_property('DustActive'),'dust_anchor':v(p.get_actor_location()),'gate':v(gate.get_actor_location()),'gate_top':sum(z.z for z in gate.get_actor_bounds(False)),'required':l.get_editor_property('RequiredGateTravel'),'pressed':l.get_editor_property('bPressed'),'complete':l.get_editor_property('bCompleted'),'move_ignored':pc.is_move_input_ignored(),'actors':len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor))})
     if t-s['last_shot']>.4 and t-s['begin']<4:s['last_shot']=t;shot(w,key+'-frame-'+str(round((t-s['begin'])*10)))
     if cc:s['samples'][-1]['motion_blur']={'override':cc.get_editor_property('post_process_settings').get_editor_property('override_motion_blur_amount'),'amount':cc.get_editor_property('post_process_settings').get_editor_property('motion_blur_amount')}
     if phase=='INACTIVE' and t-s['begin']>4.3:
      l=d.get_editor_property('Links')[i];s['results'].append({'puzzle':key,'below':s['below'],'above_ratio_before_seat':s['above_ratio'],'seat':v(statue.get_actor_location()),'complete':l.get_editor_property('bCompleted'),'gate_offset':l.get_editor_property('GateOffset'),'gate_top':sum(z.z for z in gate.get_actor_bounds(False)),'return_view':pc.get_view_target().get_name()==s['base_view'],'input_restored':not pc.is_move_input_ignored(),'no_active_presentation':not p.get_editor_property('PresentationActive'),'no_dust':not p.get_editor_property('DustActive'),'actor_count':len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)),'baseline_count':s['base_count']})
      s['results'][-1]['gameplay_postprocess_unchanged']=s['base_pp']==pp_hash(pc.get_view_target().get_component_by_class(unreal.CameraComponent))
      failure=acceptance_error('visual',s,require_complete=False)
      if failure:finish(failure);return
      if i==2:finish();return
      s['index']+=1;s['state']='wait';s['next']=t+1
  if t>28:finish('timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('TASK4D_VISUAL01_STARTED')
