"""Portal-first camera composition and layered portal depth, root-run only.

Fresh commandlet: -catrunPortalFollowupProbe|Author|Audit. Author requires a
completed probe report, audit a completed author report, through
-catrunPortalFollowupBaseline=".../report.json". Same isolated-geometry CVars
as upgrade_portal_paw_20261112.py. No PIE, playback, native choreography or maps
are saved. Root must separately render the actual sequence before visual signoff.
"""
import ast
import datetime
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
import types

import unreal as u
from editor_toolset.toolsets.actor import ActorTools

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import compile_bp

# Reuse the tested geometry/sequence inspection functions without executing the
# older one-shot paw authoring entrypoint. The dependency hash is in every report.
HELPER_PATH = ROOT / 'Scripts/GameplayRepair/upgrade_portal_paw_20261112.py'
tree = ast.parse(HELPER_PATH.read_text(encoding='utf-8'))
entry = next(i for i, node in enumerate(tree.body)
             if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'command' for t in node.targets))
helper = types.ModuleType('portal_followup_geometry')
helper.__dict__['__file__'] = str(HELPER_PATH)
exec(compile(ast.Module(body=tree.body[:entry], type_ignores=[]), str(HELPER_PATH), 'exec'), helper.__dict__)

AS, EDIT = u.EditorAssetLibrary, u.MaterialEditingLibrary
BASE = '/Game/Cinematics/Stage1/Portal/'
SEQUENCE = BASE + 'LS_Stage1_PortalExit'
PRESENTATION = BASE + 'BP_Stage1PortalPresentation'
SURFACE = BASE + 'M_Stage1PortalBlue'
DEPTH = BASE + 'Followup20261112/M_PortalDepthCore'
HALO = BASE + 'Followup20261112/M_PortalAetherHalo'
OWNED = (SEQUENCE, PRESENTATION, SURFACE, DEPTH, HALO)
PROTECTED = (*helper.MAPS, *helper.CLIPS, BASE + 'BP_Stage1PortalExit', BASE + 'WBP_ExitTransition')
END, ENTRY_COMPLETE = 308, 284
CUTS = ((0, 96), (96, 168), (168, END))
FOVS = (78., 84., 76.)
SHOT_LABELS = ('01 Corridor and portal reveal', '02 Raised lateral portal study', '03 Threshold and disappearance')


def curve(rows):
    return [helper.camera_key(frame, position, target) for frame, position, target in rows]


# Distances are in cm; portal center is (101, -293.919, 89.2). These cameras stay
# inside the corridor and aim at architecture. Cat motion is deliberately absent
# from all look-at targets. Camera distances are materially wider than the old
# 45-110 cm face/backward-follow views.
CAMERA_CURVES = (
    curve(((0, (80., 5., 128.), (101., -245., 82.)),
           (32, (72., -3., 132.), (101., -261., 87.)),
           (64, (63., -12., 135.), (101., -274., 91.)),
           (96, (54., -22., 136.), (101., -285., 94.)))),
    curve(((96, (151., -50., 120.), (101., helper.PORTAL_Y, 94.)),
           (120, (149., -58., 122.), (101., helper.PORTAL_Y, 96.)),
           (144, (145., -67., 123.), (101., helper.PORTAL_Y, 97.)),
           (168, (140., -75., 122.), (101., helper.PORTAL_Y, 97.)))),
    curve(((168, (74., -3., 94.), (101., helper.PORTAL_Y, 91.)),
           (216, (79., -15., 96.), (101., helper.PORTAL_Y, 93.)),
           (238, (84., -23., 98.), (101., helper.PORTAL_Y, 94.)),
           (270, (91., -37., 102.), (101., helper.PORTAL_Y, 96.)),
           (284, (94., -43., 104.), (101., helper.PORTAL_Y, 97.)),
           (308, (96., -47., 105.), (101., helper.PORTAL_Y, 98.)))),
)
ORIGINAL_CAMERA_CURVES = helper.CAMERA_CURVES
helper.CAMERA_CURVES, helper.CUTS = CAMERA_CURVES, CUTS

