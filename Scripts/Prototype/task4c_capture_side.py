"""Actual PIE playback with API proximity setup; does not represent a keyboard playthrough."""
import unreal,time,json,traceback
from pathlib import Path
OUT=Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4c/Capture04Side';OUT.mkdir(parents=True,exist_ok=True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage2')
s={'start':time.monotonic(),'samples':[],'shots':[]}
def vec(v):return [v.x,v.y,v.z]
def anim(mesh):
 a=mesh.get_anim_instance();mt=a.get_current_active_montage() if a else None
 return {'mode':str(mesh.get_editor_property('animation_mode')),'instance':a.get_class().get_name() if a else None,'montage':mt.get_path_name() if mt else None,'montage_pos':a.montage_get_position(mt) if mt else None,'montage_rate':a.montage_get_play_rate(mt) if mt else None,'single_asset':str(a.get_animation_asset()) if isinstance(a,unreal.AnimSingleNodeInstance) else None,'single_rate':mesh.get_play_rate(),'single_pos':mesh.get_position()}
def finish(err=None):
 s['error']=err;(OUT/'observations.json').write_text(json.dumps({k:v for k,v in s.items() if k!='handle'},indent=2),encoding='utf8');unreal.unregister_slate_post_tick_callback(s['handle']);levels.editor_request_end_play()
def tick(delta):
 try:
  t=time.monotonic()-s['start'];world=editor.get_game_world()
  if world:
   cat=unreal.GameplayStatics.get_player_pawn(world,0);pc=unreal.GameplayStatics.get_player_controller(world,0);armors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CatrunArmor)
   if cat and pc and armors:
    armor=armors[0];
    if 'original_view_name' not in s:s['original_view_name']=pc.get_view_target().get_name()
    cap=armor.get_editor_property('CapturePresentation');phase=str(cap.get_editor_property('Phase'));am=armor.get_editor_property('Mesh');cm=cat.get_component_by_class(unreal.SkeletalMeshComponent)
    if t>3 and not s.get('placed'):
     pos=armor.get_actor_location()+armor.get_actor_forward_vector()*65;pos.z=cat.get_actor_location().z;cat.set_actor_location(pos,False,True);s['placed']=t
    if t-s.get('last',-10)>.08:
     s['last']=t;context=armor.get_editor_property('CapturePlaybackContext')
     row={'t':t,'world':world.get_path_name(),'action':str(armor.get_action()),'phase':phase,'session':cap.get_editor_property('SessionId'),'armor_actor':vec(armor.get_actor_location()),'armor_yaw':armor.get_actor_rotation().yaw,'cat_actor':vec(cat.get_actor_location()),'cat_yaw':cat.get_actor_rotation().yaw,'cat_pelvis':vec(cm.get_socket_location('pelvis')),'cat_chest':vec(cm.get_socket_location('chest')),'cat_head':vec(cm.get_socket_location('head')),'left_hand':vec(am.get_socket_location('hand_l')),'right_hand':vec(am.get_socket_location('hand_r')),'armor':anim(am),'cat':anim(cm),'view':pc.get_view_target().get_name(),'ignore_move':pc.is_move_input_ignored(),'collision':cat.get_actor_enable_collision()}
     if context:row['context']={p:context.get_editor_property(p) for p in ['OriginSessionId','Canceled','GrabNotifyAccepted','FinishNotifyAccepted']}
     s['samples'].append(row)
     mtpos=row['armor']['montage_pos'];key=None
     if mtpos is not None and mtpos>3 and 'PickupPresentation' in (row['armor']['montage'] or '') and not s.get('side_view'):
      s['side_view']=True
      observer=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if a.get_name()==s['original_view_name'])
      observer.set_actor_tick_enabled(False);cc=observer.get_component_by_class(unreal.CameraComponent);cc.set_projection_mode(unreal.CameraProjectionMode.PERSPECTIVE);cc.set_field_of_view(50)
      at=armor.get_actor_location()+armor.get_actor_right_vector()*190+armor.get_actor_forward_vector()*100+unreal.Vector(0,0,40);focus=armor.get_actor_location()+armor.get_actor_forward_vector()*35+unreal.Vector(0,0,-10);cc.set_world_location_and_rotation(at,unreal.MathLibrary.find_look_at_rotation(at,focus),False,True);pc.set_view_target_with_blend(observer,0)
     if mtpos is not None and row['armor']['montage'] and 'PickupPresentation' in row['armor']['montage']:key='pickup-'+str(int(mtpos*2))
     elif phase not in s['shots']:key=phase.split(':')[0].replace('<','')
     if key and key not in s['shots']:
      s['shots'].append(key);unreal.SystemLibrary.execute_console_command(world,'Shot filename="'+str(OUT/(key+'.png')).replace('\\','/')+'"')
  if t>17:finish()
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play();print('CAPTURE01_STARTED')
