"""Read-only, cold-loaded Stage3 interaction opacity and preservation audit.

Root loads saved Stage3 outside PIE then calls main(). Does not load a level,
modify actors/assets/MPCs, compile shaders, or save any Unreal package.
Only Saved/Stage3GothicRevision20261125/QA/interactive_visibility.json is written.
"""
import json
import math
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
RUN = ROOT / 'Saved/Stage3GothicRevision20261125'
DEST = '/Game/Environment/Stage3/GothicRevision_20261125/InteractiveReadability/'
OWNER = 'Stage3AlwaysVisibleInteractions20261125'
PREFIXES = ('S3_Release', 'S3_GothicConnections_', 'S3_GothicVisual_Dock',
            'S3_GothicVisual_Weight', 'S3_GothicVisual_FloorFrame',
            'S3_GothicVisual_PressureDeck', 'S3_GothicVisual_Lock',
            'S3_D0', 'S3_D1_', 'S3_D2_', 'S3_FinalGate_Leaf')
OUTPUTS = ('BASE_COLOR', 'NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS', 'METALLIC',
           'SPECULAR', 'EMISSIVE_COLOR', 'WORLD_POSITION_OFFSET')
ML = u.MaterialEditingLibrary
EA = u.EditorAssetLibrary


def path(obj):
    return obj.get_path_name() if obj else None


