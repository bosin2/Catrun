"""Static offscreen editor-world captures; never starts a game or saves a map.

Run UnrealEditor-Cmd -run=pythonscript -AllowCommandletRendering -RenderOffscreen
without -nullrhi. CATRUN_CAPTURE_MAPS may restrict the comma-separated map names.
"""
import json
import hashlib
import os
from pathlib import Path
import sys
import traceback

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from minimap_geometry import MAP_NAMES, capture_plan

OUT = ROOT / 'Saved/ChaptersFlow20261112/Captures'
OUT.mkdir(parents=True, exist_ok=True)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
RL = u.RenderingLibrary


def dirty():
    return [p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


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
        component.set_editor_property('capture_source', u.SceneCaptureSource.SCS_BASE_COLOR if ortho else u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        if ortho:
            component.set_editor_property('projection_type', u.CameraProjectionMode.ORTHOGRAPHIC)
            component.set_editor_property('ortho_width', ortho)
        else:
            component.set_editor_property('fov_angle', 64.)
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


def minimap_capture(world, name, frame, floors, walls):
    # Render the actual mesh footprints with readable map colors. Overrides are
    # transient and restored before the unmodified stage beauty capture.
    parent = u.EditorAssetLibrary.load_asset('/Engine/BasicShapes/BasicShapeMaterial')
    assert 'Color' in {str(p) for p in u.MaterialEditingLibrary.get_vector_parameter_names(parent)}
    original = []
    try:
        for actors, color in ((floors, u.LinearColor(.18, .21, .26, 1)),
                              (walls, u.LinearColor(.68, .58, .38, 1))):
            material = u.MaterialLibrary.create_dynamic_material_instance(world, parent)
            material.set_vector_parameter_value('Color', color)
            for actor in actors:
                component = actor.static_mesh_component
                for index in range(component.get_num_materials()):
                    original.append((component, index, component.get_material(index)))
                    component.set_material(index, material)
        return capture(world, 'Minimap_' + name,
            u.Vector(*frame['center'], frame['capture_z']), u.Rotator(pitch=-90, yaw=0, roll=0),
            floors + walls, 1024, 1024, frame['size'][0])
    finally:
        for component, index, material in original:
            component.set_material(index, material)


def beauty_capture(world, name, position, focus):
    light = ACTORS.spawn_actor_from_class(u.DirectionalLight, u.Vector(0, 0, 2000),
        u.Rotator(pitch=-55, yaw=45, roll=0), transient=True)
    try:
        component = light.get_component_by_class(u.DirectionalLightComponent)
        component.set_editor_property('intensity', 8.)
        component.set_editor_property('cast_shadows', False)
        return capture(world, 'Chapter_' + name, u.Vector(*position),
            u.MathLibrary.find_look_at_rotation(u.Vector(*position), u.Vector(*focus)),
            beauty_actors(world), 1280, 720)
    finally:
        ACTORS.destroy_actor(light)


def main():
    assert not ED.get_game_world() and not dirty()
    assert u.SystemLibrary.get_console_variable_int_value('r.RHICmdBypass') is not None
    path = OUT / 'manifest.json'
    report = json.loads(path.read_text(encoding='utf8')) if path.exists() else {'maps': {}, 'chapters': {}}
    requested = os.environ.get('CATRUN_CAPTURE_MAPS', ','.join(MAP_NAMES)).split(',')
    try:
        for name in requested:
            assert name in MAP_NAMES
            assert LEVEL.load_level('/Game/Maps/' + name)
            world = ED.get_editor_world()
            frame, floors, walls = capture_plan(world)
            geometry = sorted((actor.static_mesh_component.static_mesh.get_path_name(),
                               actor.get_actor_transform().export_text(), role)
                              for role, actors in (('floor', floors), ('wall', walls)) for actor in actors)
            frame['geometry_sha256'] = hashlib.sha256(json.dumps(geometry).encode()).hexdigest()
            canonical = report['maps'].get(name.removeprefix('SoundTest_'), {})
            if name.startswith('SoundTest_') and canonical.get('geometry_sha256') == frame['geometry_sha256']:
                frame['image'] = canonical['image']
                frame['identical_geometry_capture'] = name.removeprefix('SoundTest_')
            else:
                frame['image'] = minimap_capture(world, name, frame, floors, walls)
            frame['floor_labels'] = [a.get_actor_label() for a in floors]
            frame['wall_labels'] = [a.get_actor_label() for a in walls]
            report['maps'][name] = frame
            if not name.startswith('SoundTest_'):
                position, focus = {
                    'Tutorial': ((-400., -600., 1030.), (100., -100., 60.)),
                    'Stage1': ((-100., -300., 1100.), (600., 350., 75.)),
                    'Stage2': ((400., 2000., 1500.), (1375., 3100., 40.)),
                }[name]
                report['chapters'][name] = beauty_capture(world, name, position, focus)
            assert not ED.get_game_world()
            # Transient capture actors may dirty the in-memory editor world. No
            # map package is saved; every following load is from its disk asset.
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
        report['completed'] = all(name in report['maps'] for name in MAP_NAMES)
        report.pop('error', None)
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
        print('CATRUN_STATIC_CAPTURE_REPORT', str(path))


main()
