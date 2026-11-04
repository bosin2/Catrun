"""Current Stage2 native sinking-gate route test. Run via ue_remote.py --isolated.
API places the cat on the pushing side each frame; TryPushStatue supplies real
acceleration/contact/sweep/floor support. Seating is manually integrated through
native UpdatePlatesAndGates; director Tick resumes for the timed gate/reveal.
This is not a real-input playthrough. No editor-world actors are moved or saved.
"""
import unreal,time,json,traceback,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(unreal.Paths.project_dir())/'Scripts/Prototype'))
from task4d_acceptance import acceptance_error,acceptance_errors
MAP=globals().get('TASK4D_MAP','Stage2')
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d'/('Routes-'+MAP+'-'+time.strftime('%H%M%S'));OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert lv.load_level('/Game/Maps/'+MAP)
points={'A':[(1875,2613)],'B':[(650,1070),(438,1070)],'C':[(1195,3690),(1195,3458)]}
s={'map':MAP,'setup':'API pushing-side placement; manual native push integration with director Tick disabled during each route, restored for timed reveal; not physical-input proof','start':time.monotonic(),'results':[],'samples':[],'index':0,'point':0,'state':'wait','next':2,'blocked_frames':0}
def v(x):return [x.x,x.y,x.z]
def finish(error=None):
 s['acceptance_errors']=acceptance_errors('routes',s);s['error']=error or acceptance_error('routes',s)
 try:(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8')
 finally:unreal.unregister_slate_post_tick_callback(s['handle']);lv.editor_request_end_play()
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunStatuePuzzle);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0)
   if ds and cat and pc:
    d=ds[0];i=s['index'];l=d.get_editor_property('Links')[i];key=str(l.get_editor_property('PuzzleId'));statue=l.get_editor_property('Statue');r=d.get_editor_property('Reveal');phase=r.get_editor_property('Phase').name
    if s['state']=='wait' and t>s['next']:
     for cls in [unreal.CatrunArmor,unreal.CatrunCandle]:
      for a in unreal.GameplayStatics.get_all_actors_of_class(w,cls):a.set_actor_tick_enabled(False)
     d.set_actor_tick_enabled(False);s['state']='push';s['route_start']=t;s['steps']=0;s['blocked_frames']=0;s['start_position']=v(statue.get_actor_location());s['point']=0
    if s['state']=='push' and not l.get_editor_property('bPressed'):
     p=statue.get_actor_location();tx,ty=points[key][s['point']];dx,dy=tx-p.x,ty-p.y
     if max(abs(dx),abs(dy))<1.4 and s['point']<len(points[key])-1:s['point']+=1;tx,ty=points[key][s['point']];dx,dy=tx-p.x,ty-p.y
     direction=unreal.Vector((1 if dx>0 else -1) if abs(dx)>=abs(dy) else 0,(1 if dy>0 else -1) if abs(dy)>abs(dx) else 0,0)
     radius=cat.capsule_component.get_scaled_capsule_radius();at=p-direction*(60+radius+3);at.z=26.2;cat.set_actor_location(at,False,True);cat.character_movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
     remaining=max(abs(dx),abs(dy));step=min(dt,.025,max(.0001,remaining/100))
     moved=d.try_push_statue(i,cat,direction,step);d.update_plates_and_gates(step);s['steps']+=1;s['blocked_frames']=0 if moved else s['blocked_frames']+1;s['last_position']=v(statue.get_actor_location())
     if s['blocked_frames']>20:finish('Route blocked '+key+' at '+str(v(p))+' target '+str((tx,ty)));return
    if s['state']=='push' and d.get_editor_property('Links')[i].get_editor_property('bPressed'):d.set_actor_tick_enabled(True);s['state']='reveal';s['seat_time']=t;s['seat_position']=v(statue.get_actor_location());s['phases']=[]
    if s['state']=='reveal':
     if phase not in s['phases']:s['phases'].append(phase)
     if t-s.get('last_sample',0)>.08:
      s['last_sample']=t;cam=r.get_reveal_camera();p=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation.BP_StatuePresentation_C')) if str(a.get_editor_property('PuzzleId'))==key);cc=cam.get_component_by_class(unreal.CameraComponent) if cam else None
      s['samples'].append({'t':t,'dt':dt,'puzzle':key,'phase':phase,'width':cc.get_editor_property('ortho_width') if cc else None,'active':p.get_editor_property('PresentationActive'),'dust':p.get_editor_property('DustActive'),'dust_components':[{'location':v(c.get_world_location()),'hidden':c.get_editor_property('hidden_in_game'),'visible':c.is_visible(),'material':c.get_material(0).get_path_name()} for c in p.get_components_by_class(unreal.StaticMeshComponent)],'gate_offset':l.get_editor_property('GateOffset')})
     if phase=='INACTIVE' and t-s['seat_time']>3.4:
      s['results'].append({'puzzle':key,'start':s['start_position'],'route':points[key],'steps':s['steps'],'route_wall_seconds':s['seat_time']-s['route_start'],'seat':s['seat_position'],'complete':l.get_editor_property('bCompleted'),'gate_offset':l.get_editor_property('GateOffset'),'gate_top':sum(z.z for z in l.get_editor_property('Gate').get_actor_bounds(False)),'phases':s['phases'],'move_restored':not pc.is_move_input_ignored()})
      failure=acceptance_error('routes',s,require_complete=False)
      if failure:finish(failure);return
      if i==2:finish();return
      s['index']+=1;s['state']='wait';s['next']=t+.5
  if t>60:finish('timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);lv.editor_request_begin_play();print('TASK4D_ROUTES_STARTED',str(OUT))
