"""Controlled offscreen PIE, not a manual complete playthrough.

Run in an isolated normal editor via -ExecCmds="py <this file>" with
-RenderOffscreen -onethread -SaveToUserDir -UserDir=<isolated directory>.
Moves the real cat through the hole twice, tests the real bell denial there,
then drives the armor's normal sound-investigation/door-animation path from
both sides. Placement and perception isolation are explicit fixture setup.
No level/asset/settings writes. Uses engine input, never OS mouse/keyboard.
"""
import json, time, traceback
from pathlib import Path
import unreal as u

ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL=u.get_editor_subsystem(u.LevelEditorSubsystem)
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=Path(u.Paths.project_saved_dir()).resolve()/'TutorialPassagesPIE'
assert str(OUT).startswith(str(ROOT/'Saved/GameplayExpansion20261124'))
OUT.mkdir(parents=True,exist_ok=True)
# Background throttling is disabled by the isolated process's -ini override.
# EditorPerformanceSettings is not exposed as a Python type in UE 5.8.
assert not ED.get_game_world()
assert LEVEL.load_level('/Game/Maps/Tutorial')
S={'start':time.monotonic(),'phase':'ready','events':[],'samples':[],
   'scope':'Controlled real movement and armor animation in PIE; fixture relocations, candle tick disabled, capture disabled. No manual-play claim.'}

def v(p):return [round(p.x,4),round(p.y,4),round(p.z,4)]
def event(name,**data):S['events'].append({'name':name,**data})
def save():
 (OUT/'report.json').write_text(json.dumps({k:v for k,v in S.items() if k!='handle'},ensure_ascii=False,indent=2),encoding='utf8')
def change(phase,game):S.update(phase=phase,changed_game=game)
def hit_info(hit):
 if not hit:return None
 d=hit.to_dict();a=d.get('hit_actor');c=d.get('hit_component')
 return {'actor':a.get_name() if a else None,'component':c.get_name() if c else None,'point':v(d['impact_point'])}
def sweep(w,a,start,end,ignored):
 c=a.get_component_by_class(u.CapsuleComponent)
 return u.SystemLibrary.capsule_trace_single_by_profile(w,start,end,c.get_scaled_capsule_radius(),c.get_scaled_capsule_half_height(),'Pawn',False,ignored,u.DrawDebugTrace.NONE,False)
def finish(error=None):
 S['error']=error;S['complete']=error is None;S['elapsed_wall_seconds']=time.monotonic()-S['start'];save()
 LEVEL.editor_request_end_play();S['phase']='shutdown';S['shutdown']=time.monotonic()

