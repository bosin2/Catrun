"""User-requested Stage3-only X-side camera orbit, without reflecting the map."""
import json,hashlib,shutil
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve();OUT=ROOT/'Saved/Stage3CameraXReverse20261125'
OUT.mkdir(parents=True,exist_ok=True)
ED=u.get_editor_subsystem(u.UnrealEditorSubsystem);ACT=u.get_editor_subsystem(u.EditorActorSubsystem)
assert ED.get_editor_world().get_path_name()=='/Game/Maps/Stage3.Stage3' and not ED.get_game_world()
assert not (OUT/'applied.json').exists()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'Content/Maps/Stage1.umap',ROOT/'Content/Maps/Stage2.umap',ROOT/'Content/Systems/Camera/BP_QuarterViewCamera.uasset']}
actors=list(ACT.get_all_level_actors());cam=next(a for a in actors if a.get_actor_label()=='S3_FollowCamera')
transforms={a.get_path_name():a.get_actor_transform().export_text() for a in actors if a!=cam}
old=cam.get_actor_rotation();assert abs(old.yaw+45)<.01,str(old)
shutil.copy2(ROOT/'Content/Maps/Stage3.umap',OUT/'Stage3_before.umap')
cam.set_actor_rotation(u.Rotator(pitch=old.pitch,yaw=-135,roll=old.roll),True)
view=cam.get_component_by_class(u.CameraComponent)
assert abs(view.get_world_rotation().yaw+135)<.01
assert not cam.get_component_by_class(u.SpringArmComponent).get_editor_property('do_collision_test')
assert view.get_editor_property('ortho_width')==900
assert all(a.get_actor_transform().export_text()==transforms[a.get_path_name()] for a in actors if a!=cam)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
assert all(digest(ROOT/p)==h for p,h in protected.items())
(OUT/'applied.json').write_text(json.dumps({'success':True,'before_yaw':old.yaw,'after_yaw':cam.get_actor_rotation().yaw,'scope':'Stage3 placed camera only; X side reversed','protected_sha256':protected,'other_actor_transforms_unchanged':len(transforms),'saved_map_sha256':digest(ROOT/'Content/Maps/Stage3.umap')},indent=2))
print('STAGE3_CAMERA_X_REVERSED_ONLY',cam.get_actor_rotation().yaw)
