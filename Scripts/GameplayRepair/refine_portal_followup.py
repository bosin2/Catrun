"""Refine the verified portal followup: material flow and wide shot framing only.

Fresh commandlet flags: -catrunPortalRefineAuthor|Audit and
-catrunPortalRefineBaseline=".../report.json". Author consumes the completed
original followup author report; Audit consumes this script's author report.
Root must render the actual sequence separately; this never claims visual QA.
"""
import ast
import datetime
import gc
import json
import math
import os
from pathlib import Path
import re
import shutil
import traceback
import types

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
FOLLOWUP_PATH = ROOT / 'Scripts/GameplayRepair/author_portal_followup.py'
tree = ast.parse(FOLLOWUP_PATH.read_text(encoding='utf-8'))
entry = next(i for i, node in enumerate(tree.body)
             if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'command' for t in node.targets))
f = types.ModuleType('portal_refinement_helpers')
f.__dict__['__file__'] = str(FOLLOWUP_PATH)
exec(compile(ast.Module(body=tree.body[:entry], type_ignores=[]), str(FOLLOWUP_PATH), 'exec'), f.__dict__)
h = f.helper
EDIT, AS = f.EDIT, f.AS
EDITED = (f.SEQUENCE, f.SURFACE, f.DEPTH, f.HALO)

# Architecture-focused cameras, with room for the cat's ground contact.
# Targets are authored architectural points, never sampled from cat movement.
CAMERAS = (
    f.curve(((0, (80., 78., 92.), (101., -245., 53.)),
             (32, (72., 48., 98.), (101., -261., 63.)),
             (64, (63., 15., 108.), (101., -274., 72.)),
             (96, (54., -22., 120.), (101., -285., 82.)))),
    f.curve(((96, (151., -50., 120.), (101., h.PORTAL_Y, 82.)),
             (120, (149., -58., 122.), (101., h.PORTAL_Y, 84.)),
             (144, (145., -67., 123.), (101., h.PORTAL_Y, 85.)),
             (168, (140., -75., 122.), (101., h.PORTAL_Y, 85.)))),
    f.CAMERA_CURVES[2],
)
FOVS = (84., 84., 76.)

# Cartesian value noise is periodic across the atan2 seam. A rotated, radially
# compressed domain gives the clouds a coherent inward flow without 15 repeated
# pinstripes. Three octaves shape the body, one restrained fiber term adds detail.
FLOW = '''float2 p=(UV-.5)*2.;
float r=length(p); float a=atan2(p.y,p.x+0.00001);
float twist=2.25*log(max(r,.04))-.23*T;
float ca=cos(twist), sa=sin(twist);
float2 q=float2(ca*p.x-sa*p.y,sa*p.x+ca*p.y)*3.7;
q+=float2(.06*T,-.035*T);
float cloud=0.; float amp=.57;
for(int octave=0;octave<4;octave++) {
 float2 cell=floor(q); float2 b=frac(q); b=b*b*(3.-2.*b);
 float n00=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);
 float n10=frac(sin(dot(cell+float2(1,0),float2(127.1,311.7)))*43758.5453);
 float n01=frac(sin(dot(cell+float2(0,1),float2(127.1,311.7)))*43758.5453);
 float n11=frac(sin(dot(cell+float2(1,1),float2(127.1,311.7)))*43758.5453);
 cloud+=amp*lerp(lerp(n00,n10,b.x),lerp(n01,n11,b.x),b.y);
 q=q*2.03+float2(7.3,11.7); amp*=.48;
}
float bend=2.*a+4.5*log(max(r,.045))-.46*T;
float ribbon=pow(saturate(.5+.5*cos(bend+1.9*(cloud-.5))),1.8);
float wisps=saturate(.5+.5*sin(7.*bend+cloud*17.+r*14.));
wisps=pow(wisps,10.)*.16;
float body=smoothstep(.10,.26,r)*(1.-smoothstep(.80,.96,r));
float edge=r-(.905+.010*sin(a*7.-T*.6)+.006*sin(a*17.+T*.9));
float rim=exp(-pow(edge/.022,2.));
float haze=exp(-abs(edge)*19.);
float flecks=.65+.35*sin(a*29.+cloud*11.-T*1.1);
float3 cyan=float3(.07,1.1,1.75);
float3 violet=float3(.63,.12,1.4);
float3 energy=lerp(violet,cyan,saturate(.18+.65*cloud+.12*sin(bend)));
'''
SURFACE_COLOR = FLOW + '''return float3(.002,.004,.016)
 + energy*body*(.22+2.6*ribbon)*(.42+.92*cloud)
 + float3(.16,.65,1.7)*body*wisps
 + lerp(float3(.08,2.5,4.0),float3(.5,1.4,3.1),.5+.5*sin(a*3.-T*.2))
   *(rim*(.9+.4*flecks)+haze*.29);
'''
SURFACE_OPACITY = FLOW + '''return (1.-smoothstep(.018,.075,edge))
 * saturate(.31+.19*body+.23*ribbon*body+.16*cloud*body+.25*rim);
'''
DEPTH_COLOR = FLOW + '''return float3(.0015,.0025,.009)
 + energy*body*(.045+.13*ribbon)*(.5+.6*cloud);
'''
# The mask and its clipping threshold are deliberately unchanged: disappearance
# continues to be actual scene depth followed by the existing frame284 hide key.
DEPTH_MASK = f.DEPTH_MASK
HALO_COLOR = FLOW + '''float band=exp(-pow((r-.81)/.055,2.));
float threads=pow(saturate(.5+.5*sin(a*19.+cloud*13.-T*.6)),7.);
return lerp(float3(.025,.85,1.5),float3(.48,.12,1.2),cloud)
 *band*(.48+.65*threads);
'''
HALO_OPACITY = f.HALO_OPACITY
CODES = {
    f.SURFACE: (SURFACE_COLOR, SURFACE_OPACITY),
    f.DEPTH: (DEPTH_COLOR, DEPTH_MASK),
    f.HALO: (HALO_COLOR, HALO_OPACITY),
}