def encode(value):
    if isinstance(value, u.Object):
        return path(value)
    if isinstance(value, u.LinearColor):
        return [value.r, value.g, value.b, value.a]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def equal(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and math.isfinite(b) and abs(a-b) < 1.e-6
    return a == b


def node_signature(material, node):
    inputs = list(ML.get_inputs_for_material_expression(material, node))
    result = {'class': path(node.get_class()),
              'inputs': [item.get_name() if item else None for item in inputs]}
    # Fixed textures, UV channels/tiling, constants, switches and custom code
    # must survive; root names alone would miss a changed texture or multiplier.
    for name in ('texture', 'material_function', 'parameter_name', 'sampler_type',
                 'const_coordinate', 'coordinate_index', 'u_tiling', 'v_tiling',
                 'un_mirror_u', 'un_mirror_v', 'const_a', 'const_b', 'constant',
                 'default_value', 'r', 'g', 'b', 'a', 'code', 'output_type'):
        try:
            result[name] = encode(node.get_editor_property(name))
        except Exception:
            pass  # Not all expression classes expose each field.
    return result


def parameter_values(material):
    is_instance = isinstance(material, u.MaterialInstanceConstant)
    result = {}
    for kind in ('scalar', 'vector', 'texture', 'static_switch'):
        names = getattr(ML, 'get_' + kind + '_parameter_names')(material)
        prefix = 'get_material_instance_' if is_instance else 'get_material_default_'
        getter = getattr(ML, prefix + kind + '_parameter_value')
        result[kind] = {str(name): encode(getter(material, name)) for name in names}
    return result


def main():
    result = {'success': False, 'checks': [], 'materials': [], 'bindings': [],
              'packages_saved': False, 'gpu_tested': False,
              'scope': 'Saved opaque shader graph is independent of camera MPC and interaction state; actor visibility and runtime material reassignment require separate PIE tests.'}
    def check(name, passed, detail=None):
        result['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
    try:
        editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        assert not editor.get_game_world(), 'Run outside PIE in root-owned cold-load process'
        world = editor.get_editor_world()
        assert path(world) == '/Game/Maps/Stage3.Stage3', path(world)
        application = json.loads((RUN / 'interactive_visibility.json').read_text(encoding='utf8'))
        assert application['success']
        expected = {(row['actor'], row['slot']): row for row in application['assignments']}
        assert len(expected) == len(application['assignments']), 'Duplicate assignment keys'
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        initial_actor_set = {path(actor) for actor in actors}
        labels = set()
        actual_keys = set()
        materials = {}
        for actor in actors:
            label = actor.get_actor_label()
            if not label.startswith(PREFIXES):
                continue
            component = actor.get_component_by_class(u.StaticMeshComponent)
            if not component or not component.get_editor_property('visible') or component.get_editor_property('hidden_in_game'):
                continue
            labels.add(label)
            for slot in range(component.get_num_materials()):
                material = component.get_material(slot)
                key = (label, slot)
                actual_keys.add(key)
                check('Interactive slot uses owned opaque MI: %s[%d]' % key,
                      isinstance(material, u.MaterialInstanceConstant) and path(material).startswith(DEST), path(material))
                if not material:
                    continue
                check('Saved slot matches writer report: %s[%d]' % key,
                      key in expected and expected[key]['assigned'] == path(material))
                materials[path(material)] = material
                result['bindings'].append({'actor': label, 'slot': slot, 'material': path(material)})
        required = {'S3_Release%d_%s' % (number, part) for number in (1, 2, 3) for part in ('Housing', 'Ring', 'Pin')}
        check('All three Housing/Ring/Pin groups present and visible', required <= labels, sorted(required-labels))
        check('Both dock groups and connection visuals covered',
              all(any(label.startswith(prefix) for label in labels) for prefix in ('S3_GothicVisual_Dock1_', 'S3_GothicVisual_Dock2_', 'S3_GothicConnections_')))
        check('Actual visible slots exactly match assignment inventory', actual_keys == set(expected),
              {'missing': sorted(set(expected)-actual_keys), 'unexpected': sorted(actual_keys-set(expected))})
        for material_path, mi in sorted(materials.items()):
            if not isinstance(mi, u.MaterialInstanceConstant) or not material_path.startswith(DEST):
                continue
            source_path = EA.get_metadata_tag(mi, 'Stage3InteractiveSource')
            source = u.load_asset(source_path) if source_path else None
            check('Owned source metadata: '+material_path, EA.get_metadata_tag(mi, 'Stage3InteractiveOwner') == OWNER and bool(source), source_path)
            if not source:
                continue
            parent = mi.get_base_material()
            base = source.get_base_material() if isinstance(source, u.MaterialInstanceConstant) else source
            check('Parent is owned and opaque: '+material_path,
                  path(parent).startswith(DEST) and EA.get_metadata_tag(parent, 'Stage3InteractiveOwner') == OWNER and parent.get_editor_property('blend_mode') == u.BlendMode.BLEND_OPAQUE)
            # A direct parent excludes an intermediate MI reintroducing masking.
            check('Direct MI parent is audited base material: '+material_path, mi.get_editor_property('parent') == parent)
            overrides = mi.get_editor_property('base_property_overrides')
            flags = {name: bool(overrides.get_editor_property(name)) for name in
                     ('override_blend_mode', 'override_opacity_mask_clip_value', 'override_dithered_lod_transition')}
            check('Opacity-related MI base overrides disabled: '+material_path, not any(flags.values()), flags)
            check('Parent LOD dithering disabled: '+material_path, not parent.get_editor_property('dithered_lod_transition'))
            opacity = {}
            for name in ('OPACITY', 'OPACITY_MASK'):
                node = ML.get_material_property_input_node(parent, getattr(u.MaterialProperty, 'MP_'+name))
                constant = isinstance(node, u.MaterialExpressionConstant)
                value = node.get_editor_property('r') if constant else None
                links = list(ML.get_inputs_for_material_expression(parent, node)) if node else []
                passed = constant and equal(value, 1.) and not any(links)
                opacity[name] = {'node': node.get_name() if node else None, 'value': value,
                                 'reachable_inputs': [path(item) for item in links if item]}
                check('State-independent constant-one '+name+': '+material_path, passed, opacity[name])
            errors = []
            for name in OUTPUTS:
                prop = getattr(u.MaterialProperty, 'MP_'+name)
                a = ML.get_material_property_input_node(base, prop)
                b = ML.get_material_property_input_node(parent, prop)
                left = [a.get_name() if a else None, ML.get_material_property_input_node_output_name(base, prop) if a else None]
                right = [b.get_name() if b else None, ML.get_material_property_input_node_output_name(parent, prop) if b else None]
                if left != right:
                    errors.append({'output': name, 'source': left, 'actual': right})
            check('BaseColor Normal ORM and other non-opacity roots preserved: '+material_path, not errors, errors)
            nodes = {node.get_name(): node for node in ML.get_material_expressions(parent)}
            node_errors = []
            for node in ML.get_material_expressions(base):
                copied = nodes.get(node.get_name())
                if not copied or node_signature(base, node) != node_signature(parent, copied):
                    node_errors.append(node.get_name())
            check('Original graph nodes textures UV parameters and links preserved: '+material_path, not node_errors, node_errors)
            original_parameters = parameter_values(source)
            actual_parameters = parameter_values(mi)
            differences = []
            for kind, values in original_parameters.items():
                for name, value in values.items():
                    if name not in actual_parameters[kind] or not equal(value, actual_parameters[kind][name]):
                        differences.append([kind, name, value, actual_parameters[kind].get(name)])
                if set(values) != set(actual_parameters[kind]):
                    differences.append([kind, 'parameter-name set changed'])
            check('All effective texture scalar vector and switch values inherited: '+material_path, not differences, differences)
            result['materials'].append({'material': material_path, 'source': source_path,
                'parent': path(parent), 'opacity': opacity, 'base_overrides': flags,
                'effective_parameters': actual_parameters,
                'disconnected_old_mpc_nodes_allowed': True})
        check('Original actor set unchanged by QA', initial_actor_set == {path(actor) for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()})
        result['material_count'] = len(result['materials'])
        result['assignment_count'] = len(result['bindings'])
        result['success'] = bool(result['materials']) and all(row['passed'] for row in result['checks'])
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        output = RUN / 'QA/interactive_visibility.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf8')
    return result


if __name__ == '__main__':
    main()
