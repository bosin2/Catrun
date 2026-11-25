import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3OrientationFix20261125'
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3' and not ED.get_game_world()
settings=json.loads((OUT/'minimap_projection.json').read_text())
task=u.AssetImportTask();task.filename=str(OUT/'T_Floorplan_Stage3.png');task.destination_path='/Game/UI/Minimap';task.destination_name='T_Floorplan_Stage3';task.automated=True;task.save=True;task.replace_existing=True
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
tex=u.EditorAssetLibrary.load_asset('/Game/UI/Minimap/T_Floorplan_Stage3');assert tex
actors=u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
presenter=next(a for a in actors if a.get_actor_label()=='S3_Minimap')
presenter.set_editor_properties({'BackgroundTexture':tex,'MapCenter':u.Vector2D(*settings['center']),'MapSize':u.Vector2D(*settings['size']),'CaptureYawDegrees':settings['yaw']})
assert LE.save_current_level()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'));import verify
verify.OUT=OUT/'QA';verify.snapshot('after')
print('ORIENTATION_FINISH_SAVED')
