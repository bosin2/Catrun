"""Actual normal-walking WASD directions, one guide, cloth playback and room walking.

Cat placement near each basket is an explicit test fixture. Exit and subsequent
walking use player input. Armor capture is disabled in this isolated process only.
"""
import unreal as u,json,time,math,traceback,sys
from pathlib import Path
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve();PREVIEW_ONLY='-BasketRepairPreviewOnly' in u.SystemLibrary.get_command_line();OUT=ROOT/'Saved/BasketRepair20261125'/('WasdPreview' if PREVIEW_ONLY else 'WasdFinal');OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'Scripts/BasketRepair'))
from room_navigation import navigation,exit_obstructions
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem);GS=u.GameplayStatics
S={'phase':'boot','started':time.monotonic(),'map_index':0,'maps':['Stage1','Stage2'],'cases':[],'shots':[]}
ROOM4_ONLY='-BasketRepairRoom4Only' in u.SystemLibrary.get_command_line()
if ROOM4_ONLY:S['maps']=['Stage2'];OUT=ROOT/'Saved/BasketRepair20261125/WasdRoom4';OUT.mkdir(parents=True,exist_ok=True)
def xyz(v):return [v.x,v.y,v.z]
def persist():
 (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k not in ['handle']},ensure_ascii=False,indent=2),encoding='utf8')
def phase(p):S['phase']=p;S['changed']=time.monotonic();persist()
def cmd(w,c):u.SystemLibrary.execute_console_command(w,c)
def key(w,k,on):cmd(w,'Catrun.Basket.TestKey '+k+(' down' if on else ' up'))
def release(w):
 for k in ['W','A','S','D','F']:key(w,k,False)
def pulse(w,k):key(w,k,True);S['release']=[k,time.monotonic()+.12]
def state(a):return str(a.get_editor_property('BasketPhase')).split('.')[-1].split(':')[0]
def cloth(b):return b.get_editor_property('ExternalCloth')
def shot(w,name):
 p=OUT/(name+'.png');cmd(w,('Shot showui -nosuffix filename="' if name.endswith('_selection') else 'HighResShot 1600x900 filename="')+str(p)+'"');S['shots'].append(str(p))
KEYS=['W','D','S','A','WD','SD','SA','WA']
DIRS=['F','FR','R','BR','B','BL','L','FL']
def direction(w,keys):
 yaw=math.radians(GS.get_player_camera_manager(w,0).get_camera_rotation().yaw)
 f=int('W' in keys)-int('S' in keys);r=int('D' in keys)-int('A' in keys);n=math.hypot(f,r)
 return u.Vector((f*math.cos(yaw)-r*math.sin(yaw))/n,(f*math.sin(yaw)+r*math.cos(yaw))/n,0)
def asset_name(c):return c.get_anim_instance().get_animation_asset().get_name()
def expected_clip(b,outward,kind):
 c=cloth(b);origin=c.get_world_location();f=c.get_socket_location('Edge_F')-origin;r=c.get_socket_location('Edge_R')-origin
 angle=math.atan2(f.x*outward.y-f.y*outward.x,f.x*outward.x+f.y*outward.y)
 if f.x*r.y-f.y*r.x<0:angle=-angle
 return 'AN_Cloth_'+kind+'_'+DIRS[int(math.floor(math.degrees(angle)/45+.5))%8]
def hold(w,keys):
 release(w)
 for k in keys:key(w,k,True)

def finish(error=None):
 S['success']=error is None;S['error']=error;phase('shutdown');LEVEL.editor_request_end_play()