# Keep a dark eye surrounded by several uneven, coherent spiral arms. A layered
# surface and halo provide translucent filaments; the depth core below writes
# depth so a pawn behind the threshold cannot show through the transmission.
FLOW = '''float2 p=(UV-.5)*2.;
float r=length(p); float a=atan2(p.y,p.x+0.00001);
float aa=clamp(fwidth(r),.002,.022);
float bend=a+2.35*log(max(r,.028))-.33*T;
float turbulence=.19*sin(a*5.+r*14.+T*.43)+.08*sin(a*11.-r*23.-T*.61);
float arm=pow(saturate(.5+.5*cos(3.*bend+turbulence)),3.5);
float filament=pow(saturate(.5+.5*sin(15.*bend+r*18.+turbulence)),14.);
float body=smoothstep(.07,.24,r)*(1.-smoothstep(.72,.96,r));
float edge=r-(.91+.009*sin(a*9.-T*.8)+.005*sin(a*21.+T));
float rim=exp(-pow(edge/.017,2.));
float glow=exp(-abs(edge)*28.);
float3 blue=float3(.035,.48,1.65);
float3 violet=float3(.47,.095,1.05);
float3 energy=lerp(blue,violet,.5+.5*sin(bend*2.+r*8.));
'''
SURFACE_COLOR = FLOW + '''return float3(.003,.006,.021)
 + energy*body*(.32+.75*arm+.75*filament)
 + lerp(float3(.12,1.1,3.1),float3(.64,.3,2.5),.5+.5*sin(a*2.+T*.2))*(rim*.95+glow*.19);
'''
SURFACE_OPACITY = FLOW + '''return (1.-smoothstep(.015,.065+aa,edge))
 * saturate(.22+.22*body+.22*arm*body+.3*rim+.17*glow);
'''
DEPTH_COLOR = FLOW + '''return float3(.0015,.003,.012)+energy*body*(.055+.12*arm+.10*filament);
'''
DEPTH_MASK = 'float2 p=(UV-.5)*2.; return .915-length(p);'
HALO_COLOR = FLOW + '''float halo=exp(-abs(r-.82)*34.);
float streak=pow(saturate(.5+.5*sin(33.*a+9.*r-T*.8)),18.);
return lerp(float3(.025,.3,1.3),float3(.5,.06,1.1),.5+.5*sin(a*3.-T*.3))
 * (halo*.16+halo*streak*.45);
'''
HALO_OPACITY = 'float2 p=(UV-.5)*2.; float r=length(p); return (1.-smoothstep(.94,1.,r))*.55;'
PP_VALUES = {'motion_blur_amount': .12, 'motion_blur_max': 1.5,
             'bloom_intensity': .42, 'depth_of_field_fstop': 8.,
             'depth_of_field_focal_distance': 260., 'vignette_intensity': .12}


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None


def asset_file(package):
    return ROOT / 'Content' / (package.removeprefix('/Game/') + ('.umap' if package in helper.MAPS else '.uasset'))


def hashes():
    return {package: digest(asset_file(package)) for package in (*OWNED, *PROTECTED)}


def component(bp, name):
    subsystem = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    library = u.SubobjectDataBlueprintFunctionLibrary
    objects = [library.get_associated_object(library.get_data(handle))
               for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp)]
    unique = {obj.get_path_name(): obj for obj in objects if obj and obj.get_name().removesuffix('_GEN_VARIABLE') == name}
    return helper.only(unique.values())


def visibility_state(sequence):
    cat = helper.sequence_parts(sequence)['bindings'][0]
    tracks = cat.find_tracks_by_type(u.MovieSceneVisibilityTrack)
    if not tracks:
        return None
    section = helper.only(helper.only(tracks).get_sections())
    return {'range': helper.span(section), 'completion': str(section.get_completion_mode()),
            'keys': helper.key_data(helper.only(section.get_all_channels()))}


def patch_sequence(sequence):
    sequence.modify()
    parts = helper.sequence_parts(sequence)
    for index, (section, camera, keys, fov) in enumerate(zip(parts['camera_sections'], parts['camera_components'], CAMERA_CURVES, FOVS)):
        for axis, channel in enumerate(helper.transform_channels(section)):
            values = [(frame, value[axis]) for frame, value in keys]
            default = values[0][1]
            helper.write_keys(channel, values if any(value != default for _, value in values) else (), default)
        camera.modify()
        camera.set_field_of_view(fov)
        settings = camera.get_editor_property('post_process_settings').copy()
        for name, value in PP_VALUES.items():
            settings.set_editor_property('override_' + name, True)
            settings.set_editor_property(name, value)
        camera.set_editor_property('post_process_settings', settings)
        camera.set_editor_property('post_process_blend_weight', 1.)
        # Keep binding names/IDs for existing editor tools and Blueprint tags.
        parts['camera_sections'][index].set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    cat = parts['bindings'][0]
    assert not cat.find_tracks_by_type(u.MovieSceneVisibilityTrack)
    track = cat.add_track(u.MovieSceneVisibilityTrack)
    track.set_property_name_and_path('bHidden', 'bHidden')
    section = track.add_section()
    section.set_range(0, END)
    section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    channel = helper.only(section.get_all_channels())
    channel.set_default(True)
    # Visibility track stores visible semantics; UE inverts into Actor::bHidden.
    channel.add_key(u.FrameNumber(0), True)
    channel.add_key(u.FrameNumber(ENTRY_COMPLETE), False)


