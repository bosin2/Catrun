"""Offline quantitative source-texture calibration. Requires Pillow and numpy.

Run after probe.py; never edits PNGs or Unreal packages. The reference statistic
is the per-channel arithmetic mean of IEC 61966-2-1 linear RGB over ALL mip-zero
source texels, equally weighted. It is deliberately not a lit-screen average.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'Saved/Stage3MaterialCorrection20261125/Materials'
TARGETS = {'Wall': [101,97,95], 'Pillar': [119,115,109], 'Floor': [150,146,139],
           'FloorDiamond': [112,108,102], 'GateDecorStone': [81,77,75],
           'BlackIron': [52,50,54], 'Brass': [150,134,107], 'Banner': [101,49,62],
           'Wood': [89,72,61], 'Carpet': [73,67,74]}


def decode(rgb):
    v = np.asarray(rgb, dtype=np.float64)
    return np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)


def encode(rgb):
    v = np.asarray(rgb, dtype=np.float64)
    return np.where(v <= .0031308, v * 12.92, 1.055 * np.maximum(v, 0) ** (1/2.4) - .055)


def classify(actor, slot):
    """Use actual mesh/slot identity, including generated floor/wall closures."""
    mesh = actor['mesh'].split('.')[-1]
    key = slot['name'].removeprefix('M_S3_').split('.')[0]
    if actor.get('skeletal'):
        return 'Brass' if slot['name']=='M_ArmorStage2_Brass' else None
    if key == 'iron': return 'BlackIron'
    if key == 'brass': return 'Brass'
    if key in ('wood', 'wood_end'): return 'Wood'
    if 'Runner' in mesh and key in ('GrandGateRunner_Center','GrandGateRunner_End','woven_runner'): return 'Carpet'
    if 'Banner' in mesh and key in ('cloth','guard_pennon','grand_pennon'): return 'Banner'
    if key in ('dressed_stone','limestone','flagstone','dark_stone','mid_stone'):
        if 'Floor_' in mesh:
            return 'FloorDiamond' if key in ('dark_stone','mid_stone') else 'Floor'
        if 'Pillar' in mesh or 'Pilaster' in mesh: return 'Pillar'
        if 'FinalGate_' in mesh: return 'GateDecorStone'
        if any(x in mesh for x in ('Wall','CatHole','ArmorDoor_Frame','PuzzleGate_Frame')): return 'Wall'
        # Remaining furnishing/puzzle stone has no user-specified color role.
        return None
    return None


def main():
    probe = json.loads((OUT/'source_probe.json').read_text())
    report = {'version':1, 'metric':'arithmetic mean of all mip0 source texels in IEC sRGB-decoded linear RGB; equal texel weighting',
              'formula':'BaseColor = original_BaseColor / SourceMeanLinear * ColorTint * Brightness',
              'parameter_semantics':{'ColorTint':'desired representative linear RGB, sRGB target decoded exactly', 'Brightness':'linear scalar; default 1'},
              'targets_srgb':TARGETS, 'textures':{}, 'calibrations':{}, 'assignments':[], 'preserved':[],
              'scope_note':'Grout/mortar, steel (including armor steel), armor joints/charcoal cloth, leather, wax, flame, paper, guardian statue and unspecified furnishing/puzzle stone preserve source; no material slot is dropped.'}
    arrays = {}
    for tex, row in probe['textures'].items():
        if '_BaseColor' not in tex: continue
        assert row['srgb'], tex
        source = Path(row['source_files'][0]).resolve()
        assert source.is_file(), source
        pixels = np.asarray(Image.open(source).convert('RGB'),dtype=np.float64)/255
        data = decode(pixels)
        mean = data.mean(axis=(0,1))
        assert np.min(mean) > 1e-8
        report['textures'][tex] = {'source':str(source), 'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'size':[data.shape[1],data.shape[0]],'source_mean_linear':mean.tolist(),
            'source_mean_srgb':(encode(mean)*255).tolist(), 'source_std_linear':data.std(axis=(0,1)).tolist()}
        arrays[tex] = data
    for actor in probe['actors']:
        for slot in actor['slots']:
            role = classify(actor,slot)
            assignment = {'actor':actor['actor'], 'actor_path':actor['actor_path'], 'component':actor['component'],
                          'mesh':actor['mesh'],'slot':slot['index'],'slot_name':slot['name'],'source_material':slot['material']}
            if not role:
                report['preserved'].append(assignment)
                continue
            mat = probe['materials'][slot['material']]
            prop = mat['properties']['BASE_COLOR']
            node = next(n for n in mat['nodes'] if n['name']==prop['node'])
            assert node['class']=='MaterialExpressionTextureSample' and prop['output']=='RGB', (slot,node,prop)
            tex = node['texture']
            assert tex in arrays
            source_base = mat['base']
            key = source_base.split('.')[-1] + '__' + role
            if key not in report['calibrations']:
                target = decode(np.array(TARGETS[role])/255)
                data = arrays[tex]
                mean = np.array(report['textures'][tex]['source_mean_linear'])
                tint = target
                out = data/mean*tint
                clipped = (out>1).mean(axis=(0,1))
                assert np.max(clipped)==0, ('Clipping needs alternate preserving mapping', key,clipped)
                avg = out.mean(axis=(0,1))
                report['calibrations'][key] = {'role':role,'source_base_material':source_base,'source_texture':tex,
                    'target_srgb':TARGETS[role],'target_linear':target.tolist(),'source_mean_linear':mean.tolist(),
                    'source_normalization':(1/mean).tolist(),'color_tint':tint.tolist(),'brightness':1.,
                    'effective_multiplier':(tint/mean).tolist(),'result_mean_linear':avg.tolist(),
                    'result_srgb':(encode(avg)*255).tolist(),'result_std_linear':out.std(axis=(0,1)).tolist(),
                    'clipped_fraction':clipped.tolist(),'source_blend_mode':mat['blend_mode'],
                    'source_two_sided':mat['two_sided']}
            assignment.update(role=role,calibration=key)
            report['assignments'].append(assignment)
    report['role_counts'] = dict(Counter(x['role'] for x in report['assignments']))
    assert set(report['role_counts'])==set(TARGETS), report['role_counts']
    report['source_material_count']=len(probe['materials'])
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'calibrations':len(report['calibrations']), 'assignments':len(report['assignments']),
                      'preserved':len(report['preserved']), 'roles':report['role_counts']}))


if __name__=='__main__': main()
