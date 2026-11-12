"""Repair tutorial exit ownership in the existing two Blueprints.

Run in Unreal's Python commandlet with CATRUN_TUTORIAL_REPAIR_MODE set to
probe, author, resave_metadata or audit. Probe and audit never save packages.
The metadata resave persists GUIDs supplied by Unreal when the comments load.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.object import ObjectTools


ROOT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
OUT = ROOT / 'Saved/GameplayRepair20261112/TutorialTravelFailure'
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import Graph, compile_bp, entry, pin, wire


EXIT = '/Game/Systems/LevelFlow/BP_LevelExit'
DIRECTOR = '/Game/Cinematics/Transitions/Blueprints/BP_StairDescentDirector'
SEQUENCE = '/Game/Cinematics/Transitions/LS_Tutorial_StairDescent'
TUTORIAL = '/Game/Maps/Tutorial'
OWNED = (EXIT, DIRECTOR)
PRESERVED = (TUTORIAL, SEQUENCE, '/Game/Cinematics/LS_Tutorial',
             '/Game/Blueprints/BP_TutorialIntro', '/Game/UI/Tutorial/WBP_Tutorial_KeyHint')
FLOW = '/Script/Catrun.CatrunLevelFlowLibrary:'
ACTOR = '/Script/Engine.Actor:'
CONTROLLER = '/Script/Engine.Controller:'
PLAYER = '/Script/Engine.PlayerController:'
CAMERA = '/Script/Engine.PlayerCameraManager:'
GAME = '/Script/Engine.GameplayStatics:'
SYSTEM = '/Script/Engine.KismetSystemLibrary:'
MATH = '/Script/Engine.KismetMathLibrary:'
MOVIE = '/Script/MovieScene.MovieSceneSequencePlayer:'
LEVEL_PLAYER = '/Script/LevelSequence.LevelSequencePlayer:'
COMPONENT = '/Script/Engine.ActorComponent:'


def asset(path):
    result = u.EditorAssetLibrary.load_asset(path)
    assert result, path
    return result


def content_file(package):
    extension = '.umap' if package == TUTORIAL else '.uasset'
    return ROOT / 'Content' / (package.removeprefix('/Game/') + extension)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(packages):
    return {package: file_hash(content_file(package)) for package in packages}


def write_report(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def graph_rows(bp):
    return {g.get_name(): [
        {'name': n.node.get_name(), 'type': n.type_id,
         'inputs': [{'name': p.name, 'type': p.type_id, 'value': str(p.value),
                     'links': str(p.connected_pins)} for p in n.input_pins],
         'outputs': [{'name': p.name, 'type': p.type_id,
                      'links': str(p.connected_pins)} for p in n.output_pins]}
        for n in BP.get_node_infos(BP.find_nodes(g))] for g in BP.list_graphs(bp)}


def probe(blueprints):
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert levels.load_level(TUTORIAL), TUTORIAL
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    rows = {}
    for path, fields in ((EXIT, ('WaitForCinematic', 'TransitionStarted')),
                         (DIRECTOR, ('ExitActor', 'GameplayCamera', 'Started', 'SequencePlayer'))):
        bp = blueprints[path]
        cls = bp.generated_class()
        instances = [a for a in actors if a.get_class() == cls]
        assert len(instances) == 1, (path, instances)
        rows[path] = {
            'instance': instances[0].get_path_name(),
            'properties': ObjectTools.get_properties(instances[0], list(fields)),
            'class_defaults': ObjectTools.get_properties(u.get_default_object(cls), list(fields)),
            'tick_enabled': instances[0].is_actor_tick_enabled(),
            'graphs': graph_rows(bp),
        }
    q = Graph(BP.get_graph(blueprints[EXIT], 'BeginTransition'))
    actions = [n for n in q.e.list_available_nodes([]) if any(
        match in re.sub(r'[^a-z]', '', n.lower())
        for match in ('referencetoself', 'createevent', 'getactortransform'))]
    sequence = asset(SEQUENCE)
    def tracks(items):
        return [{'name': t.get_class().get_name(), 'sections': [
            str(s.get_completion_mode()) for s in t.get_sections()]} for t in items]
    bindings = [{'name': b.get_name(), 'tracks': tracks(b.get_tracks())}
                for b in sequence.get_bindings()]
    write_report('probe', {'assets': rows, 'hashes': hashes(OWNED + PRESERVED),
                           'actions': actions, 'sequence_bindings': bindings,
                           'sequence_tracks': tracks(sequence.get_tracks())})
    u.log('CATRUN_TUTORIAL_TRAVEL_FAILURE_PROBE_OK')


def read_report(name):
    return json.loads((OUT / f'{name}.json').read_text(encoding='utf-8'))


def bp_function(package, name):
    return package + '.' + package.rsplit('/', 1)[1] + '_C:' + name


def result(node):
    return node, 'ReturnValue'


def break_wire(a, ap, b, bp):
    output = pin(a, ap, True)
    target = pin(b, bp)
    assert target in output.list_connected_pins(), (a.get_name(), ap, b.get_name(), bp)
    BP.break_pins(BP._pin_to_id(output), BP._pin_to_id(target))


def named_nodes(q):
    return {n.get_name(): n for n in BP.find_nodes(q.g)}


def action(q, suffix):
    matches = [n for n in q.e.list_available_nodes([])
               if re.sub(r'[^a-z]', '', n.lower()).endswith(suffix)]
    assert len(matches) == 1, (suffix, matches)
    return q.placed(BP.create_node(q.g, matches[0], u.IntPoint(q.x, q.y)))


def self_ref(q):
    return action(q, 'getareferencetoself'), 'self'


def failure_callback(q, travel, function):
    callback = action(q, 'createevent')
    assert callback.get_class().get_name() == 'K2Node_CreateDelegate'
    wire(callback, 'OutputDelegate', travel, 'Failure')
    BP.set_create_event_function(callback, function)


def valid(q, source):
    return result(q.fn(SYSTEM + 'IsValid', Object=source))


def both(q, a, b):
    return result(q.fn(MATH + 'BooleanAND', A=a, B=b))


def equal(q, a, b):
    return result(q.fn(MATH + 'EqualEqual_ObjectObject', A=a, B=b))


def notice(q, message):
    text = q.fn('/Script/Engine.KismetTextLibrary:Conv_StringToText', InString=message)
    return q.fn('/Script/Catrun.CatrunNoticeLibrary:ShowBottomNotice', Text=result(text), Duration='3')


def clear(q, *names):
    return [q.set(name) for name in names]


def setup(bp, obj_vars, value_vars, functions):
    for name, cls in obj_vars:
        BP.add_object_variable(bp, name, cls.static_class())
    for name, typename in value_vars:
        BP.add_variable(bp, name, typename)
    for name in functions:
        BP.add_function_graph(bp, name)
    compile_bp(bp)


def author_exit(bp):
    recover_name = 'RecoverFailedStageExit'
    setup(bp, (('ExitPawn', u.Pawn), ('ExitController', u.PlayerController),
               ('ExitCameraManager', u.PlayerCameraManager)),
          (('ExitPawnPose', 'Transform'), ('ExitPawnHadCollision', 'bool'),
           ('RestoringExit', 'bool'), ('ExitTravelRequested', 'bool')),
          (recover_name,))

    q = Graph(BP.get_graph(bp, 'BeginTransition'), -3300, 0)
    old = named_nodes(q)
    started = old['K2Node_VariableSet_0']
    move_lock = old['K2Node_CallFunction_1']
    stop = old['K2Node_CallFunction_4']
    fade = old['K2Node_CallFunction_6']
    pawn = result(old['K2Node_CallFunction_2'])
    controller = result(old['K2Node_CallFunction_0'])
    camera = result(old['K2Node_CallFunction_5'])
    movement = result(old['K2Node_CallFunction_3'])
    ready = q.branch(both(q, both(q, valid(q, pawn), valid(q, controller)), valid(q, camera)))
    break_wire(entry(q), 'then', started, 'execute')
    q.chain(entry(q), ready)
    reserve = q.fn(FLOW + 'ReserveStagePresentation', Owner=self_ref(q))
    wire(ready, 'then', reserve, 'execute')
    reserved = q.branch(result(reserve))
    save_pawn = q.set('ExitPawn', source=pawn)
    save_controller = q.set('ExitController', source=controller)
    save_camera = q.set('ExitCameraManager', source=camera)
    pose = q.fn(ACTOR + 'GetTransform', target=q.ref('ExitPawn'))
    collision = q.fn(ACTOR + 'GetActorEnableCollision', target=q.ref('ExitPawn'))
    save_pose = q.set('ExitPawnPose', source=result(pose))
    save_collision = q.set('ExitPawnHadCollision', source=result(collision))
    q.chain(reserve, reserved, save_pawn, save_controller, save_camera, save_pose, save_collision, started)
    break_wire(*controller, move_lock, 'self')
    wire(*q.ref('ExitController'), move_lock, 'self')
    break_wire(*camera, fade, 'self')
    wire(*q.ref('ExitCameraManager'), fade, 'self')
    movement_gate = q.branch(valid(q, movement))
    break_wire(move_lock, 'then', stop, 'execute')
    q.chain(move_lock, movement_gate, stop)
    wire(movement_gate, 'else', fade, 'execute')
    q.comment('Reserve stage presentation and snapshot the departing pawn before locking input.')

    q = Graph(BP.get_graph(bp, 'EventGraph'), 1600, 390)
    overlap = named_nodes(q)
    begin = overlap['K2Node_CallFunction_6']
    wait_for_cinematic = overlap['K2Node_IfThenElse_2']
    started_gate = q.branch(q.ref('TransitionStarted'))
    break_wire(begin, 'then', wait_for_cinematic, 'execute')
    q.chain(begin, started_gate, wait_for_cinematic)

    q = Graph(BP.get_graph(bp, 'CompleteTransition'), 340, 0)
    old = named_nodes(q)['K2Node_CallFunction_1']
    BP.delete_node(old)
    started_gate = q.branch(q.ref('TransitionStarted'))
    duplicate = q.branch(q.ref('ExitTravelRequested'))
    requested = q.set('ExitTravelRequested', value='true')
    travel = q.fn(FLOW + 'CompleteCurrentStageWithFailure', Owner=self_ref(q))
    failure_callback(q, travel, recover_name)
    q.chain(entry(q), started_gate, duplicate)
    wire(duplicate, 'else', requested, 'execute')
    q.chain(requested, travel)
    q.comment('Direct exit passes the reservation owner and a failure callback to level flow.')

    q = Graph(BP.get_graph(bp, recover_name), 340, 0)
    started_gate = q.branch(q.ref('TransitionStarted'))
    recovering_gate = q.branch(q.ref('RestoringExit'))
    recovering = q.set('RestoringExit', value='true')
    q.chain(entry(q), started_gate, recovering_gate)
    wire(recovering_gate, 'else', recovering, 'execute')
    restore = q.fn(FLOW + 'RestoreFailedStagePawn', Pawn=q.ref('ExitPawn'),
                   OriginalTransform=q.ref('ExitPawnPose'), bOriginalCollision=q.ref('ExitPawnHadCollision'))
    controller_gate = q.branch(valid(q, q.ref('ExitController')))
    unlock = q.fn(CONTROLLER + 'SetIgnoreMoveInput', target=q.ref('ExitController'), bNewMoveInput='false')
    camera_gate = q.branch(valid(q, q.ref('ExitCameraManager')))
    unmask = q.fn(CAMERA + 'StopCameraFade', target=q.ref('ExitCameraManager'))
    release = q.fn(FLOW + 'ReleaseStagePresentation', Owner=self_ref(q))
    rearm = q.set('TransitionStarted', value='false')
    reset_travel = q.set('ExitTravelRequested', value='false')
    reset_restore = q.set('RestoringExit', value='false')
    q.chain(recovering, restore, controller_gate, unlock, camera_gate, unmask, release, rearm, reset_travel,
            *clear(q, 'ExitPawn', 'ExitController', 'ExitCameraManager'), reset_restore)
    wire(controller_gate, 'else', camera_gate, 'execute')
    wire(camera_gate, 'else', release, 'execute')
    safe = q.branch(result(restore))
    retry = notice(q, '이동을 마치지 못했어요. 출구에서 나왔다가 다시 시도해 주세요.')
    restart = notice(q, '안전한 위치로 돌아가지 못했어요. 설정에서 스테이지를 다시 시작해 주세요.')
    q.chain(reset_restore, safe, retry)
    wire(safe, 'else', restart, 'execute')
    q.comment('Recover pawn safely before rearming the trigger. Balance this exit’s input lock and release its reservation.')
    compile_bp(bp)


def author_director(bp):
    recover_name = 'RecoverFailedStairPresentation'
    queue_name = 'QueueFailedStairRecovery'
    setup(bp, (('StairSequenceActor', u.LevelSequenceActor), ('StairController', u.PlayerController),
               ('StairPreviousView', u.Actor), ('StairCamera', u.Actor), ('StairCameraAtFailure', u.Actor)),
          (('StairCameraTickWasEnabled', 'bool'), ('StairTravelRequested', 'bool')),
          (recover_name, queue_name))

    g = BP.get_graph(bp, 'EventGraph')
    q = Graph(g, -3200, 960)
    old = named_nodes(q)
    director_gate = old['K2Node_IfThenElse_0']
    exit_gate = old['K2Node_IfThenElse_1']
    director_tick = old['K2Node_CallFunction_3']
    camera_tick = old['K2Node_CallFunction_4']
    original_delay = old['K2Node_CallFunction_5']
    original_fade = old['K2Node_CallFunction_7']
    create = old['K2Node_CallFunction_8']
    save_player = old['K2Node_VariableSet_1']
    bind = old['K2Node_AddDelegate_1']
    finished = old['K2Node_CustomEvent_0']
    old_travel = old['K2Node_CallFunction_10']

    exit_valid = q.branch(valid(q, q.ref('ExitActor')))
    break_wire(director_gate, 'else', exit_gate, 'execute')
    wire(director_gate, 'else', exit_valid, 'execute')
    q.chain(exit_valid, exit_gate)

    camera = q.set('StairCamera', source=(old['K2Node_VariableGet_4'], 'GameplayCamera'))
    camera_valid = q.branch(valid(q, q.ref('StairCamera')))
    tick = q.fn(ACTOR + 'IsActorTickEnabled', target=q.ref('StairCamera'))
    save_tick = q.set('StairCameraTickWasEnabled', source=result(tick))
    camera_was_ticking = q.branch(q.ref('StairCameraTickWasEnabled'))
    break_wire(director_tick, 'then', camera_tick, 'execute')
    break_wire(old['K2Node_VariableGet_4'], 'GameplayCamera', camera_tick, 'self')
    q.chain(director_tick, camera, camera_valid, save_tick, camera_was_ticking, camera_tick)
    wire(*q.ref('StairCamera'), camera_tick, 'self')
    wire(camera_valid, 'else', original_delay, 'execute')
    wire(camera_was_ticking, 'else', original_delay, 'execute')

    controller = result(q.fn(GAME + 'GetPlayerController', PlayerIndex='0'))
    save_controller = q.set('StairController', source=controller)
    controller_valid = q.branch(valid(q, q.ref('StairController')))
    view = q.fn(CONTROLLER + 'GetViewTarget', target=q.ref('StairController'))
    save_view = q.set('StairPreviousView', source=result(view))
    recover = q.fn(bp_function(DIRECTOR, recover_name))
    break_wire(original_fade, 'then', create, 'execute')
    q.chain(original_fade, save_controller, controller_valid, save_view, create)
    wire(controller_valid, 'else', recover, 'execute')

    save_actor = q.set('StairSequenceActor', source=(create, 'OutActor'))
    player_valid = q.branch(valid(q, q.ref('SequencePlayer')))
    break_wire(save_player, 'then', bind, 'execute')
    q.chain(save_player, save_actor, player_valid, bind)
    wire(player_valid, 'else', recover, 'execute')
    q.comment('Keep the existing delay, fade, sequence and play nodes. Capture their pre-play view and camera tick.')

    q = Graph(g, 400, 1600)
    BP.delete_node(old_travel)
    started = q.branch(q.ref('Started'))
    duplicate = q.branch(q.ref('StairTravelRequested'))
    request = q.set('StairTravelRequested', value='true')
    travel = q.fn(FLOW + 'CompleteCurrentStageWithFailure', Owner=q.ref('ExitActor'))
    failure_callback(q, travel, queue_name)
    q.chain(finished, started, duplicate)
    wire(duplicate, 'else', request, 'execute')
    q.chain(request, travel)
    q.comment('Sequence completion requests travel as its exit actor and reports rejection back to this director.')

    q = Graph(BP.get_graph(bp, queue_name), 340, 0)
    defer = q.fn(SYSTEM + 'K2_SetTimer', FunctionName=recover_name, Time='0.001', bLooping='false')
    q.chain(entry(q), defer)
    q.comment('Leave Sequencer’s OnFinished callback before stopping and destroying the sequence player.')

    q = Graph(BP.get_graph(bp, recover_name), 340, 0)
    started_gate = q.branch(q.ref('Started'))
    disarm = q.set('Started', value='false')
    player_gate = q.branch(valid(q, q.ref('SequencePlayer')))
    q.chain(entry(q), started_gate, disarm, player_gate)
    active_camera = result(q.fn(LEVEL_PLAYER + 'GetActiveCameraComponent', target=q.ref('SequencePlayer')))
    active_gate = q.branch(valid(q, active_camera))
    camera_owner = result(q.fn(COMPONENT + 'GetOwner', target=active_camera))
    remember_camera = q.set('StairCameraAtFailure', source=camera_owner)
    stop = q.fn(MOVIE + 'Stop', target=q.ref('SequencePlayer'))
    q.chain(player_gate, active_gate, remember_camera, stop)
    wire(active_gate, 'else', stop, 'execute')

    controller_gate = q.branch(valid(q, q.ref('StairController')))
    current_view = result(q.fn(CONTROLLER + 'GetViewTarget', target=q.ref('StairController')))
    same_view = equal(q, current_view, q.ref('StairCameraAtFailure'))
    views_valid = both(q, valid(q, q.ref('StairPreviousView')), valid(q, q.ref('StairCameraAtFailure')))
    owned_view = q.branch(both(q, views_valid, same_view))
    restore_view = q.fn(PLAYER + 'SetViewTargetWithBlend', target=q.ref('StairController'),
                        NewViewTarget=q.ref('StairPreviousView'), BlendTime='0.000000')
    actor_gate = q.branch(valid(q, q.ref('StairSequenceActor')))
    destroy = q.fn(ACTOR + 'K2_DestroyActor', target=q.ref('StairSequenceActor'))
    camera_gate = q.branch(both(q, valid(q, q.ref('StairCamera')), q.ref('StairCameraTickWasEnabled')))
    restore_tick = q.fn(ACTOR + 'SetActorTickEnabled', target=q.ref('StairCamera'), bEnabled='true')
    exit_gate = q.branch(valid(q, q.ref('ExitActor')))
    exit_recover = q.fn(bp_function(EXIT, 'RecoverFailedStageExit'), target=q.ref('ExitActor'))
    clear_refs = clear(q, 'SequencePlayer', 'StairSequenceActor', 'StairController', 'StairPreviousView',
                       'StairCamera', 'StairCameraAtFailure')
    reset_travel = q.set('StairTravelRequested', value='false')
    rearm = q.fn(ACTOR + 'SetActorTickEnabled', bEnabled='true')
    q.chain(stop, controller_gate, owned_view, restore_view, actor_gate, destroy, camera_gate, restore_tick,
            exit_gate, exit_recover, *clear_refs, reset_travel, rearm)
    for bypass, resume in ((player_gate, actor_gate), (controller_gate, actor_gate), (owned_view, actor_gate),
                           (actor_gate, camera_gate), (camera_gate, exit_gate), (exit_gate, clear_refs[0])):
        wire(bypass, 'else', resume, 'execute')
    q.comment('Stop only the owned sequence, recover its view and camera tick, and then rearm both triggers.')
    compile_bp(bp)


def snapshot(blueprints):
    return {path: graph_rows(bp) for path, bp in blueprints.items()}


def assert_connection(nodes, a, ap, b, bp):
    assert pin(nodes[b], bp) in pin(nodes[a], ap, True).list_connected_pins(), (a, ap, b, bp)


def assert_route(blueprints):
    for path, graph_name, callback, owner_type in (
        (EXIT, 'CompleteTransition', 'RecoverFailedStageExit', 'K2Node_Self'),
        (DIRECTOR, 'EventGraph', 'QueueFailedStairRecovery', 'K2Node_VariableGet'),
    ):
        g = BP.get_graph(blueprints[path], graph_name)
        calls = [n for n in BP.get_node_infos(BP.find_nodes(g)) if n.type_id.endswith('|CompleteCurrentStageWithFailure')]
        assert len(calls) == 1, (path, calls)
        travel = calls[0].node
        owners = pin(travel, 'Owner').list_connected_pins()
        assert len(owners) == 1 and owners[0].get_owning_node().get_class().get_name() == owner_type
        if path == DIRECTOR:
            assert owners[0].get_pin_name() == 'ExitActor'
        delegates = pin(travel, 'Failure').list_connected_pins()
        assert len(delegates) == 1
        assert BP.get_create_event_function(delegates[0].get_owning_node()) == callback
    g = BP.get_graph(blueprints[DIRECTOR], 'EventGraph')
    old = {node.get_name(): node for node in BP.find_nodes(g)}
    assert_connection(old, 'K2Node_CallFunction_5', 'then', 'K2Node_CallFunction_7', 'execute')
    assert_connection(old, 'K2Node_AddDelegate_1', 'then', 'K2Node_CallFunction_9', 'execute')
    assert_connection(old, 'K2Node_CustomEvent_0', 'OutputDelegate', 'K2Node_AddDelegate_1', 'Delegate')
    assert abs(float(pin(old['K2Node_CallFunction_5'], 'Duration').get_pin_value()) - .55) < 1.e-6
    assert SEQUENCE in str(pin(old['K2Node_CallFunction_8'], 'LevelSequence').get_pin_value())


def backup(assets_to_backup):
    for package, digest in assets_to_backup.items():
        path = content_file(package)
        target = OUT / 'Backup' / path.relative_to(ROOT)
        if target.exists():
            assert file_hash(target) == digest, target
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            assert file_hash(target) == digest, target


def author(blueprints):
    before = read_report('probe')
    owned_before = hashes(OWNED)
    assert owned_before == {path: before['hashes'][path] for path in OWNED}, 'Probe is stale for an edited Blueprint'
    assert snapshot(blueprints) == {path: before['assets'][path]['graphs'] for path in OWNED}
    unchanged = hashes(PRESERVED)
    backup(owned_before)
    author_exit(blueprints[EXIT])
    author_director(blueprints[DIRECTOR])
    assert_route(blueprints)
    expected = snapshot(blueprints)
    for path, bp in blueprints.items():
        assert u.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), path
    assert hashes(PRESERVED) == unchanged
    write_report('author', {'graphs': expected, 'before': owned_before, 'after': hashes(OWNED), 'preserved': unchanged})
    u.log('CATRUN_TUTORIAL_TRAVEL_FAILURE_AUTHOR_OK')


def normalize_camera_blend_literal(graphs):
    # UE serializes this float's authored zero with six fractional digits.
    recover = graphs[DIRECTOR]['RecoverFailedStairPresentation']
    camera = [n for n in recover if n['type'] == 'Game|Player|SetViewTargetWithBlend']
    assert len(camera) == 1
    blend = next(p for p in camera[0]['inputs'] if p['name'] == 'BlendTime')
    assert blend['type'] == 'Float (single-precision)' and blend['links'] == '[]'
    if blend['value'] == '0':
        blend['value'] = '0.000000'
    return graphs


def audit(blueprints, resave_metadata=False):
    expected = read_report('author')
    has_metadata_save = (OUT / 'metadata_resave.json').exists()
    assert not resave_metadata or not has_metadata_save, 'Comment metadata was already resaved'
    owned_hashes = expected['after']
    if has_metadata_save:
        metadata = read_report('metadata_resave')
        assert metadata['before'] == owned_hashes
        owned_hashes = metadata['after']
    assert hashes(OWNED) == owned_hashes
    assert hashes(PRESERVED) == expected['preserved']
    actual = snapshot(blueprints)
    write_report('cold_graphs', actual)
    assert normalize_camera_blend_literal(actual) == normalize_camera_blend_literal(expected['graphs']), (
        'Cold graph contents differ from the authored graphs')
    assert_route(blueprints)
    for bp in blueprints.values():
        compile_bp(bp)
    assert hashes(OWNED) == owned_hashes
    assert hashes(PRESERVED) == expected['preserved']
    if resave_metadata:
        for path, bp in blueprints.items():
            assert u.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), path
        assert hashes(PRESERVED) == expected['preserved']
        write_report('metadata_resave', {'before': owned_hashes, 'after': hashes(OWNED)})
        u.log('CATRUN_TUTORIAL_TRAVEL_FAILURE_METADATA_RESAVE_OK')
        return
    write_report('audit', {'compiled': list(blueprints), 'hashes': hashes(OWNED + PRESERVED), 'cold_graphs_match': True})
    u.log('CATRUN_TUTORIAL_TRAVEL_FAILURE_AUDIT_OK')


mode = os.environ.get('CATRUN_TUTORIAL_REPAIR_MODE', 'probe')
assert mode in ('probe', 'author', 'audit', 'resave_metadata'), mode
blueprints = {path: asset(path) for path in OWNED}
if mode in ('audit', 'resave_metadata'):
    audit(blueprints, resave_metadata=mode == 'resave_metadata')
else:
    {'probe': probe, 'author': author}[mode](blueprints)
