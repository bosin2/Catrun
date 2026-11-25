"""Reveal recessed dock surfaces without altering native floor/puzzle geometry.

Root writer calls apply() in the Stage3 editor. Import is inert. Only new owned
floor materials and two noncolliding dark bottom-cap actors are authored.
Never saves a map, changes a source mesh, or moves a native gameplay actor.
"""
import hashlib
import json
from pathlib import Path

import unreal as u

DEST = '/Game/Environment/Stage3/GothicRevision_20261125/DockFloorRecess'
OWNER = 'Stage3DockFloorRecess20261125'
CENTERS = ((-700., 2250.), (760., 2420.))
HALF_WIDTH = 75.
CORNER_SUM = 146.5
CODE = '''float2 A = abs(World.xy - float2(-700.0,2250.0));
float2 B = abs(World.xy - float2(760.0,2420.0));
bool HoleA = A.x < 75.0 && A.y < 75.0 && A.x+A.y < 146.5;
bool HoleB = B.x < 75.0 && B.y < 75.0 && B.x+B.y < 146.5;
return (HoleA || HoleB) ? 0.0 : 1.0;'''
ROOT_OUTPUTS = ('BASE_COLOR', 'NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS',
                'METALLIC', 'SPECULAR', 'EMISSIVE_COLOR', 'OPACITY',
                'WORLD_POSITION_OFFSET', 'REFRACTION')


def _path(obj):
    return obj.get_path_name() if obj else None


def _graph(material):
    ml = u.MaterialEditingLibrary
    result = {'outputs': {}, 'nodes': {}}
    for name in ROOT_OUTPUTS:
        prop = getattr(u.MaterialProperty, 'MP_' + name)
        node = ml.get_material_property_input_node(material, prop)
        result['outputs'][name] = [node.get_name() if node else None,
            ml.get_material_property_input_node_output_name(material, prop) if node else None]
    for node in ml.get_material_expressions(material):
        result['nodes'][node.get_name()] = [node.get_class().get_name(),
            [child.get_name() if child else None for child in ml.get_inputs_for_material_expression(material, node)]]
    return result


def _parameters(instance):
    result = {}
    for name in ('scalar_parameter_values', 'vector_parameter_values', 'texture_parameter_values'):
        rows = []
        for entry in instance.get_editor_property(name):
            info = entry.get_editor_property('parameter_info')
            value = entry.get_editor_property('parameter_value')
            if isinstance(value, u.Object):
                value = _path(value)
            elif isinstance(value, u.LinearColor):
                value = [value.r, value.g, value.b, value.a]
            rows.append([str(info.get_editor_property('name')),
                         str(info.get_editor_property('association')),
                         info.get_editor_property('index'), value])
        result[name] = rows
    return result


