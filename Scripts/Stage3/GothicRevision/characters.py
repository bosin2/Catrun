"""Calibrated Stage3-only armor steel; inert on import, root writer calls apply.

Only armor slot 0 is changed. Existing brass, charcoal, joint, skeletal meshes,
animations and every candle slot are preserved. Saves ONLY owned new materials;
the director saves the Stage3 map separately after runtime visual review.
"""
import hashlib
import json
from pathlib import Path

import unreal as u

DEST = '/Game/Environment/Stage3/GothicRevision_20261125/Characters'
OWNER = 'Stage3GothicArmorSteel20261125'
SOURCE = '/Game/Characters/Stage2/A/LivingArmor/Materials/M_ArmorStage2_Steel'
TARGET_SRGB = (72, 71, 74)


def _linear(byte):
    value = byte / 255.
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def _outputs(material):
    ml = u.MaterialEditingLibrary
    result = {}
    for prop in ('NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS', 'METALLIC',
                 'OPACITY_MASK', 'OPACITY', 'EMISSIVE_COLOR', 'WORLD_POSITION_OFFSET'):
        enum = getattr(u.MaterialProperty, 'MP_' + prop)
        node = ml.get_material_property_input_node(material, enum)
        result[prop] = [node.get_name() if node else None,
                        ml.get_material_property_input_node_output_name(material, enum) if node else None]
    return result


