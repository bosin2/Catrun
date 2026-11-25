"""Root-only authoring of a cosmetic Stage3 docking presenter.

Run apply() after visuals.apply() and a successful mechanism import. Creates one
owned new BP and two new actors; never saves the level or alters gameplay code.
The only Catrun runtime call is the pure IsPuzzleSeated(PuzzleId) query.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GothicRevision20261125'
SOURCE = Path('C:/Users/whghk/Desktop/CastleKit/Stage3/Mechanisms03_20261125')
PATH = '/Game/Environment/Stage3/GothicRevision_20261125/Blueprints/BP_GothicDockPresentation'
PREFIX = 'S3_GothicPresentation_'
OWNER = 'Stage3GothicDockPresentation20261125'
VERSION = '2'
MATH = '/Script/Engine.KismetMathLibrary:'
ACTOR = '/Script/Engine.Actor:'
SYSTEM = '/Script/Engine.KismetSystemLibrary:'
PARTS = {'Fork': 'SM_S3_DockCaptureFork', 'Pin': 'SM_S3_DockCrossPin',
         'ChainTerminal': 'SM_S3_DockChainTerminal'}


def read_poses():
    paths = {state: SOURCE / ('Dock/Assemblies/Dock_' + filename + '.json')
             for state, filename in (('open', 'Approach'), ('closed', 'Latched'))}
    raw = {state: path.read_bytes() for state, path in paths.items()}
    data = {state: json.loads(value) for state, value in raw.items()}
    delta = {part: [(data['closed'][name]['translation_m'][axis] -
                     data['open'][name]['translation_m'][axis]) * 100 for axis in range(3)]
             for part, name in PARTS.items()}
    if abs(delta['Fork'][2] + 19) > .01 or abs(delta['Pin'][1] - 7.2) > .01:
        raise RuntimeError('Dock source contract changed: ' + str(delta))
    return data, delta, {str(paths[s]): hashlib.sha256(raw[s]).hexdigest() for s in raw}


def world_closed(open_world, source_delta_cm, rear_sign):
    """Apply exactly the axis correction used by visuals.py to a source delta."""
    delta = [-rear_sign * source_delta_cm[0], -source_delta_cm[1], source_delta_cm[2]]
    return [a + b for a, b in zip(open_world, delta)]


def author_blueprint():
    import unreal as u
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
    from menu_graph import Graph, compile_bp, entry, wire, editor
    ea = u.EditorAssetLibrary
    bp = ea.load_asset(PATH) if ea.does_asset_exist(PATH) else None
    if bp:
        if ea.get_metadata_tag(bp, 'GothicDockOwner') != OWNER:
            raise RuntimeError('Refusing existing unowned BP: ' + PATH)
        if ea.get_metadata_tag(bp, 'GothicDockGraphVersion') == VERSION:
            compile_bp(bp)
            return bp
    else:
        folder, name = PATH.rsplit('/', 1)
        bp = BP.create(folder, name, u.Actor.static_class())
        if not bp: raise RuntimeError('Could not create cosmetic presentation BP')
        ea.set_metadata_tag(bp, 'GothicDockOwner', OWNER)
    # Retry support is confined to this owned new asset. Never edits another BP.
    graph = BP.get_graph(bp, 'EventGraph')
    nodes = [r.node for r in BP.get_node_infos(BP.find_nodes(graph))]
    if nodes: editor(graph).remove_nodes(nodes)
    if BP.get_graph(bp, 'ApplyCosmeticPose'):
        BP.remove_function_graph(bp, 'ApplyCosmeticPose')
    existing = {str(n) for n in BP.list_variables(bp)}
    objects = {'Director': u.CatrunStatuePuzzle, 'Fork': u.StaticMeshActor,
               'Pin': u.StaticMeshActor, 'ChainTerminal': u.StaticMeshActor,
               'OpenChain': u.StaticMeshActor, 'ChainComponent': u.StaticMeshComponent,
               'OpenMesh': u.StaticMesh, 'ClosedMesh': u.StaticMesh}
    variables = {'PuzzleId': 'name', 'Alpha': 'float', 'MoveSpeed': 'float',
                 'Initialized': 'bool', 'ClosedDisplayed': 'bool',
                 'ForkOpen': 'Vector', 'ForkClosed': 'Vector', 'PinOpen': 'Vector',
                 'PinLowered': 'Vector', 'PinClosed': 'Vector',
                 'ChainTerminalOpen': 'Vector', 'ChainTerminalClosed': 'Vector'}
    for name, cls in objects.items():
        if name not in existing: BP.add_object_variable(bp, name, cls.static_class())
    for name, kind in variables.items():
        if name not in existing: BP.add_variable(bp, name, kind)
    for name in list(objects) + list(variables):
        if name not in ('Alpha', 'Initialized', 'ClosedDisplayed'):
            BP.set_variable_instance_editable(bp, name, True)
    compile_bp(bp)
    pose_graph = BP.add_function_graph(bp, 'ApplyCosmeticPose')
    q = Graph(pose_graph)
    start = entry(q)
    move = q.fn(MATH + 'MapRangeClamped', Value=q.ref('Alpha'), InRangeA=0, InRangeB=.7, OutRangeA=0, OutRangeB=1)
    latch = q.fn(MATH + 'MapRangeClamped', Value=q.ref('Alpha'), InRangeA=.7, InRangeB=1, OutRangeA=0, OutRangeB=1)
    fork = q.fn(MATH + 'VLerp', A=q.ref('ForkOpen'), B=q.ref('ForkClosed'), Alpha=(move, 'ReturnValue'))
    pin_down = q.fn(MATH + 'VLerp', A=q.ref('PinOpen'), B=q.ref('PinLowered'), Alpha=(move, 'ReturnValue'))
    pin_latched = q.fn(MATH + 'VLerp', A=(pin_down, 'ReturnValue'), B=q.ref('PinClosed'), Alpha=(latch, 'ReturnValue'))
    terminal = q.fn(MATH + 'VLerp', A=q.ref('ChainTerminalOpen'), B=q.ref('ChainTerminalClosed'), Alpha=(move, 'ReturnValue'))
    setters = []
    for name, result in (('Fork', fork), ('Pin', pin_latched), ('ChainTerminal', terminal)):
        setters.append(q.fn(ACTOR + 'K2_SetActorLocation', target=q.ref(name),
                           NewLocation=(result, 'ReturnValue'), bSweep='false', bTeleport='true'))
    closed = q.fn(MATH + 'GreaterEqual_DoubleDouble', A=q.ref('Alpha'), B=.999)
    different = q.fn(MATH + 'NotEqual_BoolBool', A=(closed, 'ReturnValue'), B=q.ref('ClosedDisplayed'))
    changed = q.branch((different, 'ReturnValue'))
    select = q.branch((closed, 'ReturnValue'))
    q.chain(start, *setters, changed, select)
    for output, mesh_var, value in (('then', 'ClosedMesh', 'true'), ('else', 'OpenMesh', 'false')):
        swap = q.fn('/Script/Engine.StaticMeshComponent:SetStaticMesh', target=q.ref('ChainComponent'), NewMesh=q.ref(mesh_var))
        wire(select, output, swap, 'execute')
        remember = q.set('ClosedDisplayed', value=value)
        q.chain(swap, remember)
    # Avoid add_comment_to_nodes: the installed editor helper creates comment
    # nodes without NodeGuid. Readable graph lanes remain; no comments are needed.
    compile_bp(bp)
    tick = BP.add_event(bp, 'ReceiveTick', u.IntPoint(0, 0))
    if not tick or tick.get_class().get_name() != 'K2Node_Event':
        raise RuntimeError('ReceiveTick native event could not be authored')
    q = Graph(graph, 350, 0)
    condition = None
    for name in objects:
        valid = q.fn(SYSTEM + 'IsValid', Object=q.ref(name))
        condition = (valid, 'ReturnValue') if condition is None else (
            q.fn(MATH + 'BooleanAND', A=condition, B=(valid, 'ReturnValue')), 'ReturnValue')
    ready = q.branch(condition)
    wire(tick, 'then', ready, 'execute')
    seated = q.fn('/Script/Catrun.CatrunStatuePuzzle:IsPuzzleSeated', target=q.ref('Director'), PuzzleId=q.ref('PuzzleId'))
    target = q.fn(MATH + 'SelectFloat', A=1, B=0, bPickA=(seated, 'ReturnValue'))
    initialized = q.branch(q.ref('Initialized'))
    q.chain(ready, initialized)
    smooth = q.fn(MATH + 'FInterpTo_Constant', Current=q.ref('Alpha'), Target=(target, 'ReturnValue'),
                  DeltaTime=(tick, 'DeltaSeconds'), InterpSpeed=q.ref('MoveSpeed'))
    advance = q.set('Alpha', source=(smooth, 'ReturnValue'))
    wire(initialized, 'then', advance, 'execute')
    snap = q.set('Alpha', source=(target, 'ReturnValue'))
    wire(initialized, 'else', snap, 'execute')
    mark = q.set('Initialized', value='true')
    q.chain(snap, mark)
    call_path = PATH + '.BP_GothicDockPresentation_C:ApplyCosmeticPose'
    update = q.fn(call_path)
    wire(advance, 'then', update, 'execute')
    wire(mark, 'then', update, 'execute')
    compile_bp(bp)
    cdo = u.get_default_object(bp.generated_class())
    cdo.set_editor_property('MoveSpeed', 1 / .6)
    cdo.set_editor_property('Alpha', 0.)
    cdo.set_editor_property('Initialized', False)
    cdo.set_editor_property('ClosedDisplayed', False)
    tick_settings = cdo.get_editor_property('primary_actor_tick')
    # bCanEverTick is not reflected. Compiling ReceiveTick makes the generated
    # Actor class tick-capable; its public startup flag remains configurable.
    tick_settings.set_editor_property('start_with_tick_enabled', True)
    tick_settings.set_editor_property('tick_group', u.TickingGroup.TG_POST_UPDATE_WORK)
    cdo.set_editor_property('primary_actor_tick', tick_settings)
    cdo.set_editor_property('replicates', False)
    ea.set_metadata_tag(bp, 'GothicDockGraphVersion', VERSION)
    if not ea.save_loaded_asset(bp): raise RuntimeError('Could not save presentation BP')
    return bp


def apply():
    import unreal as u
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    ea, act = u.EditorAssetLibrary, u.get_editor_subsystem(u.EditorActorSubsystem)
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name() != '/Game/Maps/Stage3.Stage3':
        raise RuntimeError('Load Stage3 explicitly')
    imported = json.loads((OUT / 'import_report.json').read_text())
    if not imported.get('success'): raise RuntimeError('Successful mechanism import required')
    source, deltas, hashes = read_poses()
    lookup = {a.get_actor_label(): a for a in act.get_all_level_actors()}
    directors = [a for a in lookup.values() if isinstance(a, u.CatrunStatuePuzzle)]
    if len(directors) != 1: raise RuntimeError('Expected one existing Stage3 puzzle director')
    director = directors[0]
    links = {str(row.get_editor_property('PuzzleId')): row for row in director.get_editor_property('Links')}
    if not {'S3_P1', 'S3_P2'} <= set(links): raise RuntimeError('Stage3 puzzle IDs missing')
    bounds = imported['meshes']['SM_S3_DockArch']['bounds']
    rear_sign = 1 if abs(bounds[1][1]) > abs(bounds[0][1]) else -1
    open_mesh = ea.load_asset(imported['meshes']['SM_S3_DockShortChain_OpenPose']['path'])
    closed_mesh = ea.load_asset(imported['meshes']['SM_S3_DockShortChain']['path'])
    if not open_mesh or not closed_mesh: raise RuntimeError('Both authored chain state meshes are required')
    plans = []
    for n in (1, 2):
        refs = {key: lookup['S3_GothicVisual_Dock%d_%s' % (n, name.removeprefix('SM_S3_'))]
                for key, name in PARTS.items()}
        refs['OpenChain'] = lookup['S3_GothicVisual_Dock%d_DockShortChain_OpenPose' % n]
        for actor in refs.values():
            if actor.static_mesh_component.get_collision_enabled() != u.CollisionEnabled.NO_COLLISION:
                raise RuntimeError('Presentation may only target cosmetic NoCollision actors: '+actor.get_actor_label()+' '+str(actor.static_mesh_component.get_collision_enabled())+' expected '+str(u.CollisionEnabled.NO_COLLISION))
        values = {}
        for key in PARTS:
            location = refs[key].get_actor_location()
            start = [location.x, location.y, location.z]
            # Apply is editor-only; current actor locations must still be the open
            # poses set by visuals.py, rather than an arbitrary runtime snapshot.
            plate = links['S3_P%d' % n].get_editor_property('Plate').get_actor_location()
            local = source['open'][PARTS[key]]['translation_m']
            expected = [plate.x - rear_sign * local[0] * 100, plate.y - local[1] * 100, local[2] * 100]
            if max(abs(a - b) for a, b in zip(start, expected)) > .1:
                raise RuntimeError('Open visual source pose mismatch: ' + refs[key].get_actor_label())
            values[key + 'Open'] = start
            values[key + 'Closed'] = world_closed(start, deltas[key], rear_sign)
        values['PinLowered'] = [values['PinOpen'][0], values['PinOpen'][1], values['PinClosed'][2]]
        plans.append((n, refs, values))
    for filename, expected in hashes.items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Source assembly changed during preparation')
    bp = author_blueprint()
    for label, actor in lookup.items():
        if label.startswith(PREFIX):
            if OWNER not in [str(t) for t in actor.tags]: raise RuntimeError('Unowned presenter actor')
            if not act.destroy_actor(actor): raise RuntimeError('Cannot remove old owned presenter')
    report = {'success': False, 'blueprint': bp.get_path_name(), 'source_sha256': hashes,
              'import_sha256': imported['input_sha256'], 'instances': [], 'map_saved': False,
              'runtime_verified': False, 'graph_status': str(bp.get_editor_property('status')),
              'motion': {'duration_seconds': .6, 'fork_lower_cm': 19, 'pin_insert_cm': 7.2,
                         'descent_fraction': .7, 'chain_swap_alpha': .999,
                         'restart_policy': 'First tick snaps to current IsPuzzleSeated; later changes interpolate'}}
    try:
        for n, refs, values in plans:
            presenter = act.spawn_actor_from_class(bp.generated_class(), u.Vector(0, 0, 0))
            if not presenter: raise RuntimeError('Could not spawn presenter')
            presenter.set_actor_label(PREFIX + 'Dock%d' % n)
            presenter.set_folder_path('Stage3/GothicRevision/Presentation')
            presenter.tags = [u.Name(OWNER)]
            presenter.set_editor_property('Director', director)
            presenter.set_editor_property('PuzzleId', u.Name('S3_P%d' % n))
            for key, actor in refs.items(): presenter.set_editor_property(key, actor)
            presenter.set_editor_property('ChainComponent', refs['OpenChain'].static_mesh_component)
            presenter.set_editor_property('OpenMesh', open_mesh)
            presenter.set_editor_property('ClosedMesh', closed_mesh)
            for key, position in values.items(): presenter.set_editor_property(key, u.Vector(*position))
            report['instances'].append({'actor': presenter.get_actor_label(), 'puzzle_id': 'S3_P%d' % n,
                'director': director.get_actor_label(), 'references': {key: a.get_actor_label() for key, a in refs.items()},
                'poses': values})
        report['graphs'] = {g.get_name(): [str(info.type_id) for info in BP.get_node_infos(BP.find_nodes(g))]
                            for g in BP.list_graphs(bp)}
        report['success'] = True
        return report
    except Exception as exc:
        report['error'] = repr(exc)
        raise
    finally:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'presentation_report.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    raise SystemExit('Root writer must explicitly call presentation.apply(); it does not save the map.')