def material_state(material):
    result = h.describe_material(material)
    mask = h.material_input(material, u.MaterialProperty.MP_OPACITY_MASK)
    result['mask_code'] = mask.get_editor_property('code') if mask else None
    result['mask_clip'] = material.get_editor_property('opacity_mask_clip_value')
    return result


def state(sequence, presentation, materials):
    result = f.state(sequence, presentation, materials[f.SURFACE])
    result['materials'] = {package: material_state(mat) for package, mat in materials.items()}
    return result


def patch_camera(sequence):
    sequence.modify()
    parts = h.sequence_parts(sequence)
    for index in (0, 1):
        for axis, channel in enumerate(h.transform_channels(parts['camera_sections'][index])):
            values = [(frame, value[axis]) for frame, value in CAMERAS[index]]
            default = values[0][1]
            h.write_keys(channel, values if any(value != default for _, value in values) else (), default)
        camera = parts['camera_components'][index]
        camera.modify()
        camera.set_field_of_view(FOVS[index])


def verify(after, before):
    for field in before:
        if field not in ('sequence', 'surface', 'materials'):
            assert f.normalized(after[field]) == f.normalized(before[field]), ('Protected state', field)
    for field in before['sequence']:
        if field != 'cameras':
            assert f.normalized(after['sequence'][field]) == f.normalized(before['sequence'][field]), field
    assert f.normalized(after['sequence']['cameras'][2]) == f.normalized(before['sequence']['cameras'][2])
    for row, keys, fov in zip(after['sequence']['cameras'], CAMERAS, FOVS):
        assert row['fov'] == fov
        for axis, channel in enumerate(row['keys']):
            values = [(h.tick(frame), value[axis]) for frame, value in keys]
            default = values[0][1]
            expected = values if any(value != default for _, value in values) else []
            assert len(channel) == len(expected)
            assert all(t == et and math.isclose(v, ev, abs_tol=1.e-5) for (t, v), (et, ev) in zip(channel, expected))
            assert math.isclose(row['defaults'][axis], default, abs_tol=1.e-5)
    for package, (color, opacity) in CODES.items():
        old, new = before['materials'][package], after['materials'][package]
        for field in ('domain', 'blend', 'two_sided', 'shading', 'has_mask', 'mask_clip'):
            assert old[field] == new[field], (package, field)
        assert new['color']['code'] == color and new['color']['inputs'] == ['UV', 'T']
        if package == f.DEPTH:
            assert new['mask_code'] == old['mask_code'] == DEPTH_MASK
        else:
            assert new['opacity']['code'] == opacity
            assert new['opacity']['inputs'] == old['opacity']['inputs']


