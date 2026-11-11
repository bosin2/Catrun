"""Inspect and author the Stage2 exit in a fresh isolated Unreal commandlet.

Use -run=pythonscript -catrunStage2ExitIsolated with the four geometry CVars
set to zero. Set CATRUN_STAGE2_EXIT_MODE/PROOF/OUT in the launcher wrapper.
Probe reads saved maps, verify edits in memory, apply saves verified edits,
and audit reloads the result. Apply and audit consume the preceding report.
"""

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = Path(globals().get('CATRUN_STAGE2_EXIT_OUT') or ROOT / 'Saved/GameplayRepair20261111/Stage2Exit'
           / datetime.now().strftime('%H%M%S-%f')).resolve()
MODE = globals().get('CATRUN_STAGE2_EXIT_MODE', 'probe')
MAPS = ('Stage2', 'SoundTest_Stage2')
REFERENCE = ('Stage1', 'SoundTest_Stage1')
CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
         'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
PAWN = u.CollisionChannel.ECC_PAWN
NO_DEBUG = u.DrawDebugTrace.NONE
GATE = 'S2_Gate_00_Bars'
FRAME = 'S2_Gate_00_Frame'
EXIT = 'Flow_Stage2Complete'
THRESHOLD = 'SM_Stage2_Threshold_exit_Stone'
BASE = 'SM_Stage2_Threshold_exit_Base'
SOURCE_PREFIX = 'S1_MagicCorridor_'
PREFIX = 'S2_ExitCorridor_'
TAG = 'Stage2ExitCorridor'
SOLID = ('WallWest_1', 'WallWest_2', 'WallEast_1', 'WallEast_2', 'Ceiling',
         'CeilingUnderside', 'DarkEnd', 'WestOuterShade', 'EastOuterShade')
MIST = ('BlackMist_1', 'BlackMist_2', 'BlackMist_3')
VISUAL_ONLY = (*MIST, 'WestOuterShade', 'EastOuterShade')
PIECES = ('FloorBase', 'Floor_1', 'Floor_2') + SOLID + MIST
TRIGGER = (715., -80., 65.)
EXTENT = (65., 30., 80.)
GUARDS = ('WallWest_1', 'WallWest_2', 'WallEast_1', 'WallEast_2', 'DarkEnd')
PUZZLE_GATES = {'S2_Gate_02_Bars', 'S2_Gate_05_Bars', 'S2_Gate_11_Bars'}


def vec(v, axes='xyz'):
    return [round(float(getattr(v, axis)), 4) for axis in axes]


def rot(r):
    return [180. if abs(v) == 180. else v for v in
            (round(float(getattr(r, axis)), 4) for axis in ('pitch', 'yaw', 'roll'))]


def object_path(obj):
    return obj.get_path_name() if obj else None


def pose(a):
    return [vec(a.get_actor_location()), rot(a.get_actor_rotation()), vec(a.get_actor_scale3d())]


def tags(a):
    return [str(tag) for tag in a.tags]


def geometry(a):
    return [vec(v) for v in a.get_actor_bounds(False)]


def static_data(a):
    c = a.static_mesh_component
    return dict(pose=pose(a), bounds=geometry(a), mesh=object_path(c.get_editor_property('static_mesh')),
                materials=[object_path(c.get_material(i)) for i in range(c.get_num_materials())],
                profile=str(c.get_collision_profile_name()), collision=str(c.get_collision_enabled()),
                shadow=c.get_editor_property('cast_shadow'), tags=tags(a))


def exit_data(a):
    trigger = a.get_editor_property('Trigger')
    return dict(pose=pose(a), trigger=vec(trigger.get_world_location()), extent=vec(trigger.get_scaled_box_extent()),
                query=str(trigger.get_collision_enabled()), pawn=str(trigger.get_collision_response_to_channel(PAWN)),
                overlap=trigger.get_editor_property('generate_overlap_events'),
                center=a.get_editor_property('bRequireCenterInside'),
                presentation=a.get_editor_property('bUseExitTransition'),
                direction=vec(a.get_editor_property('InteriorDirectionLocal')),
                depth=a.get_editor_property('MinimumInteriorDepth'))


