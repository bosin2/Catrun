"""Latest amber reference lighting: modify existing fixture lights, never save map.

Import is inert. Root calls apply() in the Stage3 editor writer slot. Uses
dressing.py's absolute defaults, so both full rebuild and repeated tuning agree.
No gameplay actors, light positions, attenuation ranges or shared assets change.
"""
import unreal as u

POINT_PROPERTIES = ('intensity', 'temperature', 'use_temperature', 'light_color',
                    'source_radius', 'soft_source_radius', 'attenuation_radius',
                    'intensity_units', 'cast_shadows')
KEY_PROPERTIES = ('intensity', 'light_color', 'use_temperature', 'light_source_angle', 'cast_shadows')
SKY_PROPERTIES = ('intensity', 'light_color', 'source_type', 'cubemap')
POST_PROPERTIES = ('override_auto_exposure_method', 'auto_exposure_method',
                   'override_auto_exposure_apply_physical_camera_exposure',
                   'auto_exposure_apply_physical_camera_exposure',
                   'override_auto_exposure_bias', 'auto_exposure_bias',
                   'override_bloom_intensity', 'bloom_intensity')
GRAY = '/Engine/EditorMaterials/AssetViewer/T_GreyAmbient.T_GreyAmbient'


def _read(obj, names):
    return {name: obj.get_editor_property(name) for name in names}


def _encode(value):
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, u.Object):
        return value.get_path_name()
    if isinstance(value, (u.LinearColor, u.Color)):
        return [value.r, value.g, value.b, value.a]
    return str(value)