def loadmap():
 LEVEL.load_level('/Game/Maps/'+S['maps'][S['map_index']]);cmd(ED.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll');LEVEL.editor_request_begin_play();phase('start_map')
def nextcase(w):
 release(w)
 if S.get('case'):S['cases'].append(S.pop('case'))
 if not S['queue']:LEVEL.editor_request_end_play();phase('end_map');return
 label,target=S['queue'].pop(0);S['case']={'map':S['maps'][S['map_index']],'basket':label,'target':target,'primary':target=='W','approaches':[],'enter_samples':[],'exit_samples':[]};S['angle']=0;phase('position')
def step(w):
 now=time.monotonic();elapsed=now-S['changed'];cat=GS.get_player_character(w,0);pc=GS.get_player_controller(w,0)
 if not cat or not pc:return
 a=cat.get_component_by_class(u.CatrunBasketInteractionComponent);move=cat.get_component_by_class(u.CharacterMovementComponent);mesh=cat.get_component_by_class(u.SkeletalMeshComponent)
 if S.get('release') and now>S['release'][1]:key(w,S.pop('release')[0],False)
 bs={b.get_actor_label():b for b in GS.get_all_actors_of_class(w,u.CatrunHideBasket)};p=S['phase']
 if p=='start_map':
  if GS.get_time_seconds(w)<1 or pc.is_move_input_ignored():return
  u.CatrunUserSettings.set_no_armor_capture_enabled(True)
  stage=int(S['maps'][S['map_index']][-1])
  for b in bs.values():
   assert cloth(b).get_material(0).get_name()==f'M_Cloth_Stage{stage}',str(cloth(b).get_material(0))
  S['queue']=[(label,keys) for label in sorted(bs) if not ROOM4_ONLY or label=='S2_Basket_Room4' for keys in (['W'] if PREVIEW_ONLY else KEYS)];nextcase(w);return
 case=S['case'];b=bs[case['basket']];center=b.get_hidden_location();c=cloth(b)
 if p=='position':
  assert state(a)=='OUTSIDE';assert S['angle']<8,('No entry',case)
  release(w);angle=S['angle']*math.pi/4;pos=center+u.Vector(math.cos(angle)*100,math.sin(angle)*100,0)
  move.stop_movement_immediately();cat.set_actor_location(pos,False,True);move.set_movement_mode(u.MovementMode.MOVE_WALKING);phase('settle');return
 if p=='settle' and elapsed>.4:
  ok=a.can_enter_nearby_basket();case['approaches'].append({'p':xyz(cat.get_actor_location()),'available':ok})
  if not ok:S['angle']+=1;phase('position');return
  assert not c.is_component_tick_enabled();case['expected_enter_clip']=expected_clip(b,cat.get_actor_location()-center,'Enter');pulse(w,'F');phase('enter');return
 if p in ('enter','exit'):
  st=state(a);active='ENTERING' if p=='enter' else 'EXITING'
  if st==active:
   row={'cat_time':mesh.get_position(),'cloth_time':c.get_position(),'cloth_tick':c.is_component_tick_enabled(),'cloth_clip':asset_name(c)}
   assert row['cloth_clip']==case['expected_'+p+'_clip'],row
   samples=case[p+'_samples']
   if not samples or row['cat_time']-samples[-1]['cat_time']>.12:samples.append(row)
   assert abs(row['cat_time']-row['cloth_time'])<.12,row
   if not case.get(p+'_shot') and row['cat_time']>.9 and (case.get('primary')):
    shot(w,case['map']+'_'+case['basket']+'_'+p);case[p+'_shot']=True
   return
  expected='HIDDEN' if p=='enter' else 'OUTSIDE'
  if p=='exit' and st=='HIDDEN' and case['exit_samples']:
   assert not a.get_editor_property('Busy') and a.get_editor_property('IsHidden') and b.get_editor_property('Occupied') and not cat.get_actor_enable_collision() and not mesh.is_visible()
   case.setdefault('late_returns',[]).append({'landing':case['landing'],'physical':exit_obstructions(w,cat,b,u.Vector(*case['landing'])),'samples':case['exit_samples']})
   assert len(case['late_returns'])<=3,('Repeated cancellation',case)
   case['exit_samples']=[];hold(w,case['actual_keys']);phase('select');return
  if st!=expected:assert elapsed<4,('Animation/input did not finish',p,st,case);return
  assert len(case[p+'_samples'])>2
  if p=='enter':
   assert not c.is_component_tick_enabled();assert not mesh.is_visible();assert not cat.get_actor_enable_collision()
   assert a.get_editor_property('ExitWorldDirection').length()<.001 and not a.get_editor_property('CanExit'),'Auto-selected an exit'
   case['actual_keys']=case['target'];case['selections']=[];hold(w,case['actual_keys']);phase('select');return
  assert cat.get_actor_enable_collision() and mesh.is_visible() and not a.get_editor_property('Busy') and not a.get_editor_property('IsHidden') and not b.get_editor_property('Occupied')
  assert (cat.get_actor_location()-u.Vector(*case['landing'])).length()<3,('Wrong landing',case)
  case['restored']={'p':xyz(cat.get_actor_location()),'movement':str(move.movement_mode),'collision':True}
  assert not c.is_component_tick_enabled()
  release(w);phase('normal_walk_ready');return
 if p=='normal_walk_ready' and elapsed>.15:
  for k in case['actual_keys']:key(w,k,True)
  phase('normal_walk_compare');return
 if p=='normal_walk_compare' and elapsed>.18:
  requested=cat.get_last_movement_input_vector();expected=direction(w,case['actual_keys'])
  if requested.length()<=.1 and elapsed<2:return
  assert requested.length()>.1,('No normal walking input',{'phase':state(a),'busy':a.get_editor_property('Busy'),'hidden':a.get_editor_property('IsHidden'),'ignored':pc.is_move_input_ignored(),'position':xyz(cat.get_actor_location()),'movement':str(move.movement_mode),'animation_mode':str(mesh.get_animation_mode()),'pending':xyz(cat.get_pending_movement_input_vector())},case)
  requested=requested/requested.length();case['normal_walk_direction']=xyz(requested)
  assert (requested-expected).length()<.002,('Normal walking differs from exit',xyz(requested),xyz(expected))
  release(w);move.stop_movement_immediately()
  if 'storage' in case['basket'].lower():
   nav=navigation(w,cat,b);case['room_path']=nav['from_cat'];assert case['room_path'],('No walkable connection to corridor',case)
   S['walk_index']=0;S['walk_started']=now;case['walk_samples']=[];phase('walk');return
  nextcase(w);return
 if p=='select' and elapsed>.25:
  expected=direction(w,case['actual_keys']);actual=a.get_editor_property('ExitWorldDirection')
  assert (actual-expected).length()<.002,('Exit snapped away from walking direction',xyz(actual),xyz(expected),case)
  previews=cat.get_components_by_class(u.CatrunBasketExitPreview)
  assert len(previews)<=1 and all(v.get_instance_count()==48 for v in previews),'Multiple exit markers'
  if a.get_editor_property('CanExit'):assert len(previews)==1 and previews[0].is_visible(),'Missing selected exit guide'
  case['selections'].append({'keys':case['actual_keys'],'direction':xyz(actual),'clear':bool(a.get_editor_property('CanExit')),'guide_instances':previews[0].get_instance_count() if previews else 0})
  case['expected_direction']=xyz(actual);release(w);phase('selection_release');return
 if p=='selection_release' and elapsed>.25:
  assert (a.get_editor_property('ExitWorldDirection')-u.Vector(*case['expected_direction'])).length()<.002,'Release changed selection'
  if case.get('primary') and len(case['selections'])==1:shot(w,case['map']+'_'+case['basket']+'_selection')
  phase('confirm');return
 if p=='confirm' and elapsed>.4:
  case['landing']=xyz(a.get_editor_property('ExitWorldLocation'));case['expected_exit_clip']=expected_clip(b,a.get_editor_property('ExitWorldDirection'),'Exit')
  case['clear_at_confirm']=bool(a.get_editor_property('CanExit'));pulse(w,'F');phase('exit' if case['clear_at_confirm'] else 'blocked_confirm');return
 if p=='blocked_confirm' and elapsed>.25:
  assert state(a)=='HIDDEN' and not a.get_editor_property('Busy')
  assert (a.get_editor_property('ExitWorldDirection')-u.Vector(*case['expected_direction'])).length()<.002,'Blocked input auto-redirected'
  case['blocked_confirmed']=True
  # Explicit test input chooses another direction; the game must never choose it.
  tried=[x['keys'] for x in case['selections']];remaining=[k for k in KEYS if k not in tried]
  assert remaining,('No physical direction available',case)
  case['actual_keys']=remaining[0];hold(w,case['actual_keys']);phase('select');return
 if p=='walk':
  release(w);route=case['room_path'];i=S['walk_index']
  while i<len(route) and (u.Vector(*route[i])-cat.get_actor_location()).length()<13:i+=1
  S['walk_index']=i
  if i==len(route):
   assert cat.get_actor_location().x<600;case['walked_out']=xyz(cat.get_actor_location());shot(w,'storage_walked_out');phase('walk_complete');return
  assert now-S['walk_started']<15,('Walk stuck',xyz(cat.get_actor_location()),route,i)
  target=u.Vector(*route[i])-cat.get_actor_location();yaw=math.radians(GS.get_player_camera_manager(w,0).get_camera_rotation().yaw)
  f=target.x*math.cos(yaw)+target.y*math.sin(yaw);r=-target.x*math.sin(yaw)+target.y*math.cos(yaw);length=max(math.hypot(f,r),1)
  if abs(f)/length>.382:key(w,'W' if f>0 else 'S',True)
  if abs(r)/length>.382:key(w,'D' if r>0 else 'A',True)
  if not case['walk_samples'] or now-case['walk_samples'][-1]['time']>.15:case['walk_samples'].append({'time':now,'p':xyz(cat.get_actor_location())})
 if p=='walk_complete' and elapsed>.4:nextcase(w);return
def tick(dt):
 if S.get('in_tick'):return
 S['in_tick']=True
 try:
  w=ED.get_game_world()
  if S['phase']=='shutdown':
   if not w:u.unregister_slate_post_tick_callback(S['handle']);cmd(ED.get_editor_world(),'QUIT_EDITOR')
   return
  assert time.monotonic()-S['started']<900,'Overall timeout'
  assert time.monotonic()-S['changed']<(180 if S['phase']=='start_map' else 40),('Phase timeout',S['phase'])
  if S['phase']=='end_map' and not w:
   S['map_index']+=1
   if S['map_index']==len(S['maps']):finish();return
   loadmap();return
  if w:step(w)
 except Exception:finish(traceback.format_exc())
 finally:S['in_tick']=False
assert '-SaveToUserDir' in u.SystemLibrary.get_command_line()
S['handle']=u.register_slate_post_tick_callback(tick)
try:
 S['cold_materials']={}
 for stage in (1,2,3):
  base='/Game/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125'
  sk=u.EditorAssetLibrary.load_asset(base+f'/Stage{stage}/Meshes/SK_HideBasket_Stage{stage}_Cloth')
  materials=[slot.material_interface for slot in sk.get_editor_property('materials')]
  assert materials and all(m and m.get_name()==f'M_Cloth_Stage{stage}' for m in materials)
  assert all(m.get_editor_property('used_with_skeletal_mesh') for m in materials)
  S['cold_materials'][str(stage)]=[m.get_path_name() for m in materials]
 loadmap()
except Exception:finish(traceback.format_exc())