def apply():
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not editor.get_game_world(), 'End PIE before character material assignment'
    ea, ml = u.EditorAssetLibrary, u.MaterialEditingLibrary
    root = Path(u.Paths.project_dir()).resolve()
    calibration = json.loads((root / 'Saved/Stage3MaterialCorrection20261125/Materials/calibration.json').read_text(encoding='utf8'))
    source = ea.load_asset(SOURCE)
    assert isinstance(source, u.Material), SOURCE
    source_node = ml.get_material_property_input_node(source, u.MaterialProperty.MP_BASE_COLOR)
    source_output = ml.get_material_property_input_node_output_name(source, u.MaterialProperty.MP_BASE_COLOR)
    assert isinstance(source_node, u.MaterialExpressionTextureSample) and source_output == 'RGB'
    texture = source_node.get_editor_property('texture')
    calibration_row = calibration['textures'][texture.get_path_name()]
    assert hashlib.sha256(Path(calibration_row['source']).read_bytes()).hexdigest() == calibration_row['sha256'], 'Armor steel source texture changed; recalibrate first'
    normalization = [1. / mean for mean in calibration_row['source_mean_linear']]
    tint = [_linear(value) for value in TARGET_SRGB]
    parent_path = DEST + '/M_Gothic_ArmorSteel_Calibrated'
    instance_path = DEST + '/MI_Gothic_ArmorSteel_72_71_74'

    def owned(path):
        if not ea.does_asset_exist(path):
            return None
        asset = ea.load_asset(path)
        assert ea.get_metadata_tag(asset, 'Stage3GothicCharacterOwner') == OWNER, ('Unowned destination', path)
        return asset

    # Validate all six targets and protect all other slots before material writes.
    bindings = []
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if not actor.get_actor_label().startswith('S3_Armor_'):
            continue
        comp = actor.get_component_by_class(u.SkeletalMeshComponent)
        assert comp and comp.get_num_materials() == 4, actor.get_actor_label()
        current = comp.get_material(0)
        assert current and current.get_path_name().split('.')[0] in (SOURCE, instance_path), (actor.get_actor_label(), current)
        bindings.append((actor, comp, comp.get_skinned_asset(),
                         [comp.get_material(index) for index in range(4)]))
    assert len(bindings) == 6, ('Unexpected armor count', len(bindings))
    source_signature = _outputs(source)
    parent = owned(parent_path)
    if not parent:
        parent = ea.duplicate_asset(source.get_path_name(), parent_path)
        assert parent
        ea.set_metadata_tag(parent, 'Stage3GothicCharacterOwner', OWNER)
        base = ml.get_material_property_input_node(parent, u.MaterialProperty.MP_BASE_COLOR)
        assert base.get_editor_property('texture') == texture
        factor = ml.create_material_expression(parent, u.MaterialExpressionConstant3Vector, -350, -500)
        factor.set_editor_property('constant', u.LinearColor(*normalization, 1.))
        factor.set_editor_property('desc', 'Inverse mean linear source texels; preserve texture variation')
        normalized = ml.create_material_expression(parent, u.MaterialExpressionMultiply, -100, -350)
        assert ml.connect_material_expressions(base, 'RGB', normalized, 'A')
        assert ml.connect_material_expressions(factor, '', normalized, 'B')
        color = ml.create_material_expression(parent, u.MaterialExpressionVectorParameter, -100, -600)
        color.set_editor_property('parameter_name', 'ColorTint')
        color.set_editor_property('default_value', u.LinearColor(*tint, 1.))
        color.set_editor_property('group', 'Stage3 Armor Steel')
        output = ml.create_material_expression(parent, u.MaterialExpressionMultiply, 150, -350)
        assert ml.connect_material_expressions(normalized, '', output, 'A')
        assert ml.connect_material_expressions(color, 'RGB', output, 'B')
        brightness = ml.create_material_expression(parent, u.MaterialExpressionScalarParameter, 150, -600)
        brightness.set_editor_property('parameter_name', 'Brightness')
        brightness.set_editor_property('default_value', 1.)
        brightness.set_editor_property('slider_min', 0.)
        brightness.set_editor_property('slider_max', 2.)
        brightness.set_editor_property('group', 'Stage3 Armor Steel')
        final = ml.create_material_expression(parent, u.MaterialExpressionMultiply, 400, -350)
        assert ml.connect_material_expressions(output, '', final, 'A')
        assert ml.connect_material_expressions(brightness, '', final, 'B')
        assert ml.connect_material_property(final, '', u.MaterialProperty.MP_BASE_COLOR)
        ml.recompile_material(parent)
    assert source_signature == _outputs(parent), 'Original Normal/ORM or another output changed'
    ea.set_metadata_tag(parent, 'Stage3GothicCharacterSource', source.get_path_name())
    ea.set_metadata_tag(parent, 'Stage3GothicCharacterTextureSHA256', calibration_row['sha256'])
    assert ea.save_loaded_asset(parent)

    instance = owned(instance_path)
    if not instance:
        instance = u.AssetToolsHelpers.get_asset_tools().create_asset(
            instance_path.rsplit('/', 1)[-1], DEST,
            u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
        assert instance
        ea.set_metadata_tag(instance, 'Stage3GothicCharacterOwner', OWNER)
    ml.set_material_instance_parent(instance, parent)
    ml.set_material_instance_vector_parameter_value(instance, 'ColorTint', u.LinearColor(*tint, 1.))
    ml.set_material_instance_scalar_parameter_value(instance, 'Brightness', 1.)
    ml.update_material_instance(instance)
    actual = ml.get_material_instance_vector_parameter_value(instance, 'ColorTint')
    assert max(abs(a - b) for a, b in zip((actual.r, actual.g, actual.b), tint)) < 1.e-6
    assert abs(ml.get_material_instance_scalar_parameter_value(instance, 'Brightness') - 1.) < 1.e-6
    assert ea.save_loaded_asset(instance)

    report = {'success': False, 'target_srgb': list(TARGET_SRGB), 'target_linear': tint, 'brightness': 1.,
              'source_mean_srgb': calibration_row['source_mean_srgb'],
              'source_mean_linear': calibration_row['source_mean_linear'],
              'source_normalization': normalization, 'source_texture_sha256': calibration_row['sha256'],
              'parent': parent.get_path_name(), 'instance': instance.get_path_name(),
              'preserved_outputs': source_signature, 'assignments': [], 'map_saved': False,
              'visual_qa': 'pending new room lights and actual player-camera enemy contrast'}
    try:
        for actor, comp, mesh, previous in bindings:
            comp.set_material(0, instance)
            assert comp.get_skinned_asset() == mesh
            assert all(comp.get_material(index) == previous[index] for index in (1, 2, 3))
            report['assignments'].append({'actor': actor.get_actor_label(), 'slot': 0,
                'before': previous[0].get_path_name(), 'after': instance.get_path_name()})
        assert source_signature == _outputs(source), 'Source material output drift'
    except Exception:
        for actor, comp, mesh, previous in bindings:
            comp.set_material(0, previous[0])
        raise
    report['success'] = True
    return report
