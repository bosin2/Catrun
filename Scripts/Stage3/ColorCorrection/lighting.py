"""Stage3-only reversible lighting correction. Running this file only probes.

Director integration (after materials):
    import lighting
    result = lighting.apply(allow_write=True, save=False)
    # Review and save the current level explicitly, or use save=True above.
    lighting.restore(result['snapshot'], allow_write=True, save=False)

Never loads another level on apply/restore and never saves source assets.
"""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

import unreal as u

MAP = '/Game/Maps/Stage3'
GRAY = '/Engine/EditorMaterials/AssetViewer/T_GreyAmbient.T_GreyAmbient'
EXPOSURE_PROPERTIES = (
    'override_auto_exposure_method', 'auto_exposure_method',
    'override_auto_exposure_apply_physical_camera_exposure',
    'auto_exposure_apply_physical_camera_exposure',
    'override_auto_exposure_bias', 'auto_exposure_bias',
    'override_auto_exposure_min_brightness', 'auto_exposure_min_brightness',
    'override_auto_exposure_max_brightness', 'auto_exposure_max_brightness',
)
EXPOSURE_CHANGES = {
    'override_auto_exposure_method': True,
    'auto_exposure_method': u.AutoExposureMethod.AEM_MANUAL,
    'override_auto_exposure_apply_physical_camera_exposure': True,
    'auto_exposure_apply_physical_camera_exposure': False,
    'override_auto_exposure_bias': True,
    'auto_exposure_bias': 0.0,
}
INTENSITIES = {'S3_KeyLight': .45, 'S3_FillLight': .14,
               'S3_AmbientSkyLight': .35}
INTENSITIES.update({'S3_LocalLight' + str(i): 18.0 if i < 5 else 40.0
                    for i in range(9)})


def _root():
    return Path(u.Paths.project_dir()).resolve()


def _out():
    result = _root() / 'Saved/Stage3MaterialCorrection20261125/Lighting'
    result.mkdir(parents=True, exist_ok=True)
    return result


def _json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def _encode(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, u.Object):
        return {'object': value.get_path_name()}
    if isinstance(value, u.AutoExposureMethod):
        return {'exposure_enum': int(value.value)}
    if hasattr(value, 'export_text'):
        return value.export_text()
    return str(value)


def _decode(value):
    if isinstance(value, dict) and 'object' in value:
        result = u.load_object(None, value['object'])
        assert result, value
        return result
    if isinstance(value, dict) and 'exposure_enum' in value:
        return {0: u.AutoExposureMethod.AEM_HISTOGRAM,
                1: u.AutoExposureMethod.AEM_BASIC,
                2: u.AutoExposureMethod.AEM_MANUAL}[value['exposure_enum']]
    return value


def _actors(load_level=False):
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name().split('.')[0] != MAP and load_level:
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP)
        world = editor.get_editor_world()
    assert world.get_path_name().split('.')[0] == MAP, 'Stage3 must already be loaded'
    # Reject PIE worlds even if their original package corresponds to Stage3.
    assert world.get_name() == 'Stage3', world.get_path_name()
    return sorted(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors(),
                  key=lambda a: a.get_path_name())


def _targets(actors):
    labels = list(INTENSITIES) + ['S3_Exposure']
    result = {}
    for label in labels:
        matches = [actor for actor in actors if actor.get_actor_label() == label]
        assert len(matches) == 1, (label, len(matches))
        actor = matches[0]
        if label == 'S3_Exposure':
            assert isinstance(actor, u.PostProcessVolume)
            result[label] = actor
        else:
            cls = u.SkyLightComponent if label == 'S3_AmbientSkyLight' else u.LightComponent
            component = actor.get_component_by_class(cls)
            assert component, label
            if label.startswith('S3_LocalLight'):
                assert isinstance(component, u.PointLightComponent), label
                assert component.get_editor_property('intensity_units') == u.LightUnits.CANDELAS
            result[label] = component
    return result


def _state(targets):
    result = {}
    for label, target in targets.items():
        if label == 'S3_Exposure':
            settings = target.get_editor_property('settings')
            result[label] = {p: _encode(settings.get_editor_property(p))
                             for p in EXPOSURE_PROPERTIES}
        else:
            props = ['intensity']
            if label == 'S3_AmbientSkyLight':
                props += ['cubemap']
            result[label] = {p: _encode(target.get_editor_property(p)) for p in props}
    return result


