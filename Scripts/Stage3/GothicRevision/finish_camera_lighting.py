"""Final Stage3-only camera, dock visibility and gate opacity repair."""
import sys,json
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts/Stage3/GothicRevision'))
import camera,reference_lighting,interactive_visibility
le=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert le.load_level('/Game/Maps/Stage3')
actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
view=actors['S3_FollowCamera'].get_component_by_class(u.CameraComponent)
assert not view.get_editor_property('update_ortho_planes')
assert view.get_editor_property('ortho_near_clip_plane')==-2000.
light=actors['S3_Gothic_Exhibition_SconceLight10'].get_component_by_class(u.PointLightComponent)
old_radius=light.get_editor_property('attenuation_radius')
assert old_radius in (360.,600.)
light.set_attenuation_radius(600.)
result=reference_lighting.apply()
result['dock_light_range_repair']={'actor':'S3_Gothic_Exhibition_SconceLight10','before':old_radius,'after':600.,'reason':'Existing wall lamp previously ended before dock center; now illuminates its physical iron frame.'}
result['camera']=camera.apply()
result['interactions']=interactive_visibility.apply()
u.CatrunAuthoringLibrary.finish_asset_compilation()
assert le.save_current_level()
result['map_saved']=True
(ROOT/'Saved/Stage3GothicRevision20261125/final_repairs.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('GOTHIC_FINAL_REPAIRS_SAVED')