def tick(delta):
 try:
  if S['phase']=='shutdown':
   if not ED.get_game_world() and time.monotonic()-S['shutdown']>1:
    u.unregister_slate_post_tick_callback(S['handle'])
    u.SystemLibrary.execute_console_command(ED.get_editor_world(),'QUIT_EDITOR')
   return
  if time.monotonic()-S['start']>210:finish('PIE watchdog expired');return
  w=ED.get_game_world()
  if not w:return
  game=u.GameplayStatics.get_time_seconds(w)
  cat=u.GameplayStatics.get_player_pawn(w,0);pc=u.GameplayStatics.get_player_controller(w,0)
  if not cat or not pc:return
  if S['phase']=='ready':
   if game<2 or u.CatrunLevelFlowLibrary.should_hide_gameplay_hud(w):return
   u.SystemLibrary.execute_console_command(w,'catrun.NoArmorCapture 1')
   for a in u.GameplayStatics.get_all_actors_of_class(w,u.CatrunCandle):a.set_actor_tick_enabled(False)
   for a in u.GameplayStatics.get_all_actors_of_class(w,u.CatrunArmor):a.set_actor_tick_enabled(False)
   cat.set_actor_location(u.Vector(-275,410,26.25),False,True)
   event('fixture_ready',game=game,cat=v(cat.get_actor_location()))
   change('hole_forward',game);return
  armors=u.GameplayStatics.get_all_actors_of_class(w,u.CatrunArmor)
  armor=next(a for a in armors if a.get_actor_label()=='Armor_Tutorial')
  doors=u.GameplayStatics.get_all_actors_of_class(w,u.CatrunDoor)
  door=next(a for a in doors if a.get_actor_label()=='Door_Tutorial_Bedroom')
  actions=next(c for c in cat.get_components_by_class(u.ActorComponent) if c.get_class().get_name()=='BP_CatActions_C')
  phase=S['phase'];pos=cat.get_actor_location()
  if phase in ('hole_forward','hole_reverse'):
   target=520 if phase=='hole_forward' else 410
   if abs(pos.y-target)<4:
    event(phase+'_passed',game=game,cat=v(pos),elapsed_game=game-S['changed_game'])
    if phase=='hole_forward':change('hole_reverse',game)
    else:change('door_prepare_positive',game)
   else:
    assert abs(pos.x+275)<4, ('Hole path drifted',v(pos))
    cat.add_movement_input(u.Vector(0,1 if target>pos.y else -1,0),1,False)
    if abs(pos.y-465)<5 and not S.get('hole_bell_checked'):
     bell=cat.get_component_by_class(u.CatrunBellComponent)
     state=bell.get_bell_status();before=actions.get_editor_property('LastBellTime')
     actions.call_method('TryBell')
     assert 'CAT_HOLE' in str(state.reason) and actions.get_editor_property('LastBellTime')==before
     S['hole_bell_checked']=True;event('actual_hole_bell_denied',game=game,reason=str(state.reason))
    assert game-S['changed_game']<6, ('Actual cat stalled in hole',v(pos))
   return
  if phase.startswith('door_prepare_'):
   side=1 if phase.endswith('positive') else -1
   center=door.get_editor_property('GateBox').get_world_location()
   if not S.get('capsules_checked'):
    ignored=[cat,*armors]
    closed=sweep(w,cat,u.Vector(-128,390,26.25),u.Vector(-128,528,26.25),ignored)
    blocked=sweep(w,armor,u.Vector(-275,410,87.25),u.Vector(-275,520,87.25),ignored)
    assert closed and blocked, 'Closed leaf/armor-hole blocking missing'
    assert hit_info(closed)['actor']==door.get_name(),hit_info(closed)
    assert 'Trim' not in (hit_info(blocked)['actor'] or ''),hit_info(blocked)
    event('physical_filters',closed_door=hit_info(closed),armor_hole=hit_info(blocked))
    S['capsules_checked']=True
   cat.set_actor_location(u.Vector(-260,-95,26.25),False,True)
   door.set_open(False)
   at=u.Vector(center.x,center.y+side*135,armor.get_actor_location().z)
   armor.set_actor_location(at,False,True)
   armor.set_actor_rotation(u.Rotator(0,-90 if side>0 else 90,0),True)
   armor.set_editor_property('PatrolPoints',[])
   S['side']=side;S['door_seen']=False;S['leaf_angles']=[]
   change('door_settle',game);return
  if phase=='door_settle':
   if game-S['changed_game']<3:return
   center=door.get_editor_property('GateBox').get_world_location()
   target=u.Vector(center.x,center.y-S['side']*175,armor.get_actor_location().z)
   sound=u.CatrunSoundEvent();sound.location=target;sound.kind=u.CatrunSoundKind.BELL;sound.size=u.CatrunSoundSize.LARGE
   armor.set_actor_tick_enabled(True)
   armor.on_sound_heard(sound,1000)
   event('armor_sound_fixture',side=S['side'],target=v(target),game=game)
   change('door_motion',game);return
  if phase=='door_motion':
   leaf=door.get_editor_property('DoorMesh');action=str(armor.get_action())
   mesh=armor.get_component_by_class(u.SkeletalMeshComponent)
   asset=armor.get_editor_property('LastRequestedAsset')
   if 'OPENING_DOOR' in action:S['door_seen']=True
   if game-S.get('sample_game',-1)>.1:
    S['sample_game']=game
    S['samples'].append({'side':S['side'],'game':game,'action':action,'armor':v(armor.get_actor_location()),
     'asset':asset.get_name() if asset else None,'leaf_yaw':leaf.get_editor_property('relative_rotation').yaw,
     'hinge':v(leaf.get_editor_property('relative_location')),'scale':v(leaf.get_editor_property('relative_scale3d')),'open':door.is_open()})
    S['leaf_angles'].append(leaf.get_editor_property('relative_rotation').yaw)
   center=door.get_editor_property('GateBox').get_world_location()
   crossed=(armor.get_actor_location().y-center.y)*S['side'] < -55
   if S['door_seen'] and crossed and 'OPENING_DOOR' not in action:
    assert door.is_open() and max(S['leaf_angles'])-min(S['leaf_angles'])>30
    event('armor_hand_door_passed',side=S['side'],game=game,armor=v(armor.get_actor_location()),samples=len(S['leaf_angles']))
    armor.set_actor_tick_enabled(False)
    if S['side']==1:change('door_prepare_negative',game)
    else:finish()
   elif game-S['changed_game']>28:finish('Armor did not complete door approach/hand animation/passage on side '+str(S['side']))
 except Exception:finish(traceback.format_exc())

S['handle']=u.register_slate_post_tick_callback(tick)
LEVEL.editor_request_begin_play()
print('TUTORIAL_PASSAGES_PIE_STARTED',str(OUT))
