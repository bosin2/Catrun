"""Capture interior views of the three saved chapter maps in an offscreen commandlet."""

import hashlib
import json
import os
from pathlib import Path
import struct
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = Path(os.environ.get('CATRUN_CONTINUE_OUTPUT', str(ROOT / 'Saved/ContinueFollowup/Captures')))
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVELS = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
RENDER = u.RenderingLibrary
SIZE = (1280, 720)

# Camera positions are inside the rooms and below the walls. Each composition
# looks toward the existing feature meshes, with the saved lights still active.
VIEWS = {
    'Tutorial': (
        ('Window', (-235, -190, 184), (177, 5, 106), 83),
        ('Bedroom', (-236, 250, 203), (142, -81, 100), 79),
    ),
    'Stage1': (
        ('Fireplace', (212, 125, 210), (738, 343, 109), 73),
        ('Banquet', (233, 588, 235), (760, 360, 112), 76),
    ),
    'Stage2': (
        ('Gargoyle', (1696, 3924, 215), (1335, 3482, 111), 82),
        ('Window', (1700, 3444, 222), (1325, 3675, 106), 77),
    ),
}
FEATURES = {
    'Tutorial': ('SM_Tutorial_DemonBed', 'SM_Tutorial_WindowFrame', 'SM_Tutorial_Sofa'),
    'Stage1': ('S1_banquet_BanquetTable_Long_02', 'S1_banquet_Fireplace_Gothic_12'),
    'Stage2': ('S2_Prop_Statue_C', 'S2_Prop_Window_Practice_West', 'S2_Gate_11_Bars'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(world, stage, view, location, focus, fov):
    position, aim = u.Vector(*location), u.Vector(*focus)
    rotation = u.MathLibrary.find_look_at_rotation(position, aim)
    camera = ACTORS.spawn_actor_from_class(u.SceneCapture2D, position, rotation, transient=True)
    light = None
    try:
        # A dim bounce from above the lens keeps the dark room detail visible
        # at thumbnail size while the room's own colored lights remain visible.
        light = ACTORS.spawn_actor_from_class(u.PointLight, position + u.Vector(0, 0, 55),
                                             u.Rotator(), transient=True)
        fill = light.get_component_by_class(u.PointLightComponent)
        fill.set_intensity(460 if stage == 'Stage2' else 380)
        fill.set_attenuation_radius(1250)
        fill.set_light_color(u.LinearColor(.72, .79, 1, 1) if stage == 'Stage2'
                             else u.LinearColor(1, .87, .71, 1))
        fill.set_editor_property('cast_shadows', False)

        component = camera.get_component_by_class(u.SceneCaptureComponent2D)
        target = RENDER.create_render_target2d(world, *SIZE, u.TextureRenderTargetFormat.RTF_RGBA8,
                                              u.LinearColor(.015, .018, .025, 1), False)
        for name, value in dict(texture_target=target, capture_every_frame=False,
                                capture_on_movement=False, fov_angle=float(fov),
                                capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
                                primitive_render_mode=u.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST).items():
            component.set_editor_property(name, value)
        component.clear_show_only_components()
        for actor in u.GameplayStatics.get_all_actors_of_class(world, u.Actor):
            if any(word in actor.get_actor_label().lower() for word in
                   ('roof', 'ceiling', 'occluder', 'collision', 'accessblocker', 'set_descentstair')):
                continue
            for mesh in actor.get_components_by_class(u.PrimitiveComponent):
                if isinstance(mesh, (u.StaticMeshComponent, u.SkeletalMeshComponent)) and mesh.is_visible() \
                        and not mesh.get_editor_property('hidden_in_game'):
                    component.show_only_component(mesh)

        settings = component.get_editor_property('post_process_settings')
        for name, value in dict(override_auto_exposure_method=True,
                                auto_exposure_method=u.AutoExposureMethod.AEM_MANUAL,
                                override_auto_exposure_apply_physical_camera_exposure=True,
                                auto_exposure_apply_physical_camera_exposure=False,
                                override_auto_exposure_bias=True, auto_exposure_bias=1.15,
                                override_vignette_intensity=True, vignette_intensity=.14).items():
            settings.set_editor_property(name, value)
        component.set_editor_property('post_process_settings', settings)
        assert u.CatrunAuthoringLibrary.finish_asset_compilation()
        component.capture_scene()
        path = OUT / f'Chapter_{stage}_{view}.png'
        RENDER.export_render_target(world, target, str(OUT), path.name)
        data = path.read_bytes()
        assert len(data) > 2048 and data.startswith(b'\x89PNG\r\n\x1a\n'), path
        assert struct.unpack('>II', data[16:24]) == SIZE, path
        return dict(image=str(path), sha256=digest(path), location=location, focus=focus, fov=fov)
    finally:
        if light:
            ACTORS.destroy_actor(light)
        ACTORS.destroy_actor(camera)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not EDITOR.get_game_world() and not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    names = os.environ.get('CATRUN_CONTINUE_MAPS', ','.join(VIEWS)).split(',')
    map_files = {name: ROOT / 'Content/Maps' / f'{name}.umap' for name in names}
    before = {name: digest(path) for name, path in map_files.items()}
    report = {}
    manifest = OUT / 'manifest.json'
    if manifest.is_file():
        report = json.loads(manifest.read_text(encoding='utf8'))
    for name in names:
        assert LEVELS.load_level('/Game/Maps/' + name), name
        world = EDITOR.get_editor_world()
        assert not EDITOR.get_game_world()
        labels = {actor.get_actor_label(): actor.get_actor_location()
                  for actor in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
        features = {label: [labels[label].x, labels[label].y, labels[label].z] for label in FEATURES[name]}
        report[name] = dict(features=features, views={view[0]: render(world, name, *view) for view in VIEWS[name]},
                            source_sha256=before[name])
        manifest.write_text(json.dumps(report, indent=2), encoding='utf8')
    assert before == {name: digest(path) for name, path in map_files.items()}
    print('CATRUN_CONTINUE_CAPTURE_REPORT', manifest)


if __name__ == '__main__':
    main()
