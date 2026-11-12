"""Add one restrained camera-side fill to the verified portal presentation BP.

Fresh commandlet: -catrunPortalFillAuthor|Audit and
-catrunPortalFillBaseline=".../report.json". Author requires completed refinement
author report. Audit requires this script's author report. No map/sequence saves.
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
REFINEMENT_PATH = ROOT / 'Scripts/GameplayRepair/refine_portal_followup.py'
tree = ast.parse(REFINEMENT_PATH.read_text(encoding='utf-8'))
entry = next(i for i, node in enumerate(tree.body)
             if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'command' for t in node.targets))
r = types.ModuleType('portal_fill_helpers')
r.__dict__['__file__'] = str(REFINEMENT_PATH)
exec(compile(ast.Module(body=tree.body[:entry], type_ignores=[]), str(REFINEMENT_PATH), 'exec'), r.__dict__)
f, h = r.f, r.h
NAME = 'PortalApproachFill'
POSITION = (-40., -230., 105.)
INTENSITY, RADIUS = 120., 350.
LIGHT_PROPERTIES = ('intensity', 'intensity_units', 'attenuation_radius',
                    'use_inverse_squared_falloff', 'light_color', 'cast_shadows',
                    'source_radius', 'soft_source_radius', 'source_length',
                    'indirect_lighting_intensity', 'volumetric_scattering_intensity',
                    'mobility', 'visible', 'relative_location', 'relative_rotation',
                    'relative_scale3d')


def light_state(light):
    result = {}
    for name in LIGHT_PROPERTIES:
        value = light.get_editor_property(name)
        result[name] = value if isinstance(value, (str, int, float, bool)) else value.export_text() if hasattr(value, 'export_text') else str(value)
    return result


def component_names(bp):
    subsystem = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    library = u.SubobjectDataBlueprintFunctionLibrary
    return sorted(set(obj.get_name().removesuffix('_GEN_VARIABLE')
                      for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp)
                      if (obj := library.get_associated_object(library.get_data(handle)))
                      and isinstance(obj, u.ActorComponent)))


def state(sequence, presentation, materials):
    result = r.state(sequence, presentation, materials)
    result['blue_light'] = light_state(f.component(presentation, 'BlueLight'))
    result['component_names'] = component_names(presentation)
    result['fill'] = light_state(f.component(presentation, NAME)) if NAME in result['component_names'] else None
    return result


def patch(bp):
    bp.modify()
    f.ActorTools.add_component(bp, u.PointLightComponent.static_class(), NAME)
    light = f.component(bp, NAME)
    light.set_editor_property('relative_location', u.Vector(*POSITION))
    light.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    light.set_editor_property('intensity_units', u.LightUnits.LUMENS)
    light.set_editor_property('use_inverse_squared_falloff', True)
    light.set_light_color(u.LinearColor(.42, .62, 1., 1.))
    light.set_intensity(INTENSITY)
    light.set_attenuation_radius(RADIUS)
    light.set_editor_property('cast_shadows', True)
    light.set_editor_property('source_radius', 25.)
    light.set_editor_property('soft_source_radius', 40.)
    light.set_editor_property('source_length', 0.)
    light.set_editor_property('indirect_lighting_intensity', 0.)
    light.set_editor_property('volumetric_scattering_intensity', 0.)
    f.compile_bp(bp)


def verify(after, before):
    for key in before:
        if key not in ('fill', 'component_names'):
            assert f.normalized(after[key]) == f.normalized(before[key]), ('Protected state', key)
    assert after['component_names'] == sorted([*before['component_names'], NAME])
    value = after['fill']
    for prop, expected in (('intensity', INTENSITY), ('attenuation_radius', RADIUS),
                           ('source_radius', 25.), ('soft_source_radius', 40.),
                           ('source_length', 0.), ('indirect_lighting_intensity', 0.),
                           ('volumetric_scattering_intensity', 0.)):
        assert math.isclose(value[prop], expected, abs_tol=1.e-5), (prop, value[prop])
    assert 'LUMENS' in value['intensity_units'] and 'MOVABLE' in value['mobility']
    assert value['use_inverse_squared_falloff'] and value['cast_shadows'] and value['visible']
    assert value['relative_location'] == u.Vector(*POSITION).export_text()


def run(mode, baseline_path):
    output = ROOT / 'Saved/GameplayRepair20261112/PortalFollowup/Fill' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    report = dict(mode=mode, pid=os.getpid(), completed=False, saved=[], backups=[],
                  source_sha256=f.digest(Path(__file__)), refinement_sha256=f.digest(REFINEMENT_PATH),
                  followup_sha256=f.digest(r.FOLLOWUP_PATH), helper_sha256=f.digest(f.HELPER_PATH),
                  visual_acceptance=False, playback_performed=False,
                  expectation='Low camera-side cool fill reveals the approaching black cat; portal remains brightest. Actual render QA required.',
                  expected_world_position=(141., h.PORTAL_Y + 230., 104.2))
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
            assert baseline['source_sha256'] == report['refinement_sha256']
            for key in ('followup_sha256', 'helper_sha256'):
                assert baseline[key] == report[key], key
            for package in f.OWNED:
                assert baseline['after_hashes'][package] == report['before_hashes'][package], package
        else:
            for key in ('source_sha256', 'refinement_sha256', 'followup_sha256', 'helper_sha256'):
                assert baseline[key] == report[key], key
            assert baseline['after_hashes'] == report['before_hashes']
        sequence, presentation = [h.load_asset(p) for p in (f.SEQUENCE, f.PRESENTATION)]
        materials = {p: h.load_asset(p) for p in r.CODES}
        report['before'] = state(sequence, presentation, materials)
        if mode == 'author':
            assert report['before']['fill'] is None and NAME not in report['before']['component_names']
            assert f.normalized({k: v for k, v in report['before'].items() if k in baseline['after']}) == baseline['after']
            world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
            gc.collect()
            u.collect_garbage()
            assert world and h.ED.get_editor_world() == world
            assert not world.get_path_name().startswith('/Game/') and not h.dirty()
            report['author_world'] = world.get_path_name()
            source = f.asset_file(f.PRESENTATION)
            destination = output / 'Before' / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            assert f.digest(destination) == report['before_hashes'][f.PRESENTATION]
            report['backups'].append(str(destination))
            persist()
            patch(presentation)
        report['after'] = state(sequence, presentation, materials)
        verify(report['after'], baseline['before'] if mode == 'audit' else report['before'])
        if mode == 'audit':
            assert f.normalized(report['after']) == baseline['after'], 'Cold state differs'
        else:
            assert set(h.dirty()) <= {f.PRESENTATION}, h.dirty()
            assert f.AS.save_asset(f.PRESENTATION, only_if_is_dirty=False)
            report['saved'].append(f.PRESENTATION)
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
        print('CATRUN_PORTAL_FILL', mode, report['completed'], str(output / 'report.json'))


command = u.SystemLibrary.get_command_line()
modes = re.findall(r'(?:^|\s)-catrunPortalFill(Author|Audit)(?=\s|$)', command, re.I)
baseline = re.search(r'-catrunPortalFillBaseline=(?:"([^"]+)"|(\S+))', command, re.I)
run(h.only(modes).lower(), (baseline.group(1) or baseline.group(2)) if baseline else None)