def apply():
    import dressing
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not editor.get_game_world(), 'End PIE before reference lighting changes'
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    labels = {}
    for actor in actors:
        labels.setdefault(actor.get_actor_label(), []).append(actor)

    def one(label):
        matches = labels.get(label, [])
        assert len(matches) == 1, (label, len(matches))
        return matches[0]

    specs = dressing.reference_light_targets()
    assert len(specs) == 33
    defaults = dressing.LIGHTING_DEFAULTS
    neutral = u.load_object(None, GRAY)
    assert neutral
    bindings, states = {}, {}
    # Preflight all fixtures/positions before any mutation. Keep emitter geometry
    # and local influence ranges fixed while making incident light warmer/softer.
    for label, spec in specs.items():
        actor, fixture = one(label), one(spec['fixture'])
        assert dressing.OWNER in map(str, actor.tags) and dressing.OWNER in map(str, fixture.tags)
        comp = actor.get_component_by_class(u.PointLightComponent)
        assert comp and comp.get_editor_property('intensity_units') == u.LightUnits.CANDELAS, label
        position = actor.get_actor_location()
        assert max(abs(a - b) for a, b in zip((position.x, position.y, position.z), spec['location'])) < .1, ('Light moved', label)
        assert abs(comp.get_editor_property('attenuation_radius') - spec['attenuation_radius']) < .1, ('Light range drift', label)
        bindings[label] = comp
        states[label] = _read(comp, POINT_PROPERTIES)
    key = one('S3_KeyLight').get_component_by_class(u.DirectionalLightComponent)
    fill = one('S3_FillLight').get_component_by_class(u.DirectionalLightComponent)
    sky = one('S3_AmbientSkyLight').get_component_by_class(u.SkyLightComponent)
    post = one('S3_Exposure')
    assert key and fill and sky and isinstance(post, u.PostProcessVolume)
    before_key, before_fill = _read(key, KEY_PROPERTIES), _read(fill, KEY_PROPERTIES)
    before_sky = _read(sky, SKY_PROPERTIES)
    before_post = _read(post.get_editor_property('settings'), POST_PROPERTIES)
    transforms = {actor.get_path_name(): actor.get_actor_transform().export_text() for actor in actors}
    meshes = {comp.get_path_name(): [comp.get_material(i) for i in range(comp.get_num_materials())]
              for actor in actors for comp in actor.get_components_by_class(u.MeshComponent)}
    report = {'success': False,
              'reference': 'User amber-lantern Gothic guard facility image, latest instruction',
              'before': {'points': _encode(states), 'key': _encode(before_key),
                         'fill': _encode(before_fill), 'sky': _encode(before_sky), 'postprocess': _encode(before_post)},
              'point_fixture_pairs': {label: spec['fixture'] for label, spec in specs.items()},
              'packages_saved': False, 'visual_qa': 'pending actual player-camera comparison to latest reference'}
    try:
        for label, comp in bindings.items():
            spec = specs[label]
            comp.set_intensity(float(spec['intensity']))
            comp.set_light_color(u.LinearColor(1, 1, 1, 1))
            comp.set_editor_property('use_temperature', True)
            for prop in ('temperature', 'source_radius', 'soft_source_radius'):
                comp.set_editor_property(prop, float(spec[prop]))
        key.set_intensity(defaults['key_intensity'])
        key.set_light_color(u.LinearColor(1, 1, 1, 1))
        key.set_editor_property('use_temperature', False)
        key.set_editor_property('light_source_angle', defaults['key_source_angle'])
        # Existing shadowless neutral fill opens masonry/black-iron midshadows.
        # The local amber points are reduced simultaneously to retain contrast.
        fill.set_intensity(defaults['fill_intensity'])
        fill.set_light_color(u.LinearColor(1, 1, 1, 1))
        fill.set_editor_property('use_temperature', False)
        fill.set_cast_shadows(False)
        sky.set_intensity(defaults['sky_intensity'])
        sky.set_light_color(u.LinearColor(1, 1, 1, 1))
        sky.set_editor_property('source_type', u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
        sky.set_cubemap(neutral)
        settings = post.get_editor_property('settings')
        changes = {
            'override_auto_exposure_method': True, 'auto_exposure_method': u.AutoExposureMethod.AEM_MANUAL,
            'override_auto_exposure_apply_physical_camera_exposure': True,
            'auto_exposure_apply_physical_camera_exposure': False,
            'override_auto_exposure_bias': True, 'auto_exposure_bias': defaults['exposure_bias'],
            'override_bloom_intensity': True, 'bloom_intensity': defaults['bloom_intensity'],
        }
        for prop, value in changes.items():
            settings.set_editor_property(prop, value)
        post.set_editor_property('settings', settings)
        for label, comp in bindings.items():
            spec = specs[label]
            for prop in ('intensity', 'temperature', 'source_radius', 'soft_source_radius', 'attenuation_radius'):
                assert abs(comp.get_editor_property(prop) - spec[prop]) < .001, (label, prop)
            assert comp.get_editor_property('cast_shadows') == states[label]['cast_shadows']
        assert abs(fill.get_editor_property('intensity') - defaults['fill_intensity']) < .001
        assert not fill.get_editor_property('cast_shadows') and not fill.get_editor_property('use_temperature')
        assert abs(key.get_editor_property('intensity') - defaults['key_intensity']) < .001
        assert abs(sky.get_editor_property('intensity') - defaults['sky_intensity']) < .001
        for actor in actors:
            assert actor.get_actor_transform().export_text() == transforms[actor.get_path_name()], actor.get_actor_label()
            for comp in actor.get_components_by_class(u.MeshComponent):
                assert [comp.get_material(i) for i in range(comp.get_num_materials())] == meshes[comp.get_path_name()]
    except Exception:
        for label, comp in bindings.items():
            for prop, value in states[label].items():
                comp.set_editor_property(prop, value)
        for obj, previous in ((key, before_key), (fill, before_fill), (sky, before_sky)):
            for prop, value in previous.items():
                obj.set_editor_property(prop, value)
        settings = post.get_editor_property('settings')
        for prop, value in before_post.items():
            settings.set_editor_property(prop, value)
        post.set_editor_property('settings', settings)
        raise
    report['after'] = {
        'points': {label: _encode(_read(comp, POINT_PROPERTIES)) for label, comp in bindings.items()},
        'key': _encode(_read(key, KEY_PROPERTIES)), 'fill': _encode(_read(fill, KEY_PROPERTIES)),
        'sky': _encode(_read(sky, SKY_PROPERTIES)),
        'postprocess': _encode(_read(post.get_editor_property('settings'), POST_PROPERTIES)),
    }
    report['transforms_and_material_bindings_unchanged'] = True
    report['success'] = True
    return report
