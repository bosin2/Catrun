"""Read-only saved Stage3 graph/slot inventory; run in a separate UE commandlet."""
import json
from pathlib import Path
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/Stage3MaterialCorrection20261125/Materials'
OUT.mkdir(parents=True, exist_ok=True)
EA = u.EditorAssetLibrary
ML = u.MaterialEditingLibrary
report = {'materials': {}, 'textures': {}, 'meshes': {}, 'actors': []}


def path(obj):
    return obj.get_path_name() if obj else None


def material(obj):
    key = path(obj)
    if key in report['materials']:
        return
    base = obj.get_base_material()
    nodes = list(ML.get_material_expressions(base))
    item = {'base': path(base), 'class': obj.get_class().get_name(),
            'blend_mode': str(base.get_editor_property('blend_mode')),
            'two_sided': base.get_editor_property('two_sided'), 'nodes': [], 'properties': {}}
    for prop in ['BASE_COLOR', 'NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS', 'METALLIC', 'OPACITY_MASK', 'EMISSIVE_COLOR']:
        enum = getattr(u.MaterialProperty, 'MP_' + prop)
        n = ML.get_material_property_input_node(base, enum)
        item['properties'][prop] = {'node': n.get_name() if n else None,
            'output': ML.get_material_property_input_node_output_name(base, enum) if n else None}
    for n in nodes:
        row = {'name': n.get_name(), 'class': n.get_class().get_name(),
               'inputs': [x.get_name() if x else None for x in ML.get_inputs_for_material_expression(base, n)]}
        for attr in ['texture', 'material_function', 'parameter_name', 'code', 'default_value', 'const_a', 'const_b', 'sampler_type', 'coordinates', 'const_coordinate']:
            try:
                val = n.get_editor_property(attr)
                row[attr] = path(val) if isinstance(val, u.Object) else str(val)
            except Exception:
                pass
        tex = getattr(n, 'texture', None)
        if tex and path(tex) not in report['textures']:
            data = tex.get_editor_property('asset_import_data')
            report['textures'][path(tex)] = {'source_files': list(data.extract_filenames()),
                'srgb': tex.get_editor_property('srgb'),
                'compression': str(tex.get_editor_property('compression_settings'))}
        item['nodes'].append(row)
    report['materials'][key] = item


im = json.loads((ROOT / 'Saved/Stage3Integration20261125/import_report.json').read_text())
for key, value in im['materials'].items():
    material(EA.load_asset(value))
for key, value in im['meshes'].items():
    mesh = EA.load_asset(value['path'])
    report['meshes'][path(mesh)] = [{'slot': str(s.material_slot_name), 'material': path(s.material_interface)} for s in mesh.static_materials]
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/Stage3')
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    for c in a.get_components_by_class(u.MeshComponent):
        skeletal = isinstance(c, u.SkeletalMeshComponent)
        if not isinstance(c, u.StaticMeshComponent) and not skeletal:
            continue
        mesh = c.get_skinned_asset() if skeletal else c.static_mesh
        if not mesh or ('/Stage3/' not in path(mesh) and not (skeletal and isinstance(a, u.CatrunArmor))):
            continue
        row = {'actor': a.get_actor_label(), 'actor_path': path(a), 'component': c.get_name(),
               'folder': str(a.get_folder_path()), 'mesh': path(mesh), 'skeletal': skeletal, 'slots': []}
        mesh_slots = mesh.get_editor_property('materials') if skeletal else mesh.static_materials
        for i in range(c.get_num_materials()):
            m = c.get_material(i)
            material(m)
            row['slots'].append({'index': i, 'name': str(mesh_slots[i].material_slot_name), 'material': path(m)})
        report['actors'].append(row)
(OUT / 'source_probe.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print('STAGE3_MATERIAL_PROBE_OK', len(report['materials']), len(report['actors']))