def _invariants(actors):
    """Readable actor/component transforms, meshes, slot bindings and camera state."""
    result = {}
    for actor in actors:
        row = {'label': actor.get_actor_label(), 'class': actor.get_class().get_path_name(),
               'transform': actor.get_actor_transform().export_text(), 'components': {}}
        for component in actor.get_components_by_class(u.SceneComponent):
            item = {'transform': component.get_relative_transform().export_text()}
            if isinstance(component, u.StaticMeshComponent):
                item['mesh'] = _encode(component.get_editor_property('static_mesh'))
            if isinstance(component, u.MeshComponent):
                item['materials'] = [_encode(component.get_material(i))
                                     for i in range(component.get_num_materials())]
            if isinstance(component, u.CameraComponent):
                for prop in ('field_of_view', 'aspect_ratio', 'post_process_blend_weight'):
                    item[prop] = _encode(component.get_editor_property(prop))
                item['post_process_settings'] = component.get_editor_property('post_process_settings').export_text()
            if isinstance(component, u.SpringArmComponent):
                item['target_arm_length'] = component.get_editor_property('target_arm_length')
            if isinstance(component, u.LightComponent):
                for prop in ('light_color', 'cast_shadows'):
                    item[prop] = _encode(component.get_editor_property(prop))
                if isinstance(component, u.PointLightComponent):
                    for prop in ('attenuation_radius', 'source_radius', 'intensity_units'):
                        item[prop] = _encode(component.get_editor_property(prop))
            row['components'][component.get_name()] = item
        result[actor.get_path_name()] = row
    return result


def probe(load_level=False):
    actors = _actors(load_level)
    report = {'map': MAP, 'state': _state(_targets(actors)),
              'invariants': _invariants(actors), 'packages_saved': False}
    path = _out() / 'probe.json'
    _json(path, report)
    print('STAGE3_LIGHTING_PROBE_OK ' + str(path))
    return report


def _write_state(targets, state):
    for label, properties in state.items():
        target = targets[label]
        if label == 'S3_Exposure':
            settings = target.get_editor_property('settings')
            for prop, value in properties.items():
                settings.set_editor_property(prop, _decode(value))
            target.set_editor_property('settings', settings)
        else:
            for prop, value in properties.items():
                if prop == 'intensity':
                    target.set_intensity(float(value))
                elif prop == 'cubemap':
                    target.set_cubemap(_decode(value))
                else:
                    raise AssertionError('Unexpected lighting property: ' + prop)


def apply(allow_write=False, save=False, normalize_locals=True):
    assert allow_write, 'Director must explicitly authorize the writer slot'
    actors = _actors()
    targets = _targets(actors)
    assert u.load_object(None, GRAY), 'Neutral cubemap must exist before mutation'
    assert targets['S3_AmbientSkyLight'].get_editor_property('source_type') == u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP
    before = _state(targets)
    invariants = _invariants(actors)
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S_%f')
    run = _out() / stamp
    run.mkdir(exist_ok=False)
    source = _root() / 'Content/Maps/Stage3.umap'
    backup = run / 'Stage3.before-lighting.umap'
    shutil.copy2(source, backup)
    snapshot = run / 'before.json'
    _json(snapshot, {'map': MAP, 'state': before, 'invariants': invariants,
                     'disk_backup': str(backup),
                     'disk_backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
                     'note': 'Disk backup contains last saved map; property snapshot includes unsaved lighting state.'})
    desired = {label: {'intensity': value} for label, value in INTENSITIES.items()
               if normalize_locals or not label.startswith('S3_LocalLight')}
    desired['S3_AmbientSkyLight']['cubemap'] = {'object': GRAY}
    desired['S3_Exposure'] = {p: _encode(v) for p, v in EXPOSURE_CHANGES.items()}
    try:
        _write_state(targets, desired)
        assert invariants == _invariants(_actors()), 'Protected scene or camera state changed'
        after = _state(targets)
        for label, properties in desired.items():
            for prop, value in properties.items():
                actual = after[label][prop]
                assert abs(actual - value) < 1e-5 if isinstance(value, float) else actual == value, (label, prop, actual, value)
        if save:
            assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
    except Exception:
        _write_state(targets, before)
        raise
    report = {'map': MAP, 'snapshot': str(snapshot), 'before': before, 'after': after,
              'invariants_equal': True, 'packages_saved': bool(save),
              'local_lights_normalized': normalize_locals,
              'visual_approval': 'pending actual player-camera comparison'}
    _json(run / 'report.json', report)
    print('STAGE3_LIGHTING_APPLY_OK ' + str(run / 'report.json'))
    return report


def restore(snapshot, allow_write=False, save=False):
    assert allow_write, 'Director must explicitly authorize the writer slot'
    data = json.loads(Path(snapshot).read_text(encoding='utf-8'))
    assert data['map'] == MAP
    actors = _actors()
    protected = _invariants(actors)
    targets = _targets(actors)
    _write_state(targets, data['state'])
    assert protected == _invariants(_actors())
    assert data['state'] == _state(targets)
    if save:
        assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
    print('STAGE3_LIGHTING_RESTORE_OK')


if __name__ == '__main__':
    probe(load_level=True)
