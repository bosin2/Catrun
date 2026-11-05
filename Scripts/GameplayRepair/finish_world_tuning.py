"""Bounded Task5 saved-world author/audit; root alone launches this commandlet.

Author: -run=pythonscript -catrunWorldAuthor -catrunGeometryIsolated
Audit (new process): same script, -catrunWorldAuditOnly -catrunGeometryIsolated
                    -catrunWorldBaseline=<absolute author report.json>
Both require the four process CVars documented in task-5-world-report.md.
No PIE, tick, rendering, input, sequence/intro/portal graph edits, or native tests.
"""
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayRepair20261105/WorldTuning' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(parents=True, exist_ok=False)
COMMAND = unreal.SystemLibrary.get_command_line()
AUDIT = '-catrunworldauditonly' in COMMAND.lower()
MAPS = tuple('/Game/Maps/' + n for n in (
    'Tutorial', 'SoundTest_Tutorial', 'Stage1', 'SoundTest_Stage1', 'Stage2', 'SoundTest_Stage2'))
ARMOR_BP = '/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor'
TARGET_RATE = 3.333333
LIFT = 2.25
HOMES = ((1180., 1540., 0., 90.), (1590., 2100., 0., -90.), (2590., 1650., 0., 180.))
OFFSETS = ((140., 0.), (0., 140.), (0., 140.))
PATROL = {'patrol_enabled': True, 'patrol_speed': 65., 'patrol_pause_seconds': 1.5, 'patrol_loop': False}
CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
         'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')
CHANNELS = tuple(getattr(unreal.CollisionChannel, n) for n in (
    'ECC_WORLD_STATIC', 'ECC_WORLD_DYNAMIC', 'ECC_PAWN', 'ECC_PHYSICS_BODY', 'ECC_VEHICLE', 'ECC_DESTRUCTIBLE'))
