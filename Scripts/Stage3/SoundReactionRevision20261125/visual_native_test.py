"""Read-only ripple/GPU observer around the actual native release sound test.

Root launches this instead of native_test.py with the same env. No direct sound
emission, BP/material writes, camera changes, package saves or paid generation.
The inherited native test owns its existing disclosed settings/staging fixtures.
"""
import hashlib
import importlib.util
import json
import os
import traceback
from pathlib import Path
import unreal as u

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stage3_sound_native_visual_host', HERE / 'native_test.py')
native = importlib.util.module_from_spec(spec)
# Load definitions only. Editor graph tools reject calls while PIE is running,
# so graph inspection must precede the native module's one-time PIE bootstrap.
source = (HERE / 'native_test.py').read_text(encoding='utf8')
bootstrap_marker = "assert '-SaveToUserDir' in SL.get_command_line()"
assert source.count(bootstrap_marker) == 1, 'Review changed native test bootstrap before reuse'
exec(compile(source.split(bootstrap_marker, 1)[0], str(HERE / 'native_test.py'), 'exec'), native.__dict__)
OUT = native.OUT / 'Visual'
OUT.mkdir()
CAPTURE = os.environ.get('CATRUN_SOUND_VISUAL_CAPTURE', '1') == '1'
if CAPTURE:
    assert '-nullrhi' not in native.S['command_line'].lower(), 'GPU evidence requires a real renderer'
old_step, old_finish = native.step, native.finish
S = {'scope': __doc__, 'samples': [], 'shots': [], 'first_seen': {},
     'camera_changed': False, 'direct_emission_calls': 0, 'material_writes': 0,
     'capture_requested': CAPTURE, 'last_game_sample': -100., 'initialized': False}
ROOT = native.ROOT
PACKAGES = [ROOT / 'Content/Systems/Sound/Visual/Bluprints' / (name + '.uasset')
            for name in ('BP_CatrunSoundController', 'BP_CatrunRippleBurst', 'BP_CatrunRipple')]
PACKAGES.append(ROOT / 'Content/Systems/Sound/Visual/Matarial/M_CatrunRipple.uasset')
S['visual_package_hashes_before'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in PACKAGES}


def persist():
    (OUT / 'report.json').write_text(json.dumps(S, indent=2), encoding='utf8')


def inspect_graphs():
    """Read actual serialized graph links, not inferred binary string names."""
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    graphs = []
    for name in ('BP_CatrunSoundController', 'BP_CatrunRippleBurst', 'BP_CatrunRipple'):
        path = '/Game/Systems/Sound/Visual/Bluprints/' + name
        bp = u.EditorAssetLibrary.load_asset(path)
        assert bp, ('Pre-PIE Blueprint inspection could not load', path)
        row = {'package': path, 'status': str(bp.get_editor_property('status')), 'graphs': []}
        for graph in BP.list_graphs(bp):
            row['graphs'].append({'name': graph.get_name(), 'nodes': [
                {'node': info.node.get_name(), 'type': str(info.type_id),
                 'inputs': [{'name': str(p.name), 'value': str(p.value), 'links': str(p.connected_pins)}
                            for p in info.input_pins],
                 'outputs': [{'name': str(p.name), 'links': str(p.connected_pins)} for p in info.output_pins]}
                for info in BP.get_node_infos(BP.find_nodes(graph))]})
        graphs.append(row)
    (OUT / 'blueprint_graphs_readonly.json').write_text(json.dumps(graphs, indent=2), encoding='utf8')


def read_ripple(actor, game):
    mid = actor.get_editor_property('MID_Ripple')
    plane = actor.get_editor_property('WavePlane')
    snapshot = actor.get_editor_property('SoundSnapshot')
    texture = snapshot.get_editor_property('DistanceTexture')
    rect = snapshot.get_editor_property('GridRect')
    row = {'name': actor.get_name(), 'location': native.v(actor.get_actor_location()),
           'max_radius_cm': actor.get_editor_property('MaxRadiusCm'),
           'duration_s': actor.get_editor_property('RippleDuration'),
           'width_scale': actor.get_editor_property('WidthScale'),
           'mid': mid.get_path_name() if mid else None,
           'material_radius_cm': mid.get_scalar_parameter_value('Radius') if mid else None,
           'plane_location': native.v(plane.get_world_location()),
           'plane_scale': native.v(plane.get_world_scale()),
           'plane_visible': plane.is_visible() and not plane.get_editor_property('hidden_in_game'),
           'distance_texture': texture.get_path_name() if texture else None,
           'distance_texture_size': [texture.blueprint_get_size_x(), texture.blueprint_get_size_y()] if texture else None,
           'grid_rect_cm': [rect.r, rect.g, rect.b, rect.a],
           'cell_size_cm': snapshot.get_editor_property('CellSizeCm')}
    S['first_seen'].setdefault(actor.get_name(), game)
    row['observed_age_s'] = game - S['first_seen'][actor.get_name()]
    return row


