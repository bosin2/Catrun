"""Inert root-only Stage3 reveal pacing preparation; no package saves.

Stage2's cold native QA reports Travel=3, Return=2.6, MaximumLock=10.5.
Only those three instance fields are changed here. Native MaximumLockTime is
an overall session watchdog, clamped to [1,15], not time dilation or gate speed.
"""
import hashlib
from pathlib import Path
import unreal as u

TARGET = {'CameraTravelTime': 3., 'CameraReturnTime': 2.6, 'MaximumLockTime': 10.5}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tuning(reveal):
    return {k: float(reveal.get_editor_property(k)) for k in TARGET}


def protected_scene(world, puzzle, reveal):
    actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
    rows = {a.get_path_name(): {'transform': a.get_actor_transform().export_text(),
            'collision': a.get_actor_enable_collision(), 'class': a.get_class().get_path_name()}
            for a in actors}
    cards = {}
    for a in actors:
        if a.get_actor_label() in ('S3_GateImpact_D1', 'S3_GateImpact_D2'):
            for i in range(8):
                c = a.get_editor_property('Dust%02d' % i)
                cards[c.get_path_name()] = {'transform': c.get_world_transform().export_text(),
                    'material': c.get_material(0).get_path_name(), 'hidden': c.get_editor_property('hidden_in_game'),
                    'collision': str(c.get_collision_enabled())}
    return {'actors': rows, 'cards': cards,
            'offset': reveal.get_editor_property('GateCameraOffset').export_text(),
            'preserve_framing': reveal.get_editor_property('bPreserveGameplayFraming'),
            'enabled': reveal.get_editor_property('bEnabled'),
            'links': [link.export_text() for link in puzzle.get_editor_property('Links')],
            'settings': puzzle.get_editor_property('Settings').get_path_name() if puzzle.get_editor_property('Settings') else None}


def prepare():
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Root isolated editor only'
    world = ed.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    puzzle, = [a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
               if a.get_actor_label() == 'S3_StatuePuzzles']
    reveal = puzzle.get_editor_property('Reveal')
    settings = puzzle.get_editor_property('Settings') or u.get_default_object(u.CatrunStatuePuzzleSettings.static_class())
    gate_speed = float(settings.get_editor_property('GateSpeed'))
    durations = []
    for link in puzzle.get_editor_property('Links'):
        gate = link.get_editor_property('Gate')
        _, extent = gate.get_actor_bounds(False, False)
        travel = max(float(settings.get_editor_property('GateTravel')),
                     2*extent.z - float(link.get_editor_property('GateFloorOffset'))
                     + max(.1, float(settings.get_editor_property('GateFloorClearance'))))
        session = TARGET['CameraTravelTime'] + travel/max(1., gate_speed) + TARGET['CameraReturnTime']
        assert TARGET['MaximumLockTime'] - session >= 1., 'Insufficient watchdog headroom'
        durations.append({'puzzle': str(link.get_editor_property('PuzzleId')), 'travel_cm': travel,
                          'gate_speed_cm_s': gate_speed, 'expected_descent_s': travel/max(1., gate_speed),
                          'expected_session_s': session, 'watchdog_headroom_s': TARGET['MaximumLockTime']-session})
    root = Path(u.Paths.project_dir()).resolve()
    paths = [root/'Content/Maps'/(n+'.umap') for n in ('Stage1','Stage2','Stage3')]
    paths += list((root/'Content/Environment/Stage3/GateFX_20261125').rglob('*.uasset'))
    hashes = {str(p): sha(p) for p in paths}
    original = protected_scene(world, puzzle, reveal)
    before = tuning(reveal)
    for key, value in TARGET.items():
        reveal.set_editor_property(key, value)
    after = tuning(reveal)
    assert all(abs(after[k]-v) < 1e-5 for k,v in TARGET.items())
    assert protected_scene(world, puzzle, reveal) == original, 'Non-timing scene data changed'
    assert all(sha(p) == h for p,h in hashes.items()), 'Protected disk package changed'
    return {'success': True, 'before': before, 'after': after, 'records': durations,
            'protected_scene_equal': True, 'protected_sha256': hashes,
            'offset_preserved': original['offset'], 'framing_preserved': original['preserve_framing'],
            'asset_save_paths': [], 'map_save_path': '/Game/Maps/Stage3', 'save_list': ['/Game/Maps/Stage3'],
            'packages_saved': False, 'native_watchdog_clamp_s': [1.,15.],
            'scope': 'Three reveal timing fields only; no pan path, camera rotation, gate speed, material or gameplay edits'}

