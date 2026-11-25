"""Independent, read-only Stage3 material correction evidence.

UE: import this module, then snapshot('before') / snapshot('after').
The active editor world must already be Stage3. No loading, saving, selection,
actor spawning or mutation occurs. Exports and reports only go to Saved/.
CPython: python verify.py compare | self-test
"""
import argparse
import difflib
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3MaterialCorrection20261125/QA'
TARGETS = {'Wall': [101, 97, 95], 'Pillar': [119, 115, 109],
           'Floor': [150, 146, 139], 'Floor diamond': [112, 108, 102],
           'Gate hall decorative stone': [81, 77, 75], 'Black iron': [52, 50, 54],
           'Brass': [150, 134, 107], 'Banner': [101, 49, 62],
           'Wood': [89, 72, 61], 'Carpet': [73, 67, 74]}


def sha256(file):
    digest = hashlib.sha256()
    with Path(file).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


def srgb_to_linear(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def linear_to_srgb(v):
    return 255.0 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)


def snapshot(label):
    """Capture current editor Stage3 without modifying the editor or assets."""
    import unreal as u
    assert label in ('before', 'after')
    destination = OUT / label
    if (destination / 'snapshot.json').exists():
        raise RuntimeError('Evidence already exists; refusing to overwrite ' + str(destination))
    destination.mkdir(parents=True, exist_ok=True)
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith('/Game/Maps/Stage3.'), world.get_path_name()
    task = u.AssetExportTask()
    task.object = world
    task.exporter = u.LevelExporterT3D()
    task.filename = str(destination / 'world.t3d')
    task.automated = True
    task.prompt = False
    task.selected = False
    task.replace_identical = False
    assert u.Exporter.run_asset_export_task(task), 'Full world T3D export failed'
    def path(obj):
        return obj.get_path_name() if obj else None
    def vec(v):
        return [v.x, v.y, v.z]
    def rot(v):
        return [v.pitch, v.yaw, v.roll]
    actors = {}
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        item = {'label': a.get_actor_label(), 'class': path(a.get_class()),
                'location': vec(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation()),
                'scale': vec(a.get_actor_scale3d()), 'components': {}}
        for c in a.get_components_by_class(u.ActorComponent):
            row = {'class': path(c.get_class())}
            if isinstance(c, u.SceneComponent):
                row.update(location=vec(c.get_world_location()), rotation=rot(c.get_world_rotation()),
                           scale=vec(c.get_world_scale()), parent=path(c.get_attach_parent()))
            if isinstance(c, u.PrimitiveComponent):
                row.update(collision_profile=str(c.get_collision_profile_name()),
                           collision_enabled=str(c.get_collision_enabled()),
                           collision_object_type=str(c.get_collision_object_type()))
            if isinstance(c, u.StaticMeshComponent):
                row.update(mesh=path(c.static_mesh),
                           materials=[path(c.get_material(i)) for i in range(c.get_num_materials())])
            item['components'][c.get_name()] = row
        actors[a.get_name()] = item
    protected = {}
    for folder in ('Content/Environment/Stage1', 'Content/Environment/Stage2',
                   'Content/Environment/Shared', 'Content/Environment/Stage3/FinalGuard',
                   'Source', 'Config'):
        for file in sorted((ROOT / folder).rglob('*')):
            if file.is_file():
                protected[file.relative_to(ROOT).as_posix()] = sha256(file)
    # Shared originals outside these folders are captured via complete material
    # and texture registry, including files not referenced by the Stage3 map.
    registry = u.AssetRegistryHelpers.get_asset_registry()
    for cls in ('Material', 'MaterialInstanceConstant', 'Texture2D'):
        assets = registry.get_assets_by_class(u.TopLevelAssetPath('/Script/Engine', cls), True)
        for asset in assets:
            package = str(asset.package_name)
            if package.startswith('/Game/') and not package.startswith('/Game/Environment/Stage3/ColorCorrection_20261125/'):
                file = ROOT / ('Content/' + package[6:] + '.uasset')
                rel = file.relative_to(ROOT).as_posix()
                if file.exists() and rel not in protected:
                    protected[rel] = sha256(file)
    result = {'world': path(world), 'actors': actors, 'protected_sha256': protected,
              'world_t3d_sha256': sha256(destination / 'world.t3d')}
    dump(destination / 'snapshot.json', result)
    print('STAGE3_READ_ONLY_SNAPSHOT_OK', label, len(actors), len(protected))
    return result


