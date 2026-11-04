"""Native return-to-post turns, with API sound/heading setup. No saved map changes."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/Turns05Timing';OUT.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
s={'start':time.monotonic(),'samples':[],'triggers':[],'shots':[]}
def vec(v):return [v.x,v.y,v.z]
def sound(armor,pos):
 e=unreal.CatrunSoundEvent();e.location=pos;e.kind=unreal.CatrunSoundKind.FOOTSTEP;e.size=unreal.CatrunSoundSize.LARGE;armor.on_sound_heard(e,1000)
def finish(error=None):
 s['error']=error;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def tick(dt):
 try:
  t=time.monotonic()-s['start'];world=editor.get_game_world()
  if world:
   aa=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor);pc=unreal.GameplayStatics.get_player_controller(world,0)
   if aa and pc:
    a=aa[0];m=a.get_editor_property('Mesh');inst=m.get_anim_instance();mt=inst.get_current_active_montage() if inst else None
    if t>1 and not s.get('setup'):
     s['setup']=True;s['post']=vec(a.get_actor_location());s['post_yaw']=a.get_actor_rotation().yaw
     a.set_editor_property('PatrolPoints',[]);a.set_editor_property('CornerTolerance',40.0);a.set_editor_property('ArrivalLookAnim',None);a.set_editor_property('SoundReactAnim',None)
     for other in aa[1:]:other.set_actor_tick_enabled(False)
     at=a.get_actor_location()+unreal.Vector(270,-190,90);focus=a.get_actor_location()+unreal.Vector(0,0,0);rot=unreal.MathLibrary.find_look_at_rotation(at,focus)
     cam=pc.get_view_target();cam.set_actor_tick_enabled(False);cc=cam.get_component_by_class(unreal.CameraComponent);cc.set_projection_mode(unreal.CameraProjectionMode.PERSPECTIVE);cc.set_field_of_view(55);cc.set_world_location_and_rotation(at,rot,False,True)
    for at,name,angle in [(2,'left',90),(6,'right',-90),(10,'repeated180',180),(15,'interrupted',90)]:
     if t>at and name not in s['triggers']:
      a.set_actor_location(unreal.Vector(*s['post'])+unreal.Vector(0,-130,0),False,True);a.set_actor_rotation(unreal.Rotator(pitch=0,yaw=90+angle,roll=0),True);sound(a,a.get_actor_location());s['scenario']=name;s['scenario_start']=t;s['triggers'].append(name)
    action=str(a.get_action());pos=inst.montage_get_position(mt) if mt else None;asset=a.get_editor_property('LastRequestedAsset')
    if s.get('scenario')=='interrupted' and 'TURNING' in action and pos and pos>.8 and not s.get('interrupted'):
     sound(a,a.get_actor_location()+unreal.Vector(0,-180,0));s['interrupted']=t
    if t-s.get('last',-10)>.01:
     s['last']=t;row={'game_time':unreal.GameplayStatics.get_time_seconds(world),'t':t,'scenario':s.get('scenario'),'action':action,'actor_yaw':a.get_actor_rotation().yaw,'actor':vec(a.get_actor_location()),'pelvis_yaw':m.get_socket_rotation('pelvis').yaw,'root_yaw':m.get_socket_rotation('root').yaw,'chest_yaw':m.get_socket_rotation('chest').yaw,'montage':mt.get_path_name() if mt else None,'asset':asset.get_path_name() if asset else None,'position':pos,'rate':inst.montage_get_play_rate(mt) if mt else None,'mode':str(m.get_editor_property('animation_mode')),'instance':inst.get_class().get_name() if inst else None};s['samples'].append(row)
     if False and 'TURNING' in action:
      key=s.get('scenario','none')+'-'+str(int((t-s['scenario_start'])*10))
      if key not in s['shots']:
       s['shots'].append(key);unreal.SystemLibrary.execute_console_command(world,'Shot filename="'+str(OUT/(key+'.png')).replace('\\','/')+'"')
  if t>21:finish()
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('TURNS01_STARTED')