OBJECTS = [getattr(unreal.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
BLOCK = unreal.CollisionResponseType.ECR_BLOCK
PAWN = unreal.CollisionChannel.ECC_PAWN
NONE = unreal.DrawDebugTrace.NONE
ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
AS = unreal.EditorAssetLibrary
REPORT = {'audit_only': AUDIT, 'process_id': os.getpid(), 'completed': False,
          'runtime_or_visual_verified': False, 'maps': {}, 'backups': [], 'saved': [], 'errors': [], 'query_count': 0,
          'scope': list(MAPS) + [ARMOR_BP], 'limits': ['Saved geometry only; no gameplay or dynamic puzzle states',
          'Nine-point support sampled every <=20cm, not continuous analytic support',
          'Tutorial grid remains single plane; tagging does not add multi-height sound propagation']}


def persist():
    (OUT / 'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def checkpoint(phase, **data):
    REPORT['phase'] = phase
    REPORT.update(data)
    persist()


def v(p):
    return [float(p.x), float(p.y), float(p.z)]


def path(o):
    return o.get_path_name() if o else None


def transform(t):
    q = t.rotation
    rot = [float(q.x), float(q.y), float(q.z), float(q.w)]
    sign = next((1 if x > 0 else -1 for x in reversed(rot) if abs(x) > 1.e-12), 1)
    return {'translation': v(t.translation), 'rotation_xyzw': [sign * x for x in rot], 'scale': v(t.scale3d)}


def diff(actual, expected, prefix=''):
    if isinstance(actual, dict) and isinstance(expected, dict):
        rows = []
        for key in sorted(set(actual) | set(expected)):
            if key not in actual or key not in expected:
                rows.append({'path': prefix+'/'+key, 'actual': actual.get(key), 'expected': expected.get(key)})
            else:
                rows += diff(actual[key], expected[key], prefix+'/'+key)
        return rows
    if isinstance(actual, list) and isinstance(expected, list) and len(actual) == len(expected):
        return [d for i, (a, e) in enumerate(zip(actual, expected)) for d in diff(a, e, prefix+'/'+str(i))]
    equal = (math.isclose(actual, expected, rel_tol=1.e-7, abs_tol=1.e-4)
             if type(actual) in (int, float) and type(expected) in (int, float) else actual == expected)
    return [] if equal else [{'path': prefix, 'actual': actual, 'expected': expected}]


def equal(actual, expected):
    return not diff(actual, expected)


def dirty():
    return [p.get_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
            + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())]


def clean():
    assert not ED.get_game_world(), 'User PIE/game world: stop without changing assets'
    assert not dirty(), ('Unexpected dirty packages; no auto-save', dirty())


def file_for(package):
    assert package.startswith('/Game/')
    return ROOT / ('Content/' + package[6:] + ('.umap' if package in MAPS else '.uasset'))


def digest(filename):
    return hashlib.sha256(filename.read_bytes()).hexdigest()


def asset_hashes():
    return {p: digest(file_for(p)) for p in REPORT['scope']}


def protected_hashes():
    # No cinematic/intro/key-hint/shared settings/animation/camera/UI asset may be saved.
    owned = {file_for(p).resolve() for p in REPORT['scope']}
    directories = ('Content/Cinematics', 'Content/UI', 'Content/Systems/Sound',
                   'Content/Characters/LivingArmor', 'Content/Systems/Interaction/Puzzles/Presentation')
    files = set()
    for folder in directories:
        files.update((ROOT / folder).rglob('*.uasset'))
    files.update((ROOT / 'Content').rglob('*TutorialIntro*.uasset'))
    return {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in sorted(files) if p.resolve() not in owned}


def refs(obj):
    """Read actual reflected object-reference attributes; no guessed BP properties."""
    result = {}
    for name in dir(obj):
        if name.startswith('_'):
            continue
        try:
            value = getattr(obj, name)
            if isinstance(value, unreal.Object):
                result[name] = path(value)
            elif isinstance(value, unreal.Array) and value and all(isinstance(i, unreal.Object) or i is None for i in value):
                result[name] = [path(i) for i in value]
        except Exception as error:
            # Unreal's Python descriptor raises plain Exception for protected
            # editor-only fields. Preserve that limitation in the snapshot.
            result['unreadable:' + name] = type(error).__name__
            continue
    return result


def component(c):
    row = {'class': path(c.get_class()), 'references': refs(c)}
    if isinstance(c, unreal.SceneComponent):
        row.update(relative={'translation': v(c.get_editor_property('relative_location')),
                             'rotation_pyr': [float(getattr(c.get_editor_property('relative_rotation'), n))
                                              for n in ('pitch', 'yaw', 'roll')],
                             'scale': v(c.get_editor_property('relative_scale3d'))},
                   world=transform(c.get_world_transform()), parent=path(c.get_attach_parent()))
    if isinstance(c, unreal.PrimitiveComponent):
        row.update(collision_enabled=str(c.get_collision_enabled()), profile=str(c.get_collision_profile_name()),
                   object_type=str(c.get_collision_object_type()),
                   responses={str(ch): str(c.get_collision_response_to_channel(ch)) for ch in CHANNELS})
    if isinstance(c, unreal.CapsuleComponent):
        row.update(radius=float(c.get_scaled_capsule_radius()), half_height=float(c.get_scaled_capsule_half_height()))
    if isinstance(c, unreal.CameraComponent):
        row['camera'] = {name: str(c.get_editor_property(name)) if name == 'projection_mode'
                         else float(c.get_editor_property(name)) for name in
                         ('projection_mode', 'ortho_width', 'field_of_view', 'aspect_ratio')}
    if isinstance(c, unreal.SpringArmComponent):
        row['arm'] = {'length': float(c.get_editor_property('target_arm_length')),
                      'socket_offset': v(c.get_editor_property('socket_offset')),
                      'target_offset': v(c.get_editor_property('target_offset'))}
    if isinstance(c, unreal.CatrunPuzzleRevealComponent):
        row['reveal'] = {name: c.get_editor_property(name) for name in
                         ('bPreserveGameplayFraming', 'CameraTravelTime', 'CameraReturnTime', 'MaximumLockTime')}
        row['reveal']['GateCameraOffset'] = v(c.get_editor_property('GateCameraOffset'))
    return row


def grid_arrays(manager):
    # Direct read-only native export: private baked data stays encapsulated.
    g = json.loads(manager.call_method('ExportBakedGridSnapshot'))
    required = {'Origin', 'CellSize', 'Width', 'Height', 'Walkable', 'CostMultiplier', 'EdgeMask', 'WallDistance', 'WallProbeLength'}
    assert set(g) == required, ('Unexpected baked grid schema', sorted(g))
    g['Origin'] = unreal.Vector(*g['Origin'])
    return g


def grid_summary(manager):
    g = grid_arrays(manager)
    encoded = {'origin': v(g['Origin']), 'cell_size': float(g['CellSize']), 'width': int(g['Width']),
               'height': int(g['Height']), 'walkable': list(g['Walkable']), 'cost': list(g['CostMultiplier']),
               'edge_mask': list(g['EdgeMask']), 'wall_distance': list(g['WallDistance']),
               'wall_probe_length': float(g['WallProbeLength'])}
    return {'sha256': hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest(),
            'origin': encoded['origin'], 'cell_size': encoded['cell_size'], 'width': encoded['width'],
            'height': encoded['height'], 'walkable_count': sum(bool(i) for i in encoded['walkable'])}


def snapshot(world):
    result = {'actors': {}}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        row = {'class': path(a.get_class()), 'label': a.get_actor_label(), 'transform': transform(a.get_actor_transform()),
               'tags': [str(t) for t in a.tags], 'references': refs(a),
               'components': {c.get_name(): component(c) for c in a.get_components_by_class(unreal.ActorComponent)}}
        if isinstance(a, unreal.CatrunArmor):
            row['turn_play_rate'] = float(a.get_editor_property('turn_play_rate'))
        if isinstance(a, unreal.CatrunHideBasket):
            row['open_direction_local'] = v(a.get_editor_property('open_direction_local'))
        if isinstance(a, unreal.CatrunDoor):
            row['door_open'] = bool(a.is_open())
        if isinstance(a, unreal.CatrunCandle):
            row['patrol'] = {k: a.get_editor_property(k) for k in PATROL}
            row['patrol']['patrol_points'] = [path(p) for p in a.get_editor_property('patrol_points')]
            row['patrol']['patrol_relative_points'] = [v(p) for p in a.get_editor_property('patrol_relative_points')]
        if isinstance(a, unreal.SoundGridManager):
            row['grid'] = grid_summary(a)
            row['bell_budget'] = float(a.get_editor_property('player_bell_budget_override'))
            row['settings'] = path(a.get_editor_property('Settings'))
        if a.get_class().get_name() == 'BP_StatuePresentation_C':
            row['presentation'] = {name: float(a.get_editor_property(name)) for name in
                                    ('RumbleStrength', 'BarHeight', 'RevealOrthoWidth')}
            row['presentation']['CameraOffset'] = v(a.get_editor_property('CameraOffset'))
        result['actors'][a.get_name()] = row
    return result


def count():
    REPORT['query_count'] += 1
    assert REPORT['query_count'] <= 12000, 'Bounded geometry query budget exceeded'


def hit_data(hit):
    if not hit:
        return None
    result = {}
    for k, val in hit.to_dict().items():
        if isinstance(val, unreal.Vector):
            result[k] = v(val)
        elif isinstance(val, unreal.Object):
            result[k] = path(val)
        elif val is None or isinstance(val, (str, int, float, bool)):
            result[k] = val
        else:
            result[k] = str(val)  # Names/enums only; no transform/rotator repr comparisons.
    return result


def line(world, start, end, ignore):
    count()
    return unreal.SystemLibrary.line_trace_single_by_profile(world, start, end, 'Pawn', False, ignore, NONE, False)


def floor(world, at, ignore):
    return line(world, at+unreal.Vector(0, 0, 30), at-unreal.Vector(0, 0, 140), ignore)


def endpoint(world, at, cap, ignore):
    count()
    overlaps = unreal.SystemLibrary.capsule_overlap_components(world, at, cap.get_scaled_capsule_radius(),
        cap.get_scaled_capsule_half_height(), OBJECTS, unreal.PrimitiveComponent, ignore) or []
    return [path(c) for c in overlaps if c.get_collision_response_to_channel(PAWN) == BLOCK
            and cap.get_collision_response_to_channel(c.get_collision_object_type()) == BLOCK]


def route_geometry(world, actor, cap, centers):
    calibration = floor(world, centers[0], [actor])
    assert calibration and calibration.to_dict()['impact_normal'].z >= .65, 'UNINITIALIZED_OR_UNCALIBRATED_NO_CLEARANCE_CLAIMS'
    assert abs(calibration.to_dict()['impact_point'].z) <= .05, 'Stage2 floor changed from calibrated Z0; refuse stale route assumption'
    rows = []
    for start, end in zip(centers, centers[1:]):
        count()
        sweep = unreal.SystemLibrary.capsule_trace_single_by_profile(world, start, end, cap.get_scaled_capsule_radius(),
            cap.get_scaled_capsule_half_height(), 'Pawn', False, [actor], NONE, False)
        row = {'start': v(start), 'end': v(end), 'sweep': hit_data(sweep), 'endpoint_blockers': endpoint(world, end, cap, [actor]), 'samples': []}
        samples = int(math.ceil(math.sqrt((end.x-start.x)**2+(end.y-start.y)**2)/20.))
        for i in range(samples+1):
            at = start + (end-start)*(i/float(samples))
            bottom = at.z-cap.get_scaled_capsule_half_height()
            rays = []
            for j in range(9):
                radius = 0. if j == 0 else cap.get_scaled_capsule_radius()
                angle = (j-1)*math.pi/4
                p = unreal.Vector(at.x+radius*math.cos(angle), at.y+radius*math.sin(angle), bottom)
                h = floor(world, p, [actor])
                d = h.to_dict() if h else None
                gap = bottom-d['impact_point'].z if d else None
                ok = bool(d and d['impact_normal'].z >= .65 and -.25 <= gap <= 8.)
                rays.append({'hit': hit_data(h), 'gap': gap, 'supported': ok})
            row['samples'].append({'center': v(at), 'footprint': rays, 'supported': all(r['supported'] for r in rays)})
        row['clear'] = not row['sweep'] and not row['endpoint_blockers'] and all(s['supported'] for s in row['samples'])
        rows.append(row)
    return {'calibration': hit_data(calibration), 'legs': rows, 'clear': all(r['clear'] for r in rows)}


def candle_plan(world, by, verify=False):
    actors = [a for a in by.values() if isinstance(a, unreal.CatrunCandle)]
    assert {a.get_name() for a in actors} == {'BP_Candle_C_'+str(i) for i in range(3)}, 'Unexpected Stage2 candle scope'
    plans = {}
    for i, (x, y, z, yaw) in enumerate(HOMES):
        a = by['BP_Candle_C_'+str(i)]
        assert equal(v(a.get_actor_location()), [x, y, z])
        rot = a.get_actor_rotation()
        assert equal([rot.pitch, rot.yaw, rot.roll], [0., yaw, 0.]) and equal(v(a.get_actor_scale3d()), [1., 1., 1.])
        cap = a.get_editor_property('blocking_capsule')
        body = a.get_editor_property('Body')
        assert cap and cap.get_attach_parent() == a.root_component
        assert body.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
        assert equal([cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()], [22., 60.])
        assert str(cap.get_collision_profile_name()) == 'Pawn'
        assert all(cap.get_collision_response_to_channel(ch) == BLOCK for ch in CHANNELS), 'Profile sweep must match actual capsule responses'
        assert equal(transform(cap.get_world_transform())['rotation_xyzw'], transform(a.get_actor_transform())['rotation_xyzw'])
        current = v(cap.get_editor_property('relative_location'))
        assert equal(current, [0., 0., 60.]) or equal(current, [0., 0., 62.25]), ('Unexpected capsule offset', current)
        # Equivalent collision-query centers to old proposal: whole actor +2.25,
        # original capsule relativeZ60. Actor/Body/sight never move in this writer.
        home = a.get_actor_transform().transform_location(unreal.Vector(0, 0, 60)) + unreal.Vector(0, 0, LIFT)
        target_relative = a.root_component.get_world_transform().inverse_transform_location(home)
        dx, dy = OFFSETS[i]
        world_points = [unreal.Vector(x, y, z), unreal.Vector(x+dx, y+dy, z), unreal.Vector(x-dx, y-dy, z)]
        relative = [a.get_actor_transform().inverse_transform_location(p) for p in world_points]
        old_points = a.get_editor_property('patrol_relative_points')
        assert not a.get_editor_property('patrol_points'), 'Actor waypoints take precedence; refuse hidden route replacement'
        assert not old_points or equal([v(p) for p in old_points], [v(p) for p in relative]), 'Distinct existing route: refuse overwrite'
        if verify:
            assert equal(current, v(target_relative)) and equal(v(cap.get_world_location()), v(home))
            assert equal([v(p) for p in old_points], [v(p) for p in relative])
            assert all(equal(a.get_editor_property(k), value) for k, value in PATROL.items())
        centers = [home, home+unreal.Vector(dx, dy, 0), home-unreal.Vector(dx, dy, 0), home]
        geometry = route_geometry(world, a, cap, centers)
        plans[a.get_name()] = {'relative_points': [v(p) for p in relative], 'world_points': [v(p) for p in world_points],
            'capsule_component': cap.get_name(), 'capsule_relative_target': v(target_relative),
            'capsule_world_target': v(home), 'geometry': geometry, 'collision_query_equivalence': True}
        REPORT['maps'][world.get_path_name().split('.')[0]]['candle_plan'] = plans
        persist()
        assert geometry['clear'], ('Candle route blocked/unsupported', a.get_name())
    return plans


def stair_plan(world, by):
    ignore = [a for a in by.values() if isinstance(a, (unreal.Pawn, unreal.CatrunCandle, unreal.CatrunArmor))]
    samples, floors = [], {}
    # Include bounded approach and lower landing around the exact user-log interval.
    ys = sorted(set([950., 998., 1490., 1520., 1540.] + [998.+12.5*i for i in range(40)]))
    for y in ys:
        h = line(world, unreal.Vector(-130, y, 90), unreal.Vector(-130, y, -240), ignore)
        assert h, ('UNINITIALIZED_OR_UNCALIBRATED_NO_FLOOR_CLAIMS', y)
        d = h.to_dict()
        actor, c = d['hit_actor'], d['hit_component']
        assert isinstance(actor, unreal.StaticMeshActor) and isinstance(c, unreal.StaticMeshComponent), hit_data(h)
        assert d['impact_normal'].z >= .5 and -180. <= d['impact_point'].z <= 25., hit_data(h)
        center, extent = actor.get_actor_bounds(False)
        assert extent.x <= 1500 and extent.y <= 1500 and extent.z <= 300, 'Unexpected floor candidate scope'
        floors[actor.get_name()] = {'label': actor.get_actor_label(), 'mesh': path(c.static_mesh),
            'bounds_center': v(center), 'bounds_extent': v(extent), 'original_tags': [str(t) for t in actor.tags]}
        samples.append({'xy': [-130., y], 'floor': hit_data(h)})
    assert 1 <= len(floors) <= 16, floors
    return {'floors': floors, 'samples': samples}


def verify_grid(manager, samples):
    g = grid_arrays(manager)
    size, width, height, origin = float(g['CellSize']), int(g['Width']), int(g['Height']), g['Origin']
    walkable, edges = list(g['Walkable']), list(g['EdgeMask'])
    assert size > 0 and width > 0 and height > 0 and len(walkable) == width*height and len(edges) == width*height
    rows = []
    previous = None
    for sample in samples:
        x, y = sample['xy']
        cx, cy = math.floor((x-origin.x)/size), math.floor((y-origin.y)/size)
        cell = cy*width+cx
        assert 0 <= cx < width and 0 <= cy < height and walkable[cell], ('Missing usable stair grid cell', x, y, cx, cy)
        neighbors = []
        for direction, (dx, dy) in enumerate(((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1))):
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < width and 0 <= ny < height and walkable[ny*width+nx] and edges[cell] & (1 << direction):
                neighbors.append(ny*width+nx)
        assert neighbors, ('Isolated stair cell', cell)
        if previous is not None and previous != cell:
            assert previous in neighbors and cell in rows[-1]['open_usable_neighbors'], ('Consecutive stair cells disconnected', previous, cell)
        rows.append({'xy': [x,y], 'cell': cell, 'grid_xy': [cx,cy], 'open_usable_neighbors': neighbors})
        previous = cell
    return {'grid': grid_summary(manager), 'samples': rows, 'all_covered_and_connected': True}


def load(package):
    clean()
    assert LEVEL.load_level(package), package
    assert not dirty(), ('Load introduced dirty package; abort without save', dirty())
    world = ED.get_editor_world()
    assert world.get_path_name().split('.')[0] == package
    by = {a.get_name(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)}
    return world, by


def manager_of(by):
    managers = [a for a in by.values() if isinstance(a, unreal.SoundGridManager)]
    assert len(managers) == 1
    manager = managers[0]
    settings = manager.get_editor_property('Settings')
    assert settings and path(settings) == '/Game/Systems/Sound/DA_SoundSettings.DA_SoundSettings', 'Unexpected shared settings dependency; report before expanding scope'
    assert str(settings.get_editor_property('floor_tag')) == 'SoundFloor'
    return manager


def target_snapshot(before, package, plan):
    expected = copy.deepcopy(before)
    for name, actor in expected['actors'].items():
        if 'turn_play_rate' in actor and equal(actor['turn_play_rate'], 5.):
            actor['turn_play_rate'] = TARGET_RATE
    if 'Tutorial' in package:
        for name in plan['stairs']['floors']:
            tags = expected['actors'][name]['tags']
            if 'SoundFloor' not in tags:
                tags.append('SoundFloor')
        expected['actors'][plan['manager']]['grid'] = None  # Independently audited bake; not an unconstrained actor change.
    elif 'Stage2' in package:
        for name, candle in plan['candles'].items():
            actor = expected['actors'][name]
            actor['patrol'] = dict(PATROL, patrol_points=[], patrol_relative_points=candle['relative_points'])
            cap = actor['components'][candle['capsule_component']]
            cap['relative']['translation'] = candle['capsule_relative_target']
            cap['world']['translation'] = candle['capsule_world_target']
    return expected


def compare_saved(actual, expected, package, stage):
    actual = copy.deepcopy(actual)
    for name, row in expected['actors'].items():
        if row.get('grid', 'missing') is None:
            actual['actors'][name]['grid'] = None
    differences = diff(actual, expected)
    REPORT['maps'][package][stage+'_differences'] = differences
    persist()
    assert not differences, ('Unexpected mutation outside exact permitted values', package, stage, differences[:10])


def main():
    assert '-run=pythonscript' in COMMAND.lower() and '-catrungeometryisolated' in COMMAND.lower(), 'Separate root-owned commandlet required'
    assert AUDIT or '-catrunworldauthor' in COMMAND.lower(), 'Explicit author/audit mode required'
    clean()
    REPORT['cvars'] = {c: unreal.SystemLibrary.get_console_variable_int_value(c) for c in CVARS}
    assert all(value == 0 for value in REPORT['cvars'].values()), REPORT['cvars']
    probe_path = ROOT / 'Saved/GameplayRepair20261105/candle-lifted-probe-20261105-144103.json'
    if not probe_path.is_file():
        matches = list((ROOT / 'Saved').rglob(probe_path.name))
        assert len(matches) == 1, ('Missing/ambiguous actual calibrated evidence', [str(p) for p in matches])
        probe_path = matches[0]
    evidence = json.loads(probe_path.read_text(encoding='utf-8'))
    assert evidence['completed'] and not evidence['errors']
    REPORT['prior_calibrated_evidence'] = {'path': str(probe_path), 'sha256': digest(probe_path)}
    REPORT['before_hashes'] = asset_hashes()
    REPORT['protected_hashes'] = protected_hashes()
    REPORT['source_sha256'] = digest(ROOT / 'Scripts/GameplayRepair/finish_world_tuning.py')
    bp = AS.load_asset(ARMOR_BP)
    assert bp and bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE
    cdo = unreal.get_default_object(bp.generated_class())
    REPORT['armor_cdo_before'] = float(cdo.get_editor_property('turn_play_rate'))
    assert equal(REPORT['armor_cdo_before'], 5.) or equal(REPORT['armor_cdo_before'], TARGET_RATE), 'Distinct BP default: refuse overwrite'
    baseline = None
    if AUDIT:
        match = re.search(r'-catrunWorldBaseline=(?:"([^"]+)"|(\S+))', COMMAND, re.IGNORECASE)
        assert match, 'Fresh audit requires exact author report baseline'
        baseline_file = Path(match.group(1) or match.group(2)).resolve()
        baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
        assert baseline['completed'] and not baseline['audit_only']
        assert baseline['after_hashes'] == REPORT['before_hashes'], 'Packages changed after the author save; audit this actual baseline before other asset work'
        REPORT['baseline'] = str(baseline_file)
        assert baseline['process_id'] != os.getpid(), 'Audit must be a new process'
        assert equal(REPORT['armor_cdo_before'], TARGET_RATE)
    else:
        for package in REPORT['scope']:
            source = file_for(package)
            destination = OUT / 'Before' / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            assert digest(source) == digest(destination)
            REPORT['backups'].append({'package': package, 'file': str(source), 'sha256': digest(source)})
    checkpoint('preflight')
    # Preflight ALL six maps before first asset mutation; no incompatible shared grid bake.
    for package in MAPS:
        REPORT['maps'][package] = {}
        world, by = load(package)
        manager = manager_of(by)
        plan = {'manager': manager.get_name()}
        before = snapshot(world)
        REPORT['maps'][package]['before'] = before
        REPORT['maps'][package]['intentional_armor_rates_preserved'] = {
            n: r['turn_play_rate'] for n,r in before['actors'].items() if 'turn_play_rate' in r
            and not equal(r['turn_play_rate'],5.) and not equal(r['turn_play_rate'],TARGET_RATE)}
        if 'Tutorial' in package:
            assert equal(float(manager.get_editor_property('player_bell_budget_override')), 650.), 'Preserve tutorial bell budget650'
            assert all(not a.get_editor_property('patrol_enabled') for a in by.values() if isinstance(a, unreal.CatrunCandle))
            plan['stairs'] = stair_plan(world, by)
            REPORT['maps'][package]['stairs'] = plan['stairs']
            if AUDIT:
                assert all('SoundFloor' in [str(t) for t in by[n].tags] for n in plan['stairs']['floors'])
                REPORT['maps'][package]['grid_audit'] = verify_grid(manager, plan['stairs']['samples'])
        elif 'Stage1' in package:
            basket = by['BP_HideBasket_C_1']
            REPORT['maps'][package]['basket_snapshot_only'] = {
                'open_direction_local': v(basket.get_editor_property('open_direction_local')),
                'reason': 'Latest user correction: preserve orientation pending separate input/camera proof'}
            del basket
        else:
            plan['candles'] = candle_plan(world, by, verify=AUDIT)
        expected = baseline['maps'][package]['expected'] if AUDIT else target_snapshot(before,package,plan)
        REPORT['maps'][package]['plan'] = plan
        REPORT['maps'][package]['expected'] = expected
        if AUDIT:
            compare_saved(before,expected,package,'cold_saved')
        checkpoint('preflight:'+package)
        del world, by, manager
    clean()
    if AUDIT:
        assert REPORT['before_hashes'] == asset_hashes(), 'Audit changed package bytes'
        assert baseline['protected_hashes'] == protected_hashes(), 'Protected dependency changed since authoring'
        checkpoint('audit_complete', completed=True, dirty_after=dirty())
        print('CATRUN_WORLD_AUDITED', str(OUT/'report.json'))
        return
    # Recheck current bytes against backups; another process must never be overwritten.
    assert REPORT['before_hashes'] == asset_hashes()
    # Compile outside gameplay maps so default propagation cannot dirty a loaded map.
    assert LEVEL.load_level('/Game/Maps/MainMenu')
    clean()
    checkpoint('author_blueprint')
    if not equal(cdo.get_editor_property('turn_play_rate'), TARGET_RATE):
        cdo.set_editor_property('turn_play_rate', TARGET_RATE)
        from toolset_registry.helpers import compile_blueprint
        compile_blueprint(bp, True)
        assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE
        assert equal(unreal.get_default_object(bp.generated_class()).get_editor_property('turn_play_rate'),TARGET_RATE)
        assert set(dirty()) <= {ARMOR_BP}, ('Unexpected BP compile dirty packages',dirty())
        assert AS.save_loaded_asset(bp, False)
        REPORT['saved'].append(ARMOR_BP)
    clean()
    for package in MAPS:
        checkpoint('author:'+package)
        world, by = load(package)
        row = REPORT['maps'][package]
        plan = row['plan']
        # CDO propagation may have replaced old5 with target; distinct values must survive.
        for name, old in row['before']['actors'].items():
            if 'turn_play_rate' in old:
                actual = float(by[name].get_editor_property('turn_play_rate'))
                allowed = [old['turn_play_rate'], TARGET_RATE] if equal(old['turn_play_rate'],5.) else [old['turn_play_rate']]
                assert any(equal(actual,x) for x in allowed), ('Concurrent armor tuning',name,actual)
                if equal(old['turn_play_rate'],5.):
                    by[name].set_editor_property('turn_play_rate', TARGET_RATE)
        if 'Tutorial' in package:
            for name in plan['stairs']['floors']:
                tags = list(by[name].tags)
                if 'SoundFloor' not in [str(t) for t in tags]:
                    by[name].set_editor_property('tags',tags+[unreal.Name('SoundFloor')])
            manager = manager_of(by)
            manager.build_grid()
            assert manager.has_grid()
            row['grid_audit'] = verify_grid(manager,plan['stairs']['samples'])
        elif 'Stage2' in package:
            for name, candle in plan['candles'].items():
                a = by[name]
                a.get_editor_property('blocking_capsule').set_relative_location(unreal.Vector(*candle['capsule_relative_target']),False,False)
                for key,value in PATROL.items():
                    a.set_editor_property(key,value)
                a.set_editor_property('patrol_relative_points',[unreal.Vector(*p) for p in candle['relative_points']])
            row['authored_candles'] = candle_plan(world,by,verify=True)
        row['after'] = snapshot(world)
        compare_saved(row['after'],row['expected'],package,'before_save')
        if 'Tutorial' in package:
            # The bake is allowed to change the grid during authoring, but the
            # next process must recover this exact verified serialized grid.
            row['expected']['actors'][plan['manager']]['grid'] = copy.deepcopy(
                row['after']['actors'][plan['manager']]['grid'])
        assert set(dirty()) <= {package}, ('Unexpected dirty package; refuse broad save',dirty())
        assert LEVEL.save_current_level()
        REPORT['saved'].append(package)
        row['saved_sha256'] = digest(file_for(package))
        clean()
        persist()
        if 'Tutorial' in package:
            del manager
        del world, by
    assert REPORT['protected_hashes'] == protected_hashes(), 'Protected dependency bytes changed'
    checkpoint('author_complete', completed=True, after_hashes=asset_hashes(), dirty_after=dirty())
    print('CATRUN_WORLD_SAVED', str(OUT/'report.json'))


try:
    main()
except Exception:
    REPORT['errors'].append(traceback.format_exc())
    REPORT['dirty_on_abort'] = dirty()
    persist()
    print('CATRUN_WORLD_ABORTED', str(OUT/'report.json'))
    raise