def snapshot(actors):
    result = {}
    for label, a in actors.items():
        row = dict(actor=a.get_name(), cls=object_path(a.get_class()), pose=pose(a), bounds=geometry(a),
                   parent=object_path(a.get_attach_parent_actor()), tags=tags(a), enabled=a.get_actor_enable_collision())
        if isinstance(a, u.StaticMeshActor):
            row.update(static_data(a))
        elif isinstance(a, u.CatrunHideBasket):
            row.update(direction=vec(a.get_editor_property('OpenDirectionLocal')),
                       body=object_path(a.get_editor_property('ExternalBody')),
                       cloth=object_path(a.get_editor_property('ExternalCloth')))
        elif isinstance(a, u.CatrunStatuePuzzle):
            row['links'] = [[str(link.get_editor_property('PuzzleId')),
                             *[object_path(link.get_editor_property(prop)) for prop in ('Gate', 'Plate', 'Statue')],
                             vec(link.get_editor_property('ContactHalfExtent'), 'xy'),
                             vec(link.get_editor_property('SocketAxis')), link.get_editor_property('GateFloorOffset')]
                            for link in a.get_editor_property('Links')]
        elif isinstance(a, u.CatrunStageExit):
            row.update(exit_data(a))
        result[label] = row
    return result


def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def data_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()


def content_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'Content').rglob('*'))
            if p.suffix in ('.umap', '.uasset')}


def dirty():
    utils = u.EditorLoadingAndSavingUtils
    return {p.get_name() for p in [*utils.get_dirty_map_packages(), *utils.get_dirty_content_packages()]}


def actors_by_label():
    actors = ACTORS.get_all_level_actors()
    result = {a.get_actor_label(): a for a in actors}
    assert len(actors) == len(result), 'Duplicate actor label in map'
    return result


def load_map(name):
    assert not dirty() and LEVEL.load_level('/Game/Maps/'+name), (name, dirty())
    world = ED.get_editor_world()
    assert object_path(world) == f'/Game/Maps/{name}.{name}', object_path(world)
    return world, actors_by_label()


def get_grid(manager):
    return json.loads(manager.call_method('ExportBakedGridSnapshot'))


