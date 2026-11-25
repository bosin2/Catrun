"""Inert root preparation: duplicate finished Stage2 dust; assign 16 card slots.

Never launches PIE or saves any package. Root owns backup and final map save.
Existing Stage2/Stage3 materials, presenter BPs, placement and native logic stay
unchanged; this module only creates a new material and sets 16 material slots.
"""
import hashlib
from pathlib import Path
import unreal as u

SOURCE = '/Game/Environment/Stage2/GameplayPolish_20261125/Presentation/Build_03/M_GateFloorDust'
SOURCE_SHA = '0702ec0428c5f701e30871d19c5856a07b567860cd3e816e629218e52eb432ac'
TARGET = '/Game/Environment/Stage3/GateFX_20261125/Stage2DustMatch01/M_Stage3GateDust'
LABELS = ('S3_GateImpact_D1', 'S3_GateImpact_D2')


def package_file(package):
    return Path(u.Paths.project_dir()).resolve() / 'Content' / (package.split('.')[0].removeprefix('/Game/') + '.uasset')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def graph_signature(material):
    """Compare real expression topology, shader bodies and relevant constants."""
    ml = u.MaterialEditingLibrary
    nodes = list(ml.get_material_expressions(material))
    result = {'settings': {key: str(material.get_editor_property(key)) for key in
              ('blend_mode', 'material_domain', 'shading_model', 'two_sided', 'disable_depth_test')},
              'nodes': {}, 'outputs': {}}
    for node in nodes:
        item = {'class': node.get_class().get_path_name(),
                'input_names': list(ml.get_material_expression_input_names(node)),
                'input_nodes': [p.get_name() if p else None for p in ml.get_inputs_for_material_expression(material, node)]}
        if isinstance(node, u.MaterialExpressionCustom):
            item.update(code=node.get_editor_property('code'), output_type=str(node.get_editor_property('output_type')),
                        inputs=[{'name': str(p.get_editor_property('input_name')),
                                 'wire': p.export_text().replace(material.get_path_name(), '$M')}
                                for p in node.get_editor_property('inputs')])
        elif isinstance(node, u.MaterialExpressionConstant3Vector):
            color = node.get_editor_property('constant')
            item['rgba'] = [color.r, color.g, color.b, color.a]
        elif isinstance(node, u.MaterialExpressionScalarParameter):
            item.update(parameter_name=str(node.get_editor_property('parameter_name')),
                        default_value=node.get_editor_property('default_value'))
        elif isinstance(node, u.MaterialExpressionTime):
            item.update(ignore_pause=node.get_editor_property('ignore_pause'),
                        override_period=node.get_editor_property('override_period'), period=node.get_editor_property('period'))
        elif isinstance(node, u.MaterialExpressionTextureCoordinate):
            item.update({k: node.get_editor_property(k) for k in ('coordinate_index', 'u_tiling', 'v_tiling', 'un_mirror_u', 'un_mirror_v')})
        result['nodes'][node.get_name()] = item
    for name in ('MP_EMISSIVE_COLOR', 'MP_OPACITY', 'MP_WORLD_POSITION_OFFSET'):
        prop = getattr(u.MaterialProperty, name)
        node = ml.get_material_property_input_node(material, prop)
        result['outputs'][name] = {'node': node.get_name() if node else None,
                                   'output': ml.get_material_property_input_node_output_name(material, prop)}
    assert nodes and any('code' in node for node in result['nodes'].values()), 'Actual material graph is missing'
    return result


def card_state(actor, card):
    return {'actor_class': actor.get_class().get_path_name(),
            'actor_transform': actor.get_actor_transform().export_text(),
            'component_transform': card.get_world_transform().export_text(),
            'relative_location': card.get_editor_property('relative_location').export_text(),
            'relative_rotation': card.get_editor_property('relative_rotation').export_text(),
            'relative_scale': card.get_editor_property('relative_scale3d').export_text(),
            'mesh': card.get_editor_property('static_mesh').get_path_name(),
            'material_slots': card.get_num_materials(),
            'hidden': card.get_editor_property('hidden_in_game'),
            'visible': card.is_visible(), 'cast_shadow': card.get_editor_property('cast_shadow'),
            'collision': str(card.get_collision_enabled()),
            'overlaps': card.get_editor_property('generate_overlap_events')}


def prepare():
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Root isolated editor only; do not attach to user PIE'
    world = ed.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    source_path = package_file(SOURCE)
    assert sha(source_path) == SOURCE_SHA, 'Finished Stage2 material revision changed'
    ea = u.EditorAssetLibrary
    assert not ea.does_asset_exist(TARGET), 'Fresh Stage3 copy required; never overwrite an earlier package'
    source = ea.load_asset(SOURCE)
    assert isinstance(source, u.Material)
    graph_before = graph_signature(source)
    actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    cards = [(actors[label], actors[label].get_editor_property('Dust%02d' % i), i)
             for label in LABELS for i in range(8)]
    before = [card_state(actor, card) for actor, card, _ in cards]
    old_materials = [card.get_material(0) for _, card, _ in cards]
    assert all(state['material_slots'] == 1 for state in before), 'Unexpected additional card material slots'
    protected_paths = {source_path}
    root = Path(u.Paths.project_dir()).resolve()
    protected_paths.update(root / 'Content/Maps' / (name+'.umap') for name in ('Stage1', 'Stage2', 'Stage3'))
    protected_paths.update(package_file(m.get_path_name()) for m in old_materials)
    protected_paths.update((root / 'Content/Environment/Stage3/GateFX_20261125/Run04').glob('*.uasset'))
    hashes = {str(p): sha(p) for p in protected_paths}
    copied = ea.duplicate_asset(SOURCE, TARGET)
    assert isinstance(copied, u.Material), 'Material duplication failed'
    graph_after = graph_signature(copied)
    assert graph_before == graph_after, 'Duplicate graph/code/settings differ from finished Stage2 material'
    records = []
    for (actor, card, i), old, protected in zip(cards, old_materials, before):
        card.set_material(0, copied)
        after = card_state(actor, card)
        assert protected == after, ('Non-material card property changed', actor.get_actor_label(), i)
        assert card.get_material(0) == copied
        records.append({'actor': actor.get_actor_label(), 'card': i,
                        'old_material': old.get_path_name(), 'new_material': copied.get_path_name(),
                        'protected_before': protected, 'protected_after': after})
    assert len(records) == 16
    assert graph_signature(source) == graph_before, 'Stage2 original graph modified'
    assert all(sha(path) == digest for path, digest in hashes.items()), 'Protected package changed on disk'
    return {'success': True, 'records': records, 'source': SOURCE, 'source_sha256': SOURCE_SHA,
            'target': TARGET, 'source_graph': graph_before, 'duplicate_graph': graph_after,
            'graph_equal': True, 'nonmaterial_card_state_equal': True, 'protected_sha256': hashes,
            'asset_save_paths': [TARGET], 'map_save_path': '/Game/Maps/Stage3',
            'save_list': [TARGET, '/Game/Maps/Stage3'], 'packages_saved': False,
            'scope': 'Only new Stage3 material and sixteen D1/D2 material slots; no BP/native/camera/transform changes'}

