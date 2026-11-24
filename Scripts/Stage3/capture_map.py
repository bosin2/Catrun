"""Read-only native Unreal scene captures of the integrated Stage3."""
from pathlib import Path
import unreal as u
ROOT=Path(u.Paths.project_dir()).resolve()
OUT=ROOT/'Saved/Stage3Integration20261125/Visual';OUT.mkdir(parents=True,exist_ok=True)
ACTORS=u.get_editor_subsystem(u.EditorActorSubsystem);RL=u.RenderingLibrary
LE=u.get_editor_subsystem(u.LevelEditorSubsystem);ED=u.get_editor_subsystem(u.UnrealEditorSubsystem)
def capture(world, name, location, rotation, visible, width, height, ortho=None):
    camera = ACTORS.spawn_actor_from_class(u.SceneCapture2D, location, rotation, transient=True)
    try:
        component = camera.get_component_by_class(u.SceneCaptureComponent2D)
        assert component and component.get_owner() == camera
        target = RL.create_render_target2d(world, width, height,
            u.TextureRenderTargetFormat.RTF_RGBA8, u.LinearColor(.015, .018, .025, 1), False)
        component.set_editor_property('texture_target', target)
        component.set_editor_property('capture_every_frame', False)
        component.set_editor_property('capture_on_movement', False)
        component.set_editor_property('primitive_render_mode', u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        component.clear_show_only_components()
        for actor in visible:
            for primitive in actor.get_components_by_class(u.PrimitiveComponent):
                # Scene previews must not bake editor/debug labels or arrows.
                if isinstance(primitive, (u.StaticMeshComponent, u.SkeletalMeshComponent)) \
                        and primitive.is_visible() and not primitive.get_editor_property('hidden_in_game'):
                    component.show_only_component(primitive)
        component.set_editor_property('capture_source', u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        if ortho:
            component.set_editor_property('projection_type', u.CameraProjectionMode.ORTHOGRAPHIC)
            component.set_editor_property('ortho_width', ortho)
        if True:
            component.set_editor_property('fov_angle', 75. if name=='GateHall' else 64.)
            settings = component.get_editor_property('post_process_settings')
            for key, value in [('override_auto_exposure_method', True),
                               ('auto_exposure_method', u.AutoExposureMethod.AEM_MANUAL),
                               ('override_auto_exposure_apply_physical_camera_exposure', True),
                               ('auto_exposure_apply_physical_camera_exposure', False),
                               ('override_auto_exposure_bias', True), ('auto_exposure_bias', 1.0),
                               ('override_vignette_intensity', True), ('vignette_intensity', .18)]:
                settings.set_editor_property(key, value)
            component.set_editor_property('post_process_settings', settings)
        assert u.CatrunAuthoringLibrary.finish_asset_compilation()
        component.capture_scene()
        RL.export_render_target(world, target, str(OUT), name + '.png')
        result = OUT / (name + '.png')
        assert result.is_file() and result.stat().st_size > 2048, (name, 'empty capture')
        return str(result)
    finally:
        ACTORS.destroy_actor(camera)


def beauty_actors(world):
    result = []
    for actor in u.GameplayStatics.get_all_actors_of_class(world, u.Actor):
        label = actor.get_actor_label().lower()
        if any(word in label for word in ('ceiling', 'roof', 'occluder', 'set_descentstair', 'collision', 'accessblocker')):
            continue
        if actor.get_components_by_class(u.PrimitiveComponent):
            result.append(actor)
    return result


assert LE.load_level('/Game/Maps/Stage3')
w=ED.get_editor_world();visible=beauty_actors(w)
assert u.CatrunAuthoringLibrary.finish_asset_compilation()
assert u.CatrunAuthoringLibrary.refresh_sky_lighting(w)
capture(w,'Overview',u.Vector(100,-2500,7000),u.MathLibrary.find_look_at_rotation(u.Vector(100,-2500,7000),u.Vector(100,2125,200)),visible,1200,1800,3300)
capture(w,'GateHall',u.Vector(-200,2850,520),u.Rotator(pitch=-1,yaw=90),visible,1280,720)
capture(w,'Device',u.Vector(190,190,115),u.Rotator(pitch=-17,yaw=117),visible,1024,768)
print('STAGE3_VISUAL_CAPTURE_OK')