def check_grid(before, after):
    size = before['CellSize']
    ox, oy, oz = before['Origin']
    nx, ny, nz = after['Origin']
    rows = round((oy-ny)/size)
    assert (nx, nz, after['CellSize'], after['Width'], after['WallProbeLength']) == (
        ox, oz, size, before['Width'], before['WallProbeLength'])
    assert ny == math.floor(-415./size)*size and rows > 0 and abs(ny+rows*size-oy) < .001
    assert after['Height'] == before['Height']+rows
    width = before['Width']
    added = rows*width
    for key in ('Walkable', 'CostMultiplier'):
        assert after[key][added:] == before[key], ('Existing floor grid changed', key)
    changes = {'new_walkable': 0, 'edges': [], 'clearance': []}
    for i in range(added):
        x, y = nx + (i % width+.5)*size, ny + (i // width+.5)*size
        expected = 615. <= x <= 815. and -415. <= y <= -15.
        assert bool(after['Walkable'][i]) == expected, ('Unexpected exterior floor cell', x, y)
        changes['new_walkable'] += int(expected)
    assert changes['new_walkable'] > 0
    reach = before['WallProbeLength']
    for i, old_edge in enumerate(before['EdgeMask']):
        x, y = ox + (i % width+.5)*size, oy + (i // width+.5)*size
        new_edge = after['EdgeMask'][i+added]
        if old_edge != new_edge:
            assert old_edge & ~new_edge == 0 and 615.-size <= x <= 815.+size and abs(y) <= 2.*size, (
                'Existing edge closed or distant edge changed', x, y, old_edge, new_edge)
            changes['edges'].append([x, y, old_edge, new_edge])
        old_dist, new_dist = before['WallDistance'][i], after['WallDistance'][i+added]
        if abs(old_dist-new_dist) > .001:
            assert 585.-reach <= x <= 845.+reach and abs(y) <= reach+15., (
                'Distant armor clearance changed', x, y, old_dist, new_dist)
            changes['clearance'].append([x, y, old_dist, new_dist])
    middle = int((715.-nx)//size)
    inside_row = int((20.-ny)//size)
    outside_row = int((-380.-ny)//size)
    # Along the centerline, every row toward the end must connect north/south.
    for row in range(outside_row, inside_row):
        outer, inner = row*width+middle, (row+1)*width+middle
        assert after['EdgeMask'][outer] & 4 and after['EdgeMask'][inner] & 8, ('Grid corridor disconnected', row)
    return changes


def hit_data(hit):
    if not hit:
        return None
    data = hit.to_dict()
    return dict(actor=data['hit_actor'].get_actor_label() if data['hit_actor'] else None,
                point=vec(data['impact_point']), normal=vec(data['impact_normal']),
                blocking=data['blocking_hit'], initial_overlap=data['initial_overlap'])


def sweep(world, cat, start, end, ignored=()):
    cap = cat.get_component_by_class(u.CapsuleComponent)
    return hit_data(u.SystemLibrary.capsule_trace_single_by_profile(
        world, u.Vector(*start), u.Vector(*end), cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(),
        cap.get_collision_profile_name(), False, [cat, *ignored], NO_DEBUG, False))


def start_checks(world, actors, cat):
    bars, exit_actor = actors[GATE], actors[EXIT]
    assert isinstance(bars, u.StaticMeshActor) and isinstance(actors[FRAME], u.StaticMeshActor)
    assert isinstance(exit_actor, u.CatrunStageExit) and not exit_data(exit_actor)['presentation']
    puzzle, = [a for a in actors.values() if isinstance(a, u.CatrunStatuePuzzle)]
    assert {link.get_editor_property('Gate').get_actor_label() for link in puzzle.get_editor_property('Links')} == PUZZLE_GATES
    assert pose(bars)[0] == [715., 0., 0.] and 'SoundWall' in tags(bars)
    assert pose(exit_actor)[0] == [715., 70., 65.] and exit_data(exit_actor)['extent'] == list(EXTENT)
    assert not any(label.startswith(PREFIX) for label in actors)
    z = cat.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height()+2.
    blocked = sweep(world, cat, (715., 110., z), (715., -12., z))
    assert blocked and blocked['actor'] == GATE, blocked
    assert not sweep(world, cat, (715., 110., z), (715., -12., z), [bars]), 'Frame blocks open exit'
    return blocked


def create_piece(suffix, source, location, scale=None, extra_tags=()):
    pitch, yaw, roll = source['pose'][1]
    a = ACTORS.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*location), u.Rotator(pitch=pitch, yaw=yaw, roll=roll))
    assert a, suffix
    a.set_actor_label(PREFIX+suffix)
    a.set_folder_path('Environment/Stage2/ExitCorridor')
    a.set_editor_property('tags', [u.Name(name) for name in (TAG, *extra_tags)])
    c = a.static_mesh_component
    mesh = u.load_object(None, source['mesh'])
    assert mesh, source['mesh']
    c.set_static_mesh(mesh)
    c.set_mobility(u.ComponentMobility.STATIC)
    a.set_actor_scale3d(u.Vector(*(scale or source['pose'][2])))
    c.set_collision_profile_name('NoCollision' if suffix in VISUAL_ONLY else source['profile'])
    c.set_cast_shadow(source['shadow'])
    for i, path in enumerate(source['materials']):
        if path:
            material = u.load_object(None, path)
            assert material, path
            c.set_material(i, material)
    return a


def author(actors, reference):
    bars = actors[GATE]
    bars.modify()
    bars.static_mesh_component.modify()
    bars.static_mesh_component.set_collision_profile_name('NoCollision')
    bars.set_actor_location(u.Vector(715., 0., -261.), False, True)
    bars.set_editor_property('tags', [u.Name(tag) for tag in tags(bars) if tag != 'SoundWall'])
    exit_actor = actors[EXIT]
    exit_actor.modify()
    exit_actor.get_editor_property('Trigger').modify()
    exit_actor.set_actor_location(u.Vector(*TRIGGER), False, True)
    exit_actor.set_editor_property('bRequireCenterInside', True)
    floor, base = static_data(actors[THRESHOLD]), static_data(actors[BASE])
    create_piece('FloorBase', base, (715., -215., -12.5), (2.6, 4., .15))
    create_piece('Floor_1', floor, (615., -15., -5.), (1., 1., 1.), ('SoundFloor',))
    create_piece('Floor_2', floor, (615., -215., -5.), (1., 1., 1.), ('SoundFloor',))
    for suffix in SOLID+MIST:
        source = reference[suffix]
        x, y, z = source['pose'][0]
        create_piece(suffix, source, (x+615., y, z+.9), extra_tags=('SoundWall',) if suffix in GUARDS else ())


def check_saved_geometry(world, actors, cat):
    authored = {a.get_actor_label().removeprefix(PREFIX): a for a in actors.values() if TAG in tags(a)}
    assert set(authored) == set(PIECES) and all(a.get_actor_label() == PREFIX+key for key, a in authored.items())
    for key, a in authored.items():
        expected = 'NoCollision' if key in VISUAL_ONLY else 'BlockAll'
        assert str(a.static_mesh_component.get_collision_profile_name()) == expected, key
        assert ('SoundFloor' in tags(a)) == (key in ('Floor_1', 'Floor_2')), key
        assert ('SoundWall' in tags(a)) == (key in GUARDS), key
    bars = static_data(actors[GATE])
    assert bars['pose'][0] == [715., 0., -261.] and bars['profile'] == 'NoCollision' and 'SoundWall' not in bars['tags']
    assert bars['bounds'][0][2]+bars['bounds'][1][2] < -5., bars
    trigger = exit_data(actors[EXIT])
    assert trigger['trigger'] == list(TRIGGER) and trigger['extent'] == list(EXTENT)
    assert trigger['center'] and not trigger['presentation'] and trigger['overlap']
    assert 'QUERY_ONLY' in trigger['query'] and 'OVERLAP' in trigger['pawn']
    assert trigger['direction'] == [0., 0., 0.] and trigger['depth'] == 0.
    cap = cat.get_component_by_class(u.CapsuleComponent)
    assert str(cap.get_collision_profile_name()) == 'Pawn'
    half = cap.get_scaled_capsule_half_height()
    z = half+2.
    checks = {'floor': [], 'guards': [], 'lanes': []}
    for x in (675., 715., 755.):
        assert not sweep(world, cat, (x, 120., z), (x, -387., z)), ('Exit lane blocked', x)
        checks['lanes'].append(x)
        for y in (120., 35., 5., 0., -5., -14., -15., -16., -50., -80., -110., -180., -214.,
                  -215., -216., -300., -387., -392.):
            support = sweep(world, cat, (x, y, half+12.), (x, y, half-8.))
            assert support and support['blocking'] and not support['initial_overlap'] and support['normal'][2] > .65 \
                and abs(support['point'][2]) <= .05, ('Exit floor unsupported', x, y, support)
            checks['floor'].append([x, y, support])
    for y in (-35., -45., -115., -215., -315., -387.):
        for x, side in ((550., 'WallWest_'), (880., 'WallEast_')):
            guard = sweep(world, cat, (715., y, z), (x, y, z))
            # The 20 cm radius can touch the retained frame at the entrance seam.
            assert guard and (guard['actor'].startswith(PREFIX+side) or (y == -35. and guard['actor'] == FRAME)), (
                'Unprotected corridor side', x, y, guard)
            checks['guards'].append(guard)
    end = sweep(world, cat, (715., -387., z), (715., -460., z))
    assert end and end['actor'] == PREFIX+'DarkEnd', ('Unprotected corridor end', end)
    checks['guards'].append(end)
    return checks


def compare_actors(before, after):
    assert after.keys()-before.keys() == {PREFIX+key for key in PIECES} and not before.keys()-after.keys()
    assert {label for label in before if before[label] != after[label]} == {GATE, EXIT}, 'Unrelated actor changed'


def main(report):
    command = u.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and '-catrunstage2exitisolated' in command
    assert MODE in ('probe', 'verify', 'apply', 'audit') and not ED.get_game_world() and not dirty()
    report['cvars'] = {name: u.SystemLibrary.get_console_variable_int_value(name) for name in CVARS}
    assert all(value == 0 for value in report['cvars'].values()), report['cvars']
    report['content_before'] = content_hashes()
    proof = None
    if MODE in ('apply', 'audit'):
        proof_path = Path(globals()['CATRUN_STAGE2_EXIT_PROOF']).resolve()
        proof = json.loads(proof_path.read_text(encoding='utf-8'))
        assert proof['completed'] and proof['mode'] == ('verify' if MODE == 'apply' else 'apply')
        assert proof['pid'] != report['pid'] and proof['script_sha256'] == report['script_sha256']
        assert proof['content_after'] == report['content_before'], 'Content changed after proof'
        report['proof'] = str(proof_path)
    for name in REFERENCE:
        _, actors = load_map(name)
        report['reference'][name] = {key: static_data(actors[SOURCE_PREFIX+key]) for key in PIECES}
        assert not dirty(), (name, dirty())
    assert report['reference'][REFERENCE[0]] == report['reference'][REFERENCE[1]], 'Stage1 reference mirrors differ'
    if MODE == 'apply':
        for name in MAPS:
            rel = f'Content/Maps/{name}.umap'
            backup = OUT/'Before'/rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/rel, backup)
            assert sha(backup) == report['content_before'][rel], name
            report['backups'][name] = str(backup)
    for name in MAPS:
        world, actors = load_map(name)
        cat, = [a for a in actors.values() if a.get_class().get_name() == 'BP_Cat_C']
        manager, = [a for a in actors.values() if isinstance(a, u.SoundGridManager)]
        row = report['maps'][name] = {'world': object_path(world), 'actors_before': snapshot(actors)}
        saved_grid = get_grid(manager)
        row['grid_before'] = saved_grid
        assert manager.has_grid()
        if MODE == 'audit':
            expected = proof['maps'][name]
            assert row['actors_before'] == expected['actors_after'], ('Saved actor state changed', name)
            assert data_hash(saved_grid) == expected['grid_after_sha256'], ('Saved grid changed', name)
            row['grid_changes'] = check_grid(expected['grid_before'], saved_grid)
            row['checks'] = check_saved_geometry(world, actors, cat)
        else:
            row['closed_gate_hit'] = start_checks(world, actors, cat)
            if MODE != 'probe':
                manager.build_grid()
                assert get_grid(manager) == saved_grid, ('Preexisting Stage2 grid drift', name)
                author(actors, report['reference'][REFERENCE[0]])
                manager.build_grid()
                after_grid = get_grid(manager)
                row['grid_after_sha256'] = data_hash(after_grid)
                row['grid_changes'] = check_grid(saved_grid, after_grid)
                actors = actors_by_label()
                row['actors_after'] = snapshot(actors)
                compare_actors(row['actors_before'], row['actors_after'])
                row['checks'] = check_saved_geometry(world, actors, cat)
                assert dirty() <= {'/Game/Maps/'+name}, (name, dirty())
                if MODE == 'apply':
                    expected = proof['maps'][name]
                    for key in ('actors_before', 'grid_before', 'actors_after', 'grid_after_sha256'):
                        assert row[key] == expected[key], ('Apply differs from verify', name, key)
                    assert LEVEL.save_current_level(), name
                else:
                    u.EditorLoadingAndSavingUtils.new_blank_map(False)
        assert not dirty(), (name, dirty())
        print('CATRUN_STAGE2_EXIT_'+MODE.upper(), name)
    report['content_after'] = content_hashes()
    before, after = report['content_before'], report['content_after']
    assert before.keys() == after.keys(), 'Unexpected content addition or deletion'
    report['changed_files'] = sorted(key for key in before if before[key] != after[key])
    expected_files = {f'Content/Maps/{name}.umap' for name in MAPS} if MODE == 'apply' else set()
    assert set(report['changed_files']) == expected_files, report['changed_files']


report = dict(mode=MODE, pid=os.getpid(), script_sha256=sha(ROOT/'Scripts/GameplayRepair/repair_stage2_exit.py'),
              completed=False, reference={}, maps={}, backups={})
OUT.mkdir(parents=True, exist_ok=True)
try:
    main(report)
    report['completed'] = True
except Exception:
    report['error'] = traceback.format_exc()
finally:
    report_path = OUT/'report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CATRUN_STAGE2_EXIT_REPORT', str(report_path), report['completed'])
if not report['completed']:
    raise RuntimeError(report['error'])