def apply(add_bottom_caps=True):
    global CENTERS, CODE
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not editor.get_game_world(), 'End PIE before floor recess authoring'
    ea, ml = u.EditorAssetLibrary, u.MaterialEditingLibrary
    system = u.get_editor_subsystem(u.EditorActorSubsystem)
    actors = list(system.get_all_level_actors())
    labels = {actor.get_actor_label(): actor for actor in actors}
    # Recesses follow the saved puzzle plates, including the corrected plan/world
    # orientation. Canonical authoring coordinates are not world coordinates.
    CENTERS = tuple((labels['S3_Plate'+str(i)].get_actor_location().x,
                     labels['S3_Plate'+str(i)].get_actor_location().y) for i in (1, 2))
    CODE = ('float2 A = abs(World.xy - float2(%f,%f));\n'
            'float2 B = abs(World.xy - float2(%f,%f));\n' % (*CENTERS[0], *CENTERS[1]) +
            'bool HoleA = A.x < 75.0 && A.y < 75.0 && A.x+A.y < 146.5;\n'
            'bool HoleB = B.x < 75.0 && B.y < 75.0 && B.x+B.y < 146.5;\n'
            'return (HoleA || HoleB) ? 0.0 : 1.0;')
    protected_transforms = {actor.get_path_name(): actor.get_actor_transform().export_text()
                            for actor in actors if OWNER not in map(str, actor.tags)}
    root = Path(u.Paths.project_dir()).resolve()
    imported = json.loads((root / 'Saved/Stage3GothicRevision20261125/import_report.json').read_text(encoding='utf8'))
    assert imported.get('success')

    def owned(path):
        if not ea.does_asset_exist(path):
            return None
        obj = ea.load_asset(path)
        assert ea.get_metadata_tag(obj, 'Stage3DockRecessOwner') == OWNER, ('Unowned destination', path)
        return obj

    def original(material):
        if material.get_path_name().startswith(DEST + '/'):
            assert ea.get_metadata_tag(material, 'Stage3DockRecessOwner') == OWNER
            material = ea.load_asset(ea.get_metadata_tag(material, 'Stage3DockRecessSource'))
            assert material, 'Owned floor instance lost original material reference'
        return material

    # Validate dock registration and all source materials before authoring assets.
    for index, center in enumerate(CENTERS, 1):
        for label in ('S3_Plate' + str(index), 'S3_Plate' + str(index) + '_Frame'):
            pos = labels[label].get_actor_location()
            assert abs(pos.x - center[0]) < .01 and abs(pos.y - center[1]) < .01, label
            assert abs(pos.z - .15) < .01, ('Unexpected native floor datum', label, pos.z)
    targets = []
    source_materials = {}
    for actor in actors:
        if not actor.get_actor_label().startswith('S3_Floor_'):
            continue
        center, extent = actor.get_actor_bounds(False)
        overlaps = any(center.x + extent.x > x - HALF_WIDTH and center.x - extent.x < x + HALF_WIDTH
                       and center.y + extent.y > y - HALF_WIDTH and center.y - extent.y < y + HALF_WIDTH
                       for x, y in CENTERS)
        if not overlaps:
            continue
        assert abs(center.z + extent.z) < .1, ('Unexpected native floor top', actor.get_actor_label())
        comp = actor.get_component_by_class(u.StaticMeshComponent)
        assert comp
        previous = [comp.get_material(i) for i in range(comp.get_num_materials())]
        sources = []
        for current in previous:
            assert current
            material = original(current)
            base = material.get_base_material() if isinstance(material, u.MaterialInstanceConstant) else material
            assert base.get_editor_property('blend_mode') == u.BlendMode.BLEND_OPAQUE, ('Preserve unrelated mask; refusing source', _path(material))
            source_materials[_path(material)] = material
            sources.append(material)
        targets.append((actor, comp, previous, sources,
                        comp.get_collision_enabled(), str(comp.get_collision_profile_name()),
                        comp.get_editor_property('static_mesh')))
    assert targets, 'No intersecting original floor tiles'

    resolved = {}
    report = {'success': False, 'hole_centers_cm': [list(x) for x in CENTERS],
              'half_width_cm': HALF_WIDTH, 'corner_sum_cm': CORNER_SUM,
              'method': 'Static world XY octagon mask; no camera/MPC/dither',
              'floor_tiles': [], 'materials': [], 'bottom_caps': [], 'map_saved': False,
              'visual_qa': 'pending raised and depressed dock captures'}
    for path, source in source_materials.items():
        key = hashlib.sha256(path.encode()).hexdigest()[:12]
        parent_path, instance_path = DEST + '/M_DockRecess_' + key, DEST + '/MI_DockRecess_' + key
        base = source.get_base_material() if isinstance(source, u.MaterialInstanceConstant) else source
        source_signature = _graph(base)
        parent = owned(parent_path)
        if not parent:
            parent = ea.duplicate_asset(base.get_path_name(), parent_path)
            assert parent
            ea.set_metadata_tag(parent, 'Stage3DockRecessOwner', OWNER)
            world = ml.create_material_expression(parent, u.MaterialExpressionWorldPosition, -500, 1200)
            mask = ml.create_material_expression(parent, u.MaterialExpressionCustom, -200, 1200)
            entry = u.CustomInput()
            entry.set_editor_property('input_name', 'World')
            mask.set_editor_property('inputs', [entry])
            mask.set_editor_property('output_type', u.CustomMaterialOutputType.CMOT_FLOAT1)
            assert ml.connect_material_expressions(world, '', mask, 'World')
            assert ml.connect_material_property(mask, '', u.MaterialProperty.MP_OPACITY_MASK)
        else:
            mask = ml.get_material_property_input_node(parent, u.MaterialProperty.MP_OPACITY_MASK)
            assert isinstance(mask, u.MaterialExpressionCustom)
        mask.set_editor_property('code', CODE)
        parent.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED)
        parent.set_editor_property('opacity_mask_clip_value', .333)
        preserved = _graph(parent)
        assert source_signature['outputs'] == preserved['outputs'], ('Non-mask output changed', path)
        for name, node in source_signature['nodes'].items():
            assert preserved['nodes'][name] == node, ('Original graph node changed', path, name)
        ml.recompile_material(parent)
        assert ea.save_loaded_asset(parent)

        instance = owned(instance_path)
        if not instance:
            if isinstance(source, u.MaterialInstanceConstant):
                instance = ea.duplicate_asset(source.get_path_name(), instance_path)
            else:
                instance = u.AssetToolsHelpers.get_asset_tools().create_asset(
                    instance_path.rsplit('/', 1)[-1], DEST, u.MaterialInstanceConstant,
                    u.MaterialInstanceConstantFactoryNew())
            assert instance
            ea.set_metadata_tag(instance, 'Stage3DockRecessOwner', OWNER)
            ea.set_metadata_tag(instance, 'Stage3DockRecessSource', path)
        ml.set_material_instance_parent(instance, parent)
        ml.update_material_instance(instance)
        if isinstance(source, u.MaterialInstanceConstant):
            assert _parameters(source) == _parameters(instance), ('Original scalar/vector/texture overrides changed', path)
            assert str(ml.get_material_instance_vector_parameter_value(source, 'ColorTint')) == str(ml.get_material_instance_vector_parameter_value(instance, 'ColorTint'))
            assert ml.get_material_instance_scalar_parameter_value(source, 'Brightness') == ml.get_material_instance_scalar_parameter_value(instance, 'Brightness')
        assert ea.save_loaded_asset(instance)
        assert source_signature == _graph(base), 'Original material was changed'
        resolved[path] = instance
        report['materials'].append({'source': path, 'instance': _path(instance),
                                    'preserved_outputs': source_signature['outputs']})

    try:
        for actor, comp, previous, sources, collision, profile, mesh in targets:
            for index, source in enumerate(sources):
                comp.set_material(index, resolved[_path(source)])
            assert comp.get_collision_enabled() == collision
            assert str(comp.get_collision_profile_name()) == profile
            assert comp.get_editor_property('static_mesh') == mesh
            report['floor_tiles'].append(actor.get_actor_label())
        if add_bottom_caps:
            cube = ea.load_asset('/Engine/BasicShapes/Cube')
            dark = ea.load_asset(imported['materials']['dark_stone']['instance'])
            assert cube and dark
            assert dark.get_base_material().get_editor_property('blend_mode') == u.BlendMode.BLEND_OPAQUE
            for index, (x, y) in enumerate(CENTERS, 1):
                label = 'S3_GothicRecess_Bottom' + str(index)
                cap = labels.get(label)
                if cap:
                    assert OWNER in map(str, cap.tags), ('Unowned cap label', label)
                else:
                    cap = system.spawn_actor_from_class(u.StaticMeshActor, u.Vector(x, y, -5.7), u.Rotator())
                    assert cap
                    cap.set_actor_label(label)
                    cap.tags = [u.Name(OWNER)]
                    cap.set_folder_path('Stage3/GothicRevision/DockRecess')
                comp = cap.static_mesh_component
                comp.set_static_mesh(cube)
                comp.set_material(0, dark)
                cap.set_actor_location(u.Vector(x, y, -5.7), False, True)
                cap.set_actor_scale3d(u.Vector(1.5, 1.5, .01))
                comp.set_collision_profile_name('NoCollision')
                comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
                comp.set_editor_property('can_ever_affect_navigation', False)
                center, extent = cap.get_actor_bounds(False)
                assert abs(center.z + extent.z + 5.2) < .001
                report['bottom_caps'].append({'label': label, 'top_z_cm': center.z + extent.z,
                                               'collision': str(comp.get_collision_enabled())})
        for actor in actors:
            if actor.get_path_name() in protected_transforms:
                assert actor.get_actor_transform().export_text() == protected_transforms[actor.get_path_name()], actor.get_actor_label()
    except Exception:
        for actor, comp, previous, sources, collision, profile, mesh in targets:
            for index, material in enumerate(previous):
                comp.set_material(index, material)
        raise
    report['native_transforms_and_floor_collision_unchanged'] = True
    report['success'] = True
    return report