def run(mode, baseline_path):
    output = ROOT / 'Saved/GameplayRepair20261112/PortalFollowup/Refinement' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    report = dict(mode=mode, pid=os.getpid(), completed=False, saved=[], backups=[],
                  source_sha256=f.digest(Path(__file__)), followup_sha256=f.digest(FOLLOWUP_PATH),
                  helper_sha256=f.digest(f.HELPER_PATH), visual_acceptance=False, playback_performed=False)
    def persist():
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        assert baseline_path
        baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8'))
        assert baseline['completed'] and baseline['mode'] == 'author' and baseline['pid'] != os.getpid()
        assert not h.ED.get_game_world() and not h.dirty(), h.dirty()
        assert all(u.SystemLibrary.get_console_variable_int_value(name) == 0 for name in h.ISOLATED_CVARS)
        report['before_hashes'] = f.hashes()
        assert all(report['before_hashes'].values())
        if mode == 'author':
            assert baseline['source_sha256'] == report['followup_sha256']
            assert baseline['helper_sha256'] == report['helper_sha256']
            # Other authorized tasks may edit map gameplay data. Their *current*
            # hashes are protected for this run; portal assets must match exactly.
            for package in f.OWNED:
                assert baseline['after_hashes'][package] == report['before_hashes'][package], package
        else:
            for key in ('source_sha256', 'followup_sha256', 'helper_sha256'):
                assert baseline[key] == report[key], key
            assert baseline['after_hashes'] == report['before_hashes']
        sequence, presentation = [h.load_asset(p) for p in (f.SEQUENCE, f.PRESENTATION)]
        materials = {p: h.load_asset(p) for p in CODES}
        report['before'] = state(sequence, presentation, materials)
        if mode == 'author':
            f.verify(report['before'], baseline['before'])
        # Full collision sweeps and architectural aperture traces run against the
        # proposed cameras before any edits. Never save an opened protected map.
        f.CAMERA_CURVES = h.CAMERA_CURVES = CAMERAS
        report['maps'] = {}
        for package in h.MAPS:
            report['maps'][package] = h.verify_map(package)
            report['maps'][package]['portal_aperture_sightlines'] = f.verify_portal_sightlines(package)
        if mode == 'author':
            assert not h.dirty(), h.dirty()
            world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
            gc.collect()
            u.collect_garbage()
            assert world and h.ED.get_editor_world() == world
            assert not world.get_path_name().startswith('/Game/') and not h.dirty()
            report['author_world'] = world.get_path_name()
            for package in EDITED:
                source = f.asset_file(package)
                destination = output / 'Before' / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                assert f.digest(destination) == report['before_hashes'][package]
                report['backups'].append(str(destination))
            persist()
            patch_camera(sequence)
            for package, (color, opacity) in CODES.items():
                material = materials[package]
                material.modify()
                prop = u.MaterialProperty.MP_OPACITY_MASK if package == f.DEPTH else u.MaterialProperty.MP_OPACITY
                for target, code in ((u.MaterialProperty.MP_EMISSIVE_COLOR, color), (prop, opacity)):
                    node = h.material_input(material, target)
                    assert isinstance(node, u.MaterialExpressionCustom)
                    if node.get_editor_property('code') != code:
                        node.modify()
                        node.set_editor_property('code', code)
            report['shader_errors'] = {p: list(EDIT.recompile_material(m)) for p, m in materials.items()}
            assert not any(report['shader_errors'].values()), report['shader_errors']
        report['after'] = state(sequence, presentation, materials)
        verify(report['after'], baseline['before'] if mode == 'audit' else report['before'])
        if mode == 'audit':
            assert f.normalized(report['after']) == baseline['after'], 'Cold state differs'
            assert f.normalized(report['maps']) == baseline['maps'], 'Cold geometry differs'
        else:
            assert set(h.dirty()) <= set(EDITED), h.dirty()
            for package in EDITED:
                assert AS.save_asset(package, only_if_is_dirty=False), package
                report['saved'].append(package)
                persist()
        report['after_hashes'] = f.hashes()
        for package, value in report['before_hashes'].items():
            assert (report['after_hashes'][package] != value) == (package in report['saved']), package
        assert not h.dirty(), h.dirty()
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        report['dirty'] = h.dirty()
        raise
    finally:
        persist()
        print('CATRUN_PORTAL_REFINE', mode, report['completed'], str(output / 'report.json'))


command = u.SystemLibrary.get_command_line()
modes = re.findall(r'(?:^|\s)-catrunPortalRefine(Author|Audit)(?=\s|$)', command, re.I)
baseline = re.search(r'-catrunPortalRefineBaseline=(?:"([^"]+)"|(\S+))', command, re.I)
run(h.only(modes).lower(), (baseline.group(1) or baseline.group(2)) if baseline else None)