def make_material(package, color, opacity, masked=False, additive=False):
    assert not AS.does_asset_exist(package), ('Refuse overwrite', package)
    folder, name = package.rsplit('/', 1)
    material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    assert material
    material.set_editor_property('two_sided', True)
    material.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED if masked else
                                 u.BlendMode.BLEND_ADDITIVE if additive else u.BlendMode.BLEND_TRANSLUCENT)
    uv = helper.new_expression(material, u.MaterialExpressionTextureCoordinate, (-600, 0))
    time = helper.new_expression(material, u.MaterialExpressionTime, (-600, 180))
    color_node = helper.custom_expression(material, (-200, 0), 'Layered portal flow', color,
                                          u.CustomMaterialOutputType.CMOT_FLOAT3, (('UV', uv), ('T', time)))
    opacity_node = helper.custom_expression(material, (-200, 250), 'Threshold depth' if masked else 'Aether transmission',
                                            opacity, u.CustomMaterialOutputType.CMOT_FLOAT1, (('UV', uv),))
    if masked:
        material.set_editor_property('opacity_mask_clip_value', .001)
    assert EDIT.connect_material_property(color_node, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert EDIT.connect_material_property(opacity_node, '', u.MaterialProperty.MP_OPACITY_MASK if masked else u.MaterialProperty.MP_OPACITY)
    return material


def patch_presentation(bp, depth, halo):
    bp.modify()
    for name in ('PortalDepthCore', 'PortalAetherHalo'):
        ActorTools.add_component(bp, u.StaticMeshComponent.static_class(), name)
    for name, material, offset, scale in (
            ('PortalDepthCore', depth, 2., (1.05, 1.8, 1.)),
            ('PortalAetherHalo', halo, -3., (1.18, 2.02, 1.))):
        mesh = component(bp, name)
        mesh.set_static_mesh(helper.load_asset('/Engine/BasicShapes/Plane'))
        mesh.set_material(0, material)
        mesh.set_editor_property('relative_location', u.Vector(0, offset, 90))
        mesh.set_editor_property('relative_rotation', u.Rotator(pitch=0, yaw=0, roll=90))
        mesh.set_editor_property('relative_scale3d', u.Vector(*scale))
        mesh.set_collision_profile_name('NoCollision')
        mesh.set_editor_property('generate_overlap_events', False)
        mesh.set_editor_property('cast_shadow', False)
        mesh.set_editor_property('mobility', u.ComponentMobility.STATIC)
    compile_bp(bp)


def presentation_state(bp):
    result = {}
    for name in ('Stone', 'Runes', 'Surface', 'BlueLight', 'PortalDepthCore', 'PortalAetherHalo'):
        try:
            item = component(bp, name)
        except AssertionError:
            if name in ('PortalDepthCore', 'PortalAetherHalo'):
                continue
            raise
        row = {prop: item.get_editor_property(prop).export_text()
               for prop in ('relative_location', 'relative_rotation', 'relative_scale3d')}
        if isinstance(item, u.StaticMeshComponent):
            row.update(mesh=item.get_editor_property('static_mesh').get_path_name(),
                       material=item.get_material(0).get_path_name(),
                       collision=str(item.get_collision_profile_name()),
                       overlaps=item.get_editor_property('generate_overlap_events'))
        result[name] = row
    return result


def state(sequence, presentation, material):
    parts = helper.sequence_parts(sequence)
    return {'sequence': helper.describe_sequence(sequence), 'visibility': visibility_state(sequence),
            'presentation': presentation_state(presentation), 'surface': helper.describe_material(material),
            'post_process': [{name: camera.get_editor_property('post_process_settings').get_editor_property(name)
                              for name in PP_VALUES} for camera in parts['camera_components']]}


def normalized(value):
    return json.loads(json.dumps(value))


def verify(after, before):
    old, new = before['sequence'], after['sequence']
    for field in ('end', 'cuts', 'bindings', 'spawn_ranges', 'cat', 'animations', 'light', 'light_transform', 'fade'):
        assert normalized(new[field]) == normalized(old[field]), ('Protected sequence data changed', field)
    assert new['end'] == END and normalized(new['cuts']) == normalized(CUTS)
    for row, keys, fov in zip(new['cameras'], CAMERA_CURVES, FOVS):
        assert row['fov'] == fov
        for axis, channel in enumerate(row['keys']):
            values = [(helper.tick(frame), value[axis]) for frame, value in keys]
            default = values[0][1]
            expected = values if any(value != default for _, value in values) else []
            assert len(channel) == len(expected)
            assert all(t == et and math.isclose(v, ev, abs_tol=1.e-5) for (t, v), (et, ev) in zip(channel, expected))
            assert math.isclose(row['defaults'][axis], default, abs_tol=1.e-5)
    assert after['visibility']['range'] == (0, END)
    assert after['visibility']['keys'] == [(0, True), (helper.tick(ENTRY_COMPLETE), False)]
    assert 'RESTORE_STATE' in after['visibility']['completion']
    assert all(all(math.isclose(pp[name], value, abs_tol=1.e-5) for name, value in PP_VALUES.items()) for pp in after['post_process'])
    for name in ('Stone', 'Runes', 'Surface', 'BlueLight'):
        assert after['presentation'][name] == before['presentation'][name], name
    assert len(after['presentation']) == 6
    for name, material in (('PortalDepthCore', DEPTH), ('PortalAetherHalo', HALO)):
        row = after['presentation'][name]
        assert row['material'] == material + '.' + material.rsplit('/', 1)[1]
        assert row['collision'] == 'NoCollision' and not row['overlaps']
    assert after['surface']['color']['code'] == SURFACE_COLOR
    assert after['surface']['opacity']['code'] == SURFACE_OPACITY
    for package, color, opacity, masked in ((DEPTH, DEPTH_COLOR, DEPTH_MASK, True), (HALO, HALO_COLOR, HALO_OPACITY, False)):
        material = helper.load_asset(package)
        assert helper.material_input(material, u.MaterialProperty.MP_EMISSIVE_COLOR).get_editor_property('code') == color
        prop = u.MaterialProperty.MP_OPACITY_MASK if masked else u.MaterialProperty.MP_OPACITY
        assert helper.material_input(material, prop).get_editor_property('code') == opacity


def verify_portal_sightlines(package):
    # helper.verify_map already checks every half-frame capsule/camera sample.
    # Additionally verify the aperture, not only the former cat-centric target.
    world = helper.ED.get_editor_world()
    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
    ignored = [a for a in actors if isinstance(a, u.Character)
               or 'CatrunAuthoredStage1Portal' in map(str, a.tags)
               or 'CatrunAuthoredStage1Exit' in map(str, a.tags)]
    count = 0
    for (first, last), keys in zip(CUTS, CAMERA_CURVES):
        for frame in range(first, last + 1, 6):
            position = u.Vector(*helper.camera_values(keys, frame)[:3])
            for x, z in ((101., 90.), (65., 65.), (137., 65.), (101., 172.)):
                hit = u.SystemLibrary.line_trace_single(world, position, u.Vector(x, helper.PORTAL_Y, z),
                    helper.VISIBILITY, False, ignored, helper.NONE, False)
                assert not hit, (package, frame, 'Portal aperture blocked', hit.to_dict())
                count += 1
    return count


def run(mode, baseline_path):
    output = ROOT / 'Saved/GameplayRepair20261112/PortalFollowup' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    report = {'mode': mode, 'pid': os.getpid(), 'completed': False, 'saved': [], 'backups': [],
              'source_sha256': digest(Path(__file__)), 'helper_sha256': digest(HELPER_PATH),
              'visual_acceptance': False, 'playback_performed': False, 'shot_labels': SHOT_LABELS}
    def persist():
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        assert not helper.ED.get_game_world() and not helper.dirty(), helper.dirty()
        assert all(u.SystemLibrary.get_console_variable_int_value(name) == 0 for name in helper.ISOLATED_CVARS)
        report['before_hashes'] = hashes()
        assert all(report['before_hashes'][p] for p in (*PROTECTED, SEQUENCE, PRESENTATION, SURFACE))
        baseline = None
        if mode in ('author', 'audit'):
            assert baseline_path, 'A completed baseline report is required'
            baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8'))
            assert baseline['completed'] and baseline['mode'] == ('probe' if mode == 'author' else 'author')
            assert baseline['pid'] != os.getpid()
            assert all(baseline[key] == report[key] for key in ('source_sha256', 'helper_sha256'))
            assert baseline['after_hashes'] == report['before_hashes'], 'Assets changed since baseline'
        sequence, presentation, material = [helper.load_asset(p) for p in (SEQUENCE, PRESENTATION, SURFACE)]
        report['before'] = state(sequence, presentation, material)
        if mode in ('probe', 'author'):
            assert report['before']['visibility'] is None
            assert not report['before_hashes'][DEPTH] and not report['before_hashes'][HALO]
            assert len(report['before']['presentation']) == 4
            helper.CAMERA_CURVES = ORIGINAL_CAMERA_CURVES
            try:
                helper.verify_sequence(report['before']['sequence'])
            finally:
                helper.CAMERA_CURVES = CAMERA_CURVES
        report['maps'] = {}
        for package in helper.MAPS:
            report['maps'][package] = helper.verify_map(package)
            report['maps'][package]['portal_aperture_sightlines'] = verify_portal_sightlines(package)
        persist()
        if mode == 'author':
            assert normalized(report['maps']) == baseline['maps']
            # Compiling a Blueprint with placed instances reinstantiates those
            # actors and can dirty their map. Unload the clean geometry world
            # before editing templates; never permit or save a protected map.
            assert not helper.dirty(), helper.dirty()
            world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
            gc.collect()
            u.collect_garbage()
            assert world and helper.ED.get_editor_world() == world
            assert not world.get_path_name().startswith('/Game/'), world.get_path_name()
            assert not helper.dirty(), helper.dirty()
            report['author_world'] = world.get_path_name()
            for package in (SEQUENCE, PRESENTATION, SURFACE):
                source = asset_file(package)
                destination = output / 'Before' / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                assert digest(destination) == report['before_hashes'][package]
                report['backups'].append(str(destination))
            persist()
            patch_sequence(sequence)
            material.modify()
            for prop, code in ((u.MaterialProperty.MP_EMISSIVE_COLOR, SURFACE_COLOR), (u.MaterialProperty.MP_OPACITY, SURFACE_OPACITY)):
                node = helper.material_input(material, prop)
                assert isinstance(node, u.MaterialExpressionCustom)
                node.modify()
                node.set_editor_property('code', code)
            depth = make_material(DEPTH, DEPTH_COLOR, DEPTH_MASK, masked=True)
            halo = make_material(HALO, HALO_COLOR, HALO_OPACITY, additive=True)
            patch_presentation(presentation, depth, halo)
            report['shader_errors'] = {mat.get_name(): list(EDIT.recompile_material(mat)) for mat in (material, depth, halo)}
            assert not any(report['shader_errors'].values()), report['shader_errors']
        if mode in ('author', 'audit'):
            report['after'] = state(sequence, presentation, material)
            verify(report['after'], baseline['before'] if mode == 'audit' else report['before'])
            if mode == 'audit':
                assert normalized(report['after']) == baseline['after'], 'Cold asset state differs'
            else:
                assert set(helper.dirty()) <= set(OWNED), helper.dirty()
                for package in OWNED:
                    assert AS.save_asset(package, only_if_is_dirty=False), package
                    report['saved'].append(package)
                    persist()
        report['after_hashes'] = hashes()
        assert all(report['before_hashes'][p] == report['after_hashes'][p] for p in report['before_hashes'] if p not in report['saved'])
        assert all(report['before_hashes'][p] != report['after_hashes'][p] for p in report['saved'])
        assert not helper.dirty(), helper.dirty()
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        report['dirty'] = helper.dirty()
        raise
    finally:
        persist()
        print('CATRUN_PORTAL_FOLLOWUP', mode, report['completed'], str(output / 'report.json'))


command = u.SystemLibrary.get_command_line()
modes = re.findall(r'(?:^|\s)-catrunPortalFollowup(Probe|Author|Audit)(?=\s|$)', command, re.I)
baseline = re.search(r'-catrunPortalFollowupBaseline=(?:"([^"]+)"|(\S+))', command, re.I)
run(helper.only(modes).lower(), (baseline.group(1) or baseline.group(2)) if baseline else None)