def observe(world):
    game = native.GS.get_time_seconds(world)
    if not S['initialized']:
        if 'grid' not in native.LIVE:
            return
        S['settings'] = {key: str(native.LIVE['settings'].get_editor_property(key)) for key in
                         ('LargeBudget', 'SoundSpeed', 'RippleOpacity', 'RippleGlowStrength',
                          'RippleHeight', 'RippleLineHalfWidth', 'RippleGlowHalfWidth')}
        S['expected_budget_cm'] = native.S['effective_device_budget']
        S['expected_duration_s_if_budget_over_speed'] = (S['expected_budget_cm'] /
                                                        native.S['original']['SoundSpeed'])
        S['initialized'] = True
    if game - S['last_game_sample'] < .04:
        return
    S['last_game_sample'] = game
    actors = native.GS.get_all_actors_of_class(world, u.Actor)
    rows = [read_ripple(actor, game) for actor in actors
            if actor.get_class().get_name() == 'BP_CatrunRipple_C']
    committed = native.S.get('commit_game')
    origin = native.S.get('event_origin')
    relevant = [r for r in rows if committed is not None and
                abs(r['max_radius_cm'] - S['expected_budget_cm']) < .1 and
                origin is not None and (u.Vector(*r['location']) - u.Vector(*origin)).length() < 80.]
    camera = native.GS.get_player_camera_manager(world, 0)
    sample = {'game': game, 'since_commit_s': game - committed if committed is not None else None,
              'ripples': rows, 'device_ripple_names': [r['name'] for r in relevant],
              'camera_location': native.v(camera.get_camera_location()),
              'camera_rotation': str(camera.get_camera_rotation())}
    S['samples'].append(sample)
    # Trigger capture from the actual MID radius, not an assumed timeline clock.
    # This is the unchanged player/reveal camera; a large wave can extend offscreen.
    maximum = max((r['material_radius_cm'] or 0 for r in relevant), default=0.)
    for fraction in (.20, .55, .90):
        key = 'Radius%02d' % round(fraction * 100)
        if CAPTURE and not any(s['name'] == key for s in S['shots']) and maximum >= fraction * S['expected_budget_cm']:
            path = OUT / (key + '.png')
            native.SL.execute_console_command(world, 'HighResShot 1280x720 filename="' + str(path) + '"')
            S['shots'].append({'name': key, 'path': str(path), 'game': game,
                               'observed_mid_radius_cm': maximum, 'camera': sample['camera_location']})
            break  # One raster capture per observer tick.
    if relevant or committed is not None and game - committed < 5.:
        persist()


def step(world):
    old_step(world)
    if native.S['phase'] != 'shutdown':
        observe(world)


def finish(error=None):
    if not error:
        try:
            relevant = [r for s in S['samples'] for r in s['ripples'] if r['name'] in s['device_ripple_names']]
            native.check('Native device event spawns a ripple with its exact budget', bool(relevant),
                         {'expected_cm': S.get('expected_budget_cm'), 'sampled_ripples': len(relevant)})
            native.check('Device ripple owns captured distance texture and a visible plane',
                         bool(relevant) and all(r['distance_texture'] and r['plane_visible'] for r in relevant))
            peak = max((r['material_radius_cm'] or 0 for r in relevant), default=0.)
            S['maximum_sampled_material_radius_cm'] = peak
            native.check('Actual ripple material reaches at least ninety percent of device budget',
                         peak >= .90 * S.get('expected_budget_cm', float('inf')), peak)
            native.check('Device ripple duration scales with budget divided by sound speed', bool(relevant) and
                         all(abs(r['duration_s'] - S['expected_duration_s_if_budget_over_speed']) < .02 for r in relevant),
                         sorted(set(r['duration_s'] for r in relevant)))
            if CAPTURE:
                for shot in S['shots']:
                    shot['written'] = Path(shot['path']).is_file() and Path(shot['path']).stat().st_size > 1024
                native.check('GPU produced all three actual-view ripple captures', len(S['shots']) == 3
                             and all(s['written'] for s in S['shots']), S['shots'])
            after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in PACKAGES}
            S['visual_package_hashes_after'] = after
            native.check('Shared visual Blueprints and material bytes preserved', after == S['visual_package_hashes_before'])
        except Exception as exc:
            error = repr(exc)
    S['error'] = error
    S['limits'] = ['GPU files require root visual inspection; material radius alone is not proof of readable pixels.',
                   '1800/500=3.6 is maximum weighted propagation range, not 3.6 times onscreen pixel diameter.',
                   'Walls, corridors, floor costs and camera clipping affect the visible shape. No camera was changed.']
    persist()
    old_finish(error)


native.step, native.finish = step, finish

# Perform editor-only source inspection before any BeginPlay request. Runtime
# observations use only spawned objects; never call EditorAssetLibrary in PIE.
assert '-SaveToUserDir' in native.SL.get_command_line()
native.S['handle'] = u.register_slate_post_tick_callback(native.tick)
try:
    assert not native.ED.get_game_world(), 'Visual graph preflight requires PIE stopped'
    inspect_graphs()
    S['graphs_inspected_before_pie'] = True
    persist()
    assert native.LE.load_level('/Game/Maps/Stage3')
    native.LE.editor_request_begin_play()
except Exception:
    S['failure_category'] = 'read_only_visual_preflight_or_pie_bootstrap'
    finish(traceback.format_exc())
