"""Migrate explicit native values and add independent presentation actors, keeping director/pedestals."""
import sys,unreal
sys.path.insert(0,unreal.Paths.project_dir()+'Scripts/Prototype')
from task4d_assets import *
lv=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);edworld=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);actorsys=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not edworld.get_game_world()
SET='/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings';backup(SET);settings=AS.load_asset(SET)
for k,v in {'PushSpeed':100.,'PushAcceleration':160.,'PushDeceleration':240.,'ContactDistance':12.,'SeatingOverlap':.8,'SocketAxisTolerance':24.,'SocketHeightTolerance':12.,'PlateTravel':2.,'GateTravel':280.,'GateSpeed':140.,'GateFloorClearance':4.}.items():settings.set_editor_property(k,v)
assert AS.save_loaded_asset(settings,False)
for mapname in ['Stage2','SoundTest_Stage2']:
 path='/Game/Maps/'+mapname;backup(path,'.umap');assert lv.load_level(path)
 actors=actorsys.get_all_level_actors();d=next(a for a in actors if isinstance(a,unreal.CatrunStatuePuzzle));links=d.get_editor_property('Links');rows=[]
 for index,l in enumerate(links):
  key=str(l.get_editor_property('PuzzleId'));gate=l.get_editor_property('Gate');statue=l.get_editor_property('Statue');center,extent=gate.get_actor_bounds(False);offset=20. if key=='C' else 0.
  l.set_editor_property('ContactHalfExtent',unreal.Vector2D(60,60));l.set_editor_property('SocketAxis',unreal.Vector(1,0,0) if key=='B' else unreal.Vector(0,1,0));l.set_editor_property('GateFloorOffset',offset)
  links[index]=l
  existing=[a for a in actors if a.get_actor_label()=='S2_StatuePresentation_'+key];assert len(existing)<2
  a=existing[0] if existing else actorsys.spawn_actor_from_class(AS.load_blueprint_class(PRES),unreal.Vector(center.x,center.y,center.z-extent.z+offset))
  a.set_actor_label('S2_StatuePresentation_'+key);a.set_folder_path('Gameplay/Puzzles/Presentation');a.set_actor_rotation(gate.get_actor_rotation(),False)
  for k,v in {'Director':d,'Statue':statue,'Gate':gate,'PuzzleId':key,'CameraOffset':unreal.Vector(350,350,1200),'RevealOrthoWidth':650.}.items():a.set_editor_property(k,v)
  rows.append({'puzzle':key,'actor':a.get_path_name(),'gate':gate.get_path_name(),'anchor':str(a.get_actor_location()),'offset':offset})
 d.set_editor_property('Links',links);r=d.get_editor_property('Reveal')
 for k,v in {'CameraTravelTime':.65,'CameraReturnTime':.6,'MaximumLockTime':8.}.items():r.set_editor_property(k,v)
 assert lv.save_current_level();(OUT/(mapname+'-migration.json')).write_text(json.dumps(rows,indent=2),encoding='utf8')
assert lv.load_level('/Game/Maps/Stage2');print('TASK4D_MAPS_SAVED')