def compare():
    before = json.loads((OUT / 'before/snapshot.json').read_text(encoding='utf8'))
    after = json.loads((OUT / 'after/snapshot.json').read_text(encoding='utf8'))
    checks = []
    def check(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    check('Actor identities unchanged', before['actors'].keys() == after['actors'].keys())
    differences, material_changes = [], []
    for name in sorted(before['actors'].keys() & after['actors'].keys()):
        b = json.loads(json.dumps(before['actors'][name]))
        a = json.loads(json.dumps(after['actors'][name]))
        for component in b['components'].keys() & a['components'].keys():
            bm = b['components'][component].pop('materials', None)
            am = a['components'][component].pop('materials', None)
            if bm != am:
                material_changes.append({'actor': name, 'component': component, 'before': bm, 'after': am})
        if a != b:
            differences.append({'actor': name, 'before': b, 'after': a})
    check('Actor transforms, meshes, component layout and collision unchanged', not differences, differences)
    protected_changes = [p for p, h in before['protected_sha256'].items() if after['protected_sha256'].get(p) != h]
    source_changes = [p for p in protected_changes if p.startswith('Source/')]
    asset_changes = [p for p in protected_changes if not p.startswith('Source/')]
    check('Protected Stage1 Stage2 shared originals, config and FinalGuard files unchanged', not asset_changes, asset_changes)
    check('Source tree unchanged since snapshot (concurrent chat changes reported separately)', not source_changes, source_changes)
    dedicated = '/Game/Environment/Stage3/ColorCorrection_20261125/'
    bad = [r for r in material_changes if len(r['before'] or []) != len(r['after'] or []) or
           any(b != a and (not a or not a.startswith(dedicated)) for b, a in zip(r['before'] or [], r['after'] or []))]
    check('All changed material slots use isolated correction assets', not bad, bad)
    # Retain full text diff. Exact gameplay-property classification happens after
    # concrete lighting changes are known, never by ignoring whole actor blocks.
    btext = (OUT / 'before/world.t3d').read_text(encoding='utf-8-sig').splitlines()
    atext = (OUT / 'after/world.t3d').read_text(encoding='utf-8-sig').splitlines()
    diff = '\n'.join(difflib.unified_diff(btext, atext, fromfile='before', tofile='after', n=3))
    (OUT / 'world.diff').write_text(diff, encoding='utf8')
    application = json.loads((OUT.parent / 'Materials/application_report.json').read_text(encoding='utf8'))
    approved_slots = {(r['actor_path'].rsplit('.',1)[-1], r['component'], r['slot'])
                      for r in application['assignments'] + application['preserved_slots']}
    nb, na = normalize_t3d(btext, before['actors'], approved_slots), normalize_t3d(atext, before['actors'], approved_slots)
    semantic_diff = '\n'.join(difflib.unified_diff(nb, na, fromfile='before gameplay', tofile='after gameplay', n=3))
    (OUT / 'gameplay.diff').write_text(semantic_diff, encoding='utf8')
    check('Full exported world identical except material overrides and explicit lighting exposure fields', not semantic_diff)
    result = {'checks': checks, 'material_changes': material_changes,
              'structural_checks_passed': all(c['passed'] for c in checks),
              'gameplay_text_diff_review_required': bool(diff),
              'scope': 'T3D review and material render readback remain separate required evidence.'}
    dump(OUT / 'comparison.json', result)
    return result


def normalize_t3d(lines, actors, approved_slots=()):
    """Remove only explicitly authorized property names, retaining all else."""
    result, actor, objects = [], None, []
    light_labels = {'S3_KeyLight','S3_FillLight','S3_AmbientSkyLight'} | {'S3_LocalLight'+str(i) for i in range(9)}
    exposure_fields = {'bOverride_AutoExposureMethod','AutoExposureMethod',
                       'bOverride_AutoExposureApplyPhysicalCameraExposure','AutoExposureApplyPhysicalCameraExposure',
                       'bOverride_AutoExposureBias','AutoExposureBias'}
    def struct_fields(value):
        # Unreal structs may contain commas in nested structs/quoted strings.
        text = value[1:-1]
        fields, start, depth, quoted, escaped = [], 0, 0, False, False
        for i,ch in enumerate(text):
            if escaped:
                escaped=False
                continue
            if ch=='\\' and quoted:
                escaped=True
            elif ch=='"':
                quoted=not quoted
            elif not quoted:
                if ch=='(':
                    depth+=1
                elif ch==')':
                    depth-=1
                elif ch==',' and depth==0:
                    fields.append(text[start:i]);start=i+1
        fields.append(text[start:])
        return fields
    for line in lines:
        stripped=line.strip()
        if stripped.startswith('Begin Actor '):
            actor=re.search(r'\bName=([^ ]+)',stripped).group(1)
            objects=[]
        if stripped.startswith('Begin Object '):
            objects.append(re.search(r'\bName="?([^" ]+)',stripped).group(1))
        elif stripped=='End Object':
            objects.pop()
        label=actors.get(actor,{}).get('label')
        material_match = re.match(r'OverrideMaterials\((\d+)\)=',stripped)
        if material_match and objects and (actor,objects[-1],int(material_match.group(1))) in approved_slots:
            continue
        if label in light_labels and stripped.startswith('Intensity='):
            continue
        if label=='S3_AmbientSkyLight' and stripped.startswith('Cubemap='):
            continue
        if label=='S3_Exposure' and stripped.startswith('Settings=('):
            fields=struct_fields(stripped.split('=',1)[1])
            stripped='Settings=('+','.join(f for f in fields if f.split('=',1)[0] not in exposure_fields)+')'
        result.append(stripped)
    return result


def self_test():
    assert srgb_to_linear(0) == 0 and srgb_to_linear(255) == 1
    assert abs(srgb_to_linear(128) - 0.21586050011389926) < 1e-12
    assert max(abs(linear_to_srgb(srgb_to_linear(v)) - v) for v in range(256)) < 1e-10
    # Demonstrate why normalized byte tint cannot satisfy these final targets.
    incorrect_errors = []
    for values in TARGETS.values():
        for value in values:
            target = srgb_to_linear(value)
            mean_source = 0.4
            multiplier = target / mean_source
            assert abs(linear_to_srgb(mean_source * multiplier) - value) < 1e-10
            incorrect_errors.append(abs(linear_to_srgb(mean_source * value / 255) - value))
    assert max(incorrect_errors) > 20
    return {'passed': True, 'targets': TARGETS, 'roundtrip_bytes': 256,
            'reference_midgray_linear': srgb_to_linear(128)}


def calibration():
    """Recompute from PNG histograms, independently of production statistics."""
    import numpy as np
    from PIL import Image
    directory = OUT.parent / 'Materials'
    manifest = json.loads((directory / 'calibration.json').read_text(encoding='utf8'))
    probe = json.loads((directory / 'source_probe.json').read_text(encoding='utf8'))
    checks, results, computed = [], {}, {}
    def check(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    aliases = {'FloorDiamond': 'Floor diamond', 'GateDecorStone': 'Gate hall decorative stone',
               'BlackIron': 'Black iron'}
    check('All ten exact user target RGBs', {aliases.get(k, k): v for k, v in manifest['targets_srgb'].items()} == TARGETS)
    lut = np.array([srgb_to_linear(i) for i in range(256)], dtype=np.float64)
    for path, row in manifest['textures'].items():
        image = np.asarray(Image.open(row['source']).convert('RGB'))
        means, deviations, histograms = [], [], []
        for channel in range(3):
            counts = np.bincount(image[:, :, channel].ravel(), minlength=256)
            mean = float(counts.dot(lut) / counts.sum())
            variance = float(counts.dot((lut - mean) ** 2) / counts.sum())
            means.append(mean)
            deviations.append(math.sqrt(variance))
            histograms.append(counts)
        computed[path] = {'mean': means, 'std': deviations, 'histograms': histograms}
        check('PNG source unchanged: ' + path, sha256(row['source']) == row['sha256'])
        check('Histogram mean agrees: ' + path, max(abs(a-b) for a, b in zip(means, row['source_mean_linear'])) < 1e-8)
        check('Source texture uses sRGB sampler: ' + path, probe['textures'][path]['srgb'] is True)
    for name, row in manifest['calibrations'].items():
        source = computed[row['source_texture']]
        target = TARGETS[aliases.get(row['role'], row['role'])]
        tint = row['color_tint']
        normalization = row['source_normalization']
        actual = [linear_to_srgb(s * n * t * row['brightness']) for s,n,t in zip(source['mean'], normalization, tint)]
        checks_for_role = max(abs(a-b) for a,b in zip(actual, target)) < 0.001
        check('Final representative RGB: ' + name, checks_for_role, {'measured': actual, 'target': target})
        check('ColorTint stores decoded final target: ' + name, max(abs(a-srgb_to_linear(b)) for a,b in zip(tint,target)) < 1e-10)
        check('Texture detail survives: ' + name, all(s*n*t*row['brightness'] > 0 for s,n,t in zip(source['std'], normalization, tint)))
        clipped = [float(counts[(lut*n*t*row['brightness']) > 1].sum() / counts.sum())
                   for counts,n,t in zip(source['histograms'],normalization,tint)]
        check('No independently measured albedo clipping: ' + name, max(clipped) == 0, clipped)
        results[name] = {'role': row['role'], 'target_srgb': target, 'independent_result_srgb': actual,
                         'independent_source_mean_linear': source['mean'], 'independent_source_std_linear': source['std']}
    def slot(r):
        return (r['actor_path'], r['component'], r.get('slot', r.get('index')))
    expected = {(r['actor_path'], r['component'], s['index']) for r in probe['actors'] for s in r['slots']}
    assigned = [slot(r) for r in manifest['assignments']]
    preserved = [slot(r) for r in manifest['preserved']]
    check('Every probed component slot accounted exactly once', set(assigned + preserved) == expected and len(assigned + preserved) == len(expected),
          {'expected': len(expected), 'assigned': len(assigned), 'preserved': len(preserved),
           'missing': sorted(expected-set(assigned+preserved)), 'unexpected': sorted(set(assigned+preserved)-expected)})
    check('All target roles occur in assignments', set(manifest['targets_srgb']) == {r['role'] for r in manifest['assignments']})
    result = {'success': all(c['passed'] for c in checks), 'checks': checks, 'results': results,
              'metric': 'Independent full mip0 source PNG per-channel 256-bin histogram, IEC sRGB decode then equal-texel linear mean',
              'limitations': 'Source-pixel proof only. GPU BC compression, imported texture size, mip sampling and compiled graph require readback.'}
    dump(OUT / 'calibration_independent.json', result)
    return result


def loaded_materials():
    """Read saved/loaded shader graphs and slot bindings independently in UE."""
    import unreal as u
    directory = OUT.parent / 'Materials'
    application = json.loads((directory / 'application_report.json').read_text(encoding='utf8'))
    calibration_data = json.loads((directory / 'calibration.json').read_text(encoding='utf8'))
    checks = []
    ml = u.MaterialEditingLibrary
    def check(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    def path(obj):
        return obj.get_path_name() if obj else None
    def rgb(value):
        return [value.r, value.g, value.b]
    def near(a, b, tol=1e-5):
        return len(a) == len(b) and max(abs(x-y) for x,y in zip(a,b)) <= tol
    def inputs(material, node):
        return list(ml.get_inputs_for_material_expression(material, node))
    preserved_properties = ('NORMAL', 'AMBIENT_OCCLUSION', 'ROUGHNESS', 'METALLIC',
                            'SPECULAR', 'OPACITY', 'OPACITY_MASK', 'EMISSIVE_COLOR', 'WORLD_POSITION_OFFSET')
    for parent_path, info in application['parents'].items():
        parent, source = u.load_asset(parent_path), u.load_asset(info['source'])
        assert parent and source
        original = {n.get_name(): n for n in ml.get_material_expressions(source)}
        duplicate = {n.get_name(): n for n in ml.get_material_expressions(parent)}
        node_errors = []
        for name, node in original.items():
            other = duplicate.get(name)
            if not other or node.get_class() != other.get_class():
                node_errors.append([name, 'missing or different class'])
                continue
            if [n.get_name() if n else None for n in inputs(source,node)] != [n.get_name() if n else None for n in inputs(parent,other)]:
                node_errors.append([name, 'input links changed'])
            for prop in ('texture', 'coordinates', 'const_coordinate', 'sampler_type', 'material_function',
                         'parameter_name', 'code', 'const_a', 'const_b', 'r', 'g', 'b', 'a'):
                try:
                    a, b = node.get_editor_property(prop), other.get_editor_property(prop)
                except Exception:
                    continue
                if isinstance(a, u.Object):
                    a,b = path(a),path(b)
                else:
                    a,b = str(a),str(b)
                if a != b:
                    node_errors.append([name,prop,a,b])
        check('Original graph texture UV sampling and links intact: '+parent.get_name(), not node_errors, node_errors)
        outputs = []
        for prop in preserved_properties:
            enum = getattr(u.MaterialProperty, 'MP_'+prop)
            an, bn = ml.get_material_property_input_node(source,enum), ml.get_material_property_input_node(parent,enum)
            ao = ml.get_material_property_input_node_output_name(source,enum) if an else None
            bo = ml.get_material_property_input_node_output_name(parent,enum) if bn else None
            if (an.get_name() if an else None,ao) != (bn.get_name() if bn else None,bo):
                outputs.append(prop)
        check('All non-BaseColor outputs unchanged: '+parent.get_name(), not outputs, outputs)
    for instance_path, info in application['instances'].items():
        instance = u.load_asset(instance_path)
        cal = calibration_data['calibrations'][info['calibration']]
        parent = instance.get_base_material()
        tint = ml.get_material_instance_vector_parameter_value(instance,'ColorTint')
        brightness = ml.get_material_instance_scalar_parameter_value(instance,'Brightness')
        check('Live MI parameters: '+instance.get_name(), near(rgb(tint),cal['target_linear']) and abs(brightness-1.0)<1e-7)
        # Trace the actual BaseColor graph backwards; do not accept report values.
        try:
            final = ml.get_material_property_input_node(parent,u.MaterialProperty.MP_BASE_COLOR)
            assert isinstance(final,u.MaterialExpressionMultiply)
            tinted,scalar = inputs(parent,final)[:2]
            assert isinstance(scalar,u.MaterialExpressionScalarParameter) and str(scalar.get_editor_property('parameter_name'))=='Brightness'
            normalized,vector = inputs(parent,tinted)[:2]
            assert isinstance(tinted,u.MaterialExpressionMultiply)
            assert isinstance(vector,u.MaterialExpressionVectorParameter) and str(vector.get_editor_property('parameter_name'))=='ColorTint'
            texture,norm = inputs(parent,normalized)[:2]
            assert isinstance(normalized,u.MaterialExpressionMultiply)
            assert isinstance(texture,u.MaterialExpressionTextureSample)
            assert path(texture.texture)==cal['source_texture']
            assert texture.texture.get_editor_property('srgb')
            assert isinstance(norm,u.MaterialExpressionConstant3Vector)
            assert near(rgb(norm.get_editor_property('constant')),cal['source_normalization'],1e-4)
            check('Live BaseColor equation: '+instance.get_name(),True)
        except Exception as error:
            check('Live BaseColor equation: '+instance.get_name(),False,str(error))
    actors = {a.get_path_name(): a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
    mismatches = []
    for row in application['assignments'] + application['preserved_slots']:
        actor = actors[row['actor_path']]
        components = {c.get_name(): c for c in actor.get_components_by_class(u.MeshComponent)}
        actual = path(components[row['component']].get_material(row['slot']))
        wanted = row.get('assigned_material',row['source_material'])
        if actual != wanted:
            mismatches.append([row['actor'],row['component'],row['slot'],wanted,actual])
    check('All 1095 actual component slots match assigned or preserved material',not mismatches,mismatches)
    result = {'success': all(c['passed'] for c in checks),'checks':checks}
    dump(OUT / 'loaded_materials.json',result)
    print('STAGE3_LOADED_MATERIAL_QA',result['success'],len(checks))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('compare', 'self-test', 'calibration'))
    args = parser.parse_args()
    result = {'compare': compare, 'self-test': self_test, 'calibration': calibration}[args.mode]()
    if args.mode == 'self-test':
        dump(OUT / 'color_math_self_test.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
