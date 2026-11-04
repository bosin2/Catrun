"""Real native doorway approach, door playback and capture interruption; runtime setup only."""
import unreal,time,json,traceback,math
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/Door01';OUT.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not ed.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
s={'start':time.monotonic(),'samples':[],'shots':[],'results':[],'case':'normal'}
def v(x):return [x.x,x.y,x.z]
def finish(err=None):
 s['error']=err;(OUT/'observations.json').write_text(json.dumps({k:x for k,x in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def send(a,p):
 e=unreal.CatrunSoundEvent();e.location=p;e.kind=unreal.CatrunSoundKind.FOOTSTEP;e.size=unreal.CatrunSoundSize.LARGE;a.on_sound_heard(e,1000)
def tick(dt):
 try:
  t=time.monotonic()-s['start'];w=ed.get_game_world()
  if w:
   game=unreal.GameplayStatics.get_time_seconds(w);aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor);cat=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0);doors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunDoor)
   if aa and cat and doors:
    a=aa[0];m=a.get_editor_property('Mesh');cap=a.get_editor_property('CapturePresentation');inst=m.get_anim_instance();mt=inst.get_current_active_montage();pos=inst.montage_get_position(mt) if mt else 0;asset=a.get_editor_property('LastRequestedAsset');phase=cap.get_editor_property('Phase').name
    door=next((x for x in doors if x.get_name()==s.get('door')),None)
    if game>1 and 'door' not in s:
     door=min(doors,key=lambda x:x.get_actor_location().distance(a.get_actor_location()));s['door']=door.get_name();s['cat_z']=cat.get_actor_location().z;s['base_cat']=v(cat.get_actor_location());s['base_view']=pc.get_view_target().get_name()
     gate=door.get_editor_property('GateBox');s['center']=v(gate.get_world_location());s['normal']=v(gate.get_right_vector());s['armor_z']=a.get_actor_location().z
     for x in aa[1:]:x.set_actor_tick_enabled(False)
     a.set_editor_property('PatrolPoints',[]);a.set_editor_property('ArrivalLookAnim',None);a.set_editor_property('SoundReactAnim',None);s['reset']=True
    if s.pop('reset',False):
     center=unreal.Vector(*s['center']);normal=unreal.Vector(*s['normal']);normal.z=0;at=center+normal*130;at.z=s['armor_z'];target=center-normal*180;target.z=s['armor_z'];door.set_open(False);a.set_actor_location(at,False,True);a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(at,target),True);send(a,target);s['case_start']=game
     cam=pc.get_view_target();cam.set_actor_tick_enabled(False);cc=cam.get_component_by_class(unreal.CameraComponent);cc.set_projection_mode(unreal.CameraProjectionMode.PERSPECTIVE);cc.set_field_of_view(75);cam_at=center+unreal.Vector(340,-290,210);cc.set_world_location_and_rotation(cam_at,unreal.MathLibrary.find_look_at_rotation(cam_at,center+unreal.Vector(0,0,70)),False,True)
    if door:
     action=str(a.get_action());ac=a.get_component_by_class(unreal.CapsuleComponent);ccat=cat.get_component_by_class(unreal.CapsuleComponent);al=ac.get_world_location();cl=ccat.get_world_location();r=ac.get_scaled_capsule_radius()+ccat.get_scaled_capsule_radius();gap=max(0,abs(al.z-cl.z)-(ac.get_scaled_capsule_half_height()-ac.get_scaled_capsule_radius())-(ccat.get_scaled_capsule_half_height()-ccat.get_scaled_capsule_radius()));clear=math.sqrt((al.x-cl.x)**2+(al.y-cl.y)**2+gap*gap)-r
     row={'game':game,'case':s['case'],'action':action,'phase':phase,'asset':asset.get_name() if asset else None,'position':pos,'rate':inst.montage_get_play_rate(mt) if mt else None,'actor':v(a.get_actor_location()),'pelvis':v(m.get_socket_location('pelvis')),'scale':v(m.get_relative_scale3d()),'door_open':door.is_open(),'leaf_yaw':door.get_editor_property('DoorMesh').get_world_rotation().yaw,'capsule_clearance':clear};s['samples'].append(row)
     if asset and 'Door' in asset.get_name() and 'OPENING_DOOR' in action:
      s['seen_'+s['case']]=True
      for mark in [1,3,5.5]:
       key=s['case']+'-'+str(mark)
       if pos>=mark and key not in s['shots']:s['shots'].append(key);unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/(key+'.png')).replace('\\','/')+'"')
      if s['case']=='interrupt' and pos>3 and not s.get('injected'):
       at=m.get_socket_location('pelvis')+a.get_actor_forward_vector()*65;at.z=s['cat_z'];cat.set_actor_location(at,False,True);s['injected']=game;s['pre_interrupt']=row
     if s['case']=='normal' and s.get('seen_normal') and 'OPENING_DOOR' not in action:
      s['results'].append({'case':'normal_complete',**row});s['case']='interrupt';s['reset']=True
     if s['case']=='interrupt' and phase=='HOLDING' and not s.get('held'):
      s['held']=game;s['results'].append({'case':'capture_held',**row});unreal.SystemLibrary.execute_console_command(w,'Shot filename="'+str(OUT/'capture-held.png').replace('\\','/')+'"')
     if s.get('held') and game>s['held']+.6:
      a.set_actor_tick_enabled(False);cap.abort_capture();s['results'].append({'case':'abort','cat_class':cat.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_class().get_name(),'collision':cat.get_actor_enable_collision(),'view_restored':pc.get_view_target().get_name()==s['base_view'],'move_restored':not pc.is_move_input_ignored(),'scale':v(m.get_relative_scale3d()),'door_open':door.is_open()});finish();return
  if t>38:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('DOOR01_STARTED')
