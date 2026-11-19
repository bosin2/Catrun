"""Author the Stage2 arrival Blueprint's route, lease and playback lifecycle."""

import re

import unreal as u
from editor_toolset.toolsets.actor import ActorTools
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from menu_graph import Graph, compile_bp, literal, pin, wire


FLOW = '/Script/Catrun.CatrunLevelFlowLibrary:'
LEASE = '/Script/Catrun.CatrunExitTransitionComponent:'
PLAYER = '/Script/MovieScene.MovieSceneSequencePlayer:'
SEQ_ACTOR = '/Script/LevelSequence.LevelSequenceActor:'
SEQ_PLAYER = '/Script/LevelSequence.LevelSequencePlayer:'
SYSTEM = '/Script/Engine.KismetSystemLibrary:'
GAMEPLAY = '/Script/Engine.GameplayStatics:'
MATH = '/Script/Engine.KismetMathLibrary:'
CONTROLLER = '/Script/Engine.Controller:'
PC = '/Script/Engine.PlayerController:'
COMPONENT = '/Script/Engine.ActorComponent:'
FRAME_TO_SECONDS = '/Script/TimeManagement.TimeManagementBlueprintLibrary:Conv_QualifiedFrameTimeToSeconds'
PAWN_TAG = 'CatrunArrivalPawn'


def bind_event(graph, delegate, player, event):
    candidates = BP.find_node_types(graph.g, delegate)
    expected = 'bindeventto' + delegate.lower()
    matches = [name for name in set(candidates)
               if re.sub(r'[^a-z0-9]', '', name.lower()) == 'sequencerplayer' + expected]
    assert len(matches) == 1, (delegate, list(candidates))
    node = graph.placed(BP.create_node(graph.g, matches[0], u.IntPoint(graph.x, graph.y),
                                       u.MovieSceneSequencePlayer.static_class()))
    wire(*player, node, 'self')
    wire(event, 'OutputDelegate', node, 'Delegate')
    return node


def author_director(package, handoff_seconds, blend_seconds):
    folder, name = package.rsplit('/', 1)
    bp = BP.create(folder, name, u.Actor.static_class())
    ActorTools.add_component(bp, u.CatrunExitTransitionComponent.static_class(), 'ExitTransition')
    for name, cls in (('CinematicActor', u.LevelSequenceActor), ('SequencePlayer', u.LevelSequencePlayer),
                      ('OwningController', u.PlayerController), ('ExpectedGameplayView', u.Actor),
                      ('GameplayViewTarget', u.Actor), ('OutgoingView', u.Actor)):
        BP.add_object_variable(bp, name, cls.static_class())
    for name in ('ReadinessOpen', 'Attempted', 'Started', 'Playing', 'HandoffStarted', 'Finished', 'EndingWorld'):
        BP.add_variable(bp, name, 'bool')
    for name in ('CinematicActor', 'ExpectedGameplayView'):
        BP.set_variable_instance_editable(bp, name, True)

    event_names = ('ReceiveBeginPlay', 'TryStartArrival', 'MonitorArrival', 'BeginHandoff',
                   'SequenceFinished', 'FinishArrival', 'SequenceStopped', 'AbortArrival', 'ReceiveEndPlay')
    events = {name: BP.add_event(bp, name, u.IntPoint(0, index * 950))
              for index, name in enumerate(event_names)}
    compile_bp(bp)
    graph = BP.get_graph(bp, 'EventGraph')
    owner = bp.generated_class().get_path_name() + ':'

    def lane(name):
        return Graph(graph, 360, event_names.index(name) * 950), events[name]

    def call(q, name):
        return q.fn(owner + name)

    def lease(q, name, **inputs):
        return q.fn(LEASE + name, target=q.ref('ExitTransition'), **inputs)

    def player(q, name, **inputs):
        return q.fn(PLAYER + name, target=q.ref('SequencePlayer'), **inputs)

    def timer(q, event, duration, looping=False):
        return q.fn(SYSTEM + 'K2_SetTimer', FunctionName=event, Time=str(duration),
                    bLooping=str(looping).lower())

    def clear(q, event):
        return q.fn(SYSTEM + 'K2_ClearTimer', FunctionName=event)

    def valid(q, reference):
        return q.fn(SYSTEM + 'IsValid', Object=reference), 'ReturnValue'

    def equal(q, first, second):
        return q.fn(MATH + 'EqualEqual_ObjectObject', A=first, B=second), 'ReturnValue'

    def view(q, controller):
        return q.fn(CONTROLLER + 'GetViewTarget', target=controller), 'ReturnValue'

    def branch(q, previous, condition, output='then'):
        node = q.branch(condition)
        wire(previous, output, node, 'execute')
        return node

    # The map owns one director per world. The guard also closes repeated calls to BeginPlay.
    q, event = lane('ReceiveBeginPlay')
    once = branch(q, event, q.ref('Attempted'))
    attempted = q.set('Attempted', value='true')
    wire(once, 'else', attempted, 'execute')
    qualified = branch(q, attempted, (q.fn(FLOW + 'IsStage2PortalArrival'), 'ReturnValue'))
    opened = q.set('ReadinessOpen', value='true')
    wire(qualified, 'then', opened, 'execute')
    q.chain(opened, timer(q, 'TryStartArrival', .10, True), timer(q, 'AbortArrival', 2.0))
    q.comment('Qualified portal travel opens a two-second readiness window for this world.')

    q, event = lane('TryStartArrival')
    waiting = branch(q, event, q.ref('ReadinessOpen'))
    has_actor = branch(q, waiting, valid(q, q.ref('CinematicActor')))
    get_player = q.fn(SEQ_ACTOR + 'GetSequencePlayer', target=q.ref('CinematicActor'))
    has_player = branch(q, has_actor, valid(q, (get_player, 'ReturnValue')))
    pc = q.fn(GAMEPLAY + 'GetPlayerController', PlayerIndex='0'), 'ReturnValue'
    has_pc = branch(q, has_player, valid(q, pc))
    actual_view = view(q, pc)
    has_view = branch(q, has_pc, valid(q, q.ref('ExpectedGameplayView')))
    correct_view = branch(q, has_view, equal(q, actual_view, q.ref('ExpectedGameplayView')))
    gameplay_camera = q.fn('/Script/Engine.Actor:GetComponentByClass', target=actual_view,
                           ComponentClass='/Script/Engine.CameraComponent')
    profile = q.fn(FLOW + 'ApplyStageCameraProfile', Camera=(gameplay_camera, 'ReturnValue'))
    wire(correct_view, 'then', profile, 'execute')
    profiled = branch(q, profile, (profile, 'ReturnValue'))
    pawn = q.fn(GAMEPLAY + 'GetPlayerPawn', PlayerIndex='0'), 'ReturnValue'
    acquire = lease(q, 'AcquireExitLease', Pawn=pawn)
    wire(profiled, 'then', acquire, 'execute')
    acquired = branch(q, acquire, (acquire, 'ReturnValue'))
    closed = q.set('ReadinessOpen', value='false')
    wire(acquired, 'then', closed, 'execute')
    set_pc = q.set('OwningController', source=pc)
    set_view = q.set('GameplayViewTarget', source=actual_view)
    set_player = q.set('SequencePlayer', source=(get_player, 'ReturnValue'))
    bound = q.fn(SEQ_ACTOR + 'AddBindingByTag', target=q.ref('CinematicActor'),
                 BindingTag=PAWN_TAG, Actor=pawn, bAllowBindingsFromAsset='false')
    stopped = bind_event(q, 'OnStop', q.ref('SequencePlayer'), events['SequenceStopped'])
    finished = bind_event(q, 'OnFinished', q.ref('SequencePlayer'), events['SequenceFinished'])
    q.chain(closed, clear(q, 'TryStartArrival'), clear(q, 'AbortArrival'), set_pc, set_view, set_player, bound,
            stopped, finished, q.set('Started', value='true'), q.set('Playing', value='true'),
            timer(q, 'MonitorArrival', .05, True), timer(q, 'AbortArrival', handoff_seconds + blend_seconds + 2),
            player(q, 'Play'))
    q.comment('Wait for the real camera and grounded pawn, then override the single visibility binding.')

    q, event = lane('MonitorArrival')
    active = branch(q, event, q.ref('Playing'))
    abort = call(q, 'AbortArrival')
    owned = branch(q, active, (lease(q, 'HasExitLease'), 'ReturnValue'))
    has_player = branch(q, owned, valid(q, q.ref('SequencePlayer')))
    has_pc = branch(q, has_player, valid(q, q.ref('OwningController')))
    for check in (owned, has_player, has_pc):
        wire(check, 'else', abort, 'execute')
    handing_off = branch(q, has_pc, q.ref('HandoffStarted'))
    now = view(q, q.ref('OwningController'))
    returning_view = q.fn(MATH + 'BooleanOR', A=equal(q, now, q.ref('GameplayViewTarget')),
                          B=equal(q, now, q.ref('OutgoingView'))), 'ReturnValue'
    returning = branch(q, handing_off, returning_view)
    wire(returning, 'else', abort, 'execute')
    cam = q.fn(SEQ_PLAYER + 'GetActiveCameraComponent', target=q.ref('SequencePlayer')), 'ReturnValue'
    has_camera = branch(q, handing_off, valid(q, cam), 'else')
    camera_owner = q.fn(COMPONENT + 'GetOwner', target=cam), 'ReturnValue'
    remembered = lease(q, 'RememberOwnedViewTarget', ViewTarget=camera_owner)
    wire(has_camera, 'then', remembered, 'execute')
    cache_outgoing = q.set('OutgoingView', source=camera_owner)
    q.chain(remembered, cache_outgoing)
    owns_view = branch(q, cache_outgoing, equal(q, now, camera_owner))
    wire(owns_view, 'else', abort, 'execute')
    position = player(q, 'GetCurrentTime'), 'ReturnValue'
    seconds = q.fn(FRAME_TO_SECONDS, InFrameTime=position), 'ReturnValue'
    overdue = branch(q, has_camera, (q.fn(MATH + 'GreaterEqual_DoubleDouble', A=seconds, B='.25'), 'ReturnValue'), 'else')
    wire(overdue, 'then', abort, 'execute')
    handoff = branch(q, owns_view, (q.fn(MATH + 'GreaterEqual_DoubleDouble', A=seconds, B=str(handoff_seconds)), 'ReturnValue'))
    wire(handoff, 'then', call(q, 'BeginHandoff'), 'execute')
    q.comment('Watch lease and view ownership. Use Sequencer time to enter the handoff at ten seconds.')

    q, event = lane('BeginHandoff')
    active = branch(q, event, q.ref('Playing'))
    once = branch(q, active, q.ref('HandoffStarted'))
    has_view = branch(q, once, valid(q, q.ref('GameplayViewTarget')), 'else')
    wire(has_view, 'else', call(q, 'AbortArrival'), 'execute')
    blending = q.set('HandoffStarted', value='true')
    wire(has_view, 'then', blending, 'execute')
    disable_cuts = player(q, 'SetDisableCameraCuts', bInDisableCameraCuts='true')
    blend = q.fn(PC + 'SetViewTargetWithBlend', target=q.ref('OwningController'),
                 NewViewTarget=q.ref('GameplayViewTarget'), BlendTime=str(blend_seconds),
                 BlendFunc='VTBlend_Cubic', bLockOutgoing='true')
    # Allow the camera manager one update after its blend time before removing the outgoing visual.
    q.chain(blending, disable_cuts, blend, timer(q, 'FinishArrival', blend_seconds + .06))
    q.comment('Keep the owned cat, camera and lease alive through the cubic gameplay view blend.')

    q, event = lane('SequenceFinished')
    active = branch(q, event, q.ref('Playing'))
    handoff = branch(q, active, q.ref('HandoffStarted'))
    wire(handoff, 'else', call(q, 'AbortArrival'), 'execute')
    q.comment('PauseAtEnd retains the final cinematic frame while a normal blend finishes.')

    q, event = lane('FinishArrival')
    active = branch(q, event, q.ref('Playing'))
    handoff = branch(q, active, q.ref('HandoffStarted'))
    owned = branch(q, handoff, (lease(q, 'HasExitLease'), 'ReturnValue'))
    has_pc = branch(q, owned, valid(q, q.ref('OwningController')))
    returned = branch(q, has_pc, equal(q, view(q, q.ref('OwningController')), q.ref('GameplayViewTarget')))
    done = q.set('Finished', value='true')
    wire(returned, 'then', done, 'execute')
    cleanup = call(q, 'AbortArrival')
    wire(done, 'then', cleanup, 'execute')
    for check in (owned, has_pc, returned):
        wire(check, 'else', cleanup, 'execute')

    q, event = lane('SequenceStopped')
    active = branch(q, event, q.ref('Playing'))
    owned = branch(q, active, (lease(q, 'HasExitLease'), 'ReturnValue'))
    has_pc = branch(q, owned, valid(q, q.ref('OwningController')))
    has_view = branch(q, has_pc, valid(q, q.ref('GameplayViewTarget')))
    outgoing_live = branch(q, has_view, valid(q, q.ref('OutgoingView')))
    # A direct Stop can despawn its view target before the OnStop callback. Unreal
    # then falls back to the controller or pawn. Preserve any separate live camera.
    current = view(q, q.ref('OwningController'))
    pawn = q.fn(GAMEPLAY + 'GetPlayerPawn', PlayerIndex='0'), 'ReturnValue'
    fallback = q.fn(MATH + 'BooleanOR', A=equal(q, current, q.ref('OwningController')),
                    B=equal(q, current, pawn)), 'ReturnValue'
    was_fallback = branch(q, outgoing_live, fallback, 'else')
    restore = q.fn(PC + 'SetViewTargetWithBlend', target=q.ref('OwningController'),
                   NewViewTarget=q.ref('GameplayViewTarget'), BlendTime='0')
    wire(was_fallback, 'then', restore, 'execute')
    cleanup = call(q, 'AbortArrival')
    for check in (owned, has_pc, has_view, was_fallback):
        wire(check, 'else', cleanup, 'execute')
    wire(outgoing_live, 'then', cleanup, 'execute')
    q.chain(restore, cleanup)

    q, event = lane('AbortArrival')
    closed = q.set('ReadinessOpen', value='false')
    wire(event, 'then', closed, 'execute')
    last = q.chain(closed, *(clear(q, name) for name in
                             ('TryStartArrival', 'AbortArrival', 'MonitorArrival', 'FinishArrival')))
    active = branch(q, last, q.ref('Playing'))
    inactive = q.set('Playing', value='false')
    wire(active, 'then', inactive, 'execute')
    teardown = branch(q, inactive, q.ref('EndingWorld'))
    can_query = branch(q, teardown, valid(q, q.ref('SequencePlayer')), 'else')
    camera = q.fn(SEQ_PLAYER + 'GetActiveCameraComponent', target=q.ref('SequencePlayer')), 'ReturnValue'
    camera_alive = branch(q, can_query, valid(q, camera))
    camera_owner = q.fn(COMPONENT + 'GetOwner', target=camera), 'ReturnValue'
    remember = lease(q, 'RememberOwnedViewTarget', ViewTarget=camera_owner)
    wire(camera_alive, 'then', remember, 'execute')
    released = lease(q, 'ReleaseExitLease', bRestoreStart='false')
    wire(can_query, 'else', released, 'execute')
    wire(camera_alive, 'else', released, 'execute')
    q.chain(remember, released)
    has_player = branch(q, released, valid(q, q.ref('SequencePlayer')))
    wire(teardown, 'then', has_player, 'execute')
    disable = player(q, 'SetDisableCameraCuts', bInDisableCameraCuts='true')
    wire(has_player, 'then', disable, 'execute')
    stopped = q.chain(disable, player(q, 'Stop'))
    has_actor = branch(q, stopped, valid(q, q.ref('CinematicActor')))
    reset = q.fn(SEQ_ACTOR + 'ResetBindings', target=q.ref('CinematicActor'))
    wire(has_actor, 'then', reset, 'execute')
    q.comment('Clear owned timers and end playback once. Stop restores the pawn visibility and despawns visuals.')

    q, event = lane('ReceiveEndPlay')
    destroyed = q.fn(MATH + 'EqualEqual_ByteByte', A=(event, 'EndPlayReason'), B='0'), 'ReturnValue'
    removed = q.fn(MATH + 'EqualEqual_ByteByte', A=(event, 'EndPlayReason'), B='3'), 'ReturnValue'
    surviving = q.fn(MATH + 'BooleanOR', A=destroyed, B=removed), 'ReturnValue'
    ending = q.fn(MATH + 'Not_PreBool', A=surviving), 'ReturnValue'
    mark = q.set('EndingWorld', source=ending)
    wire(event, 'then', mark, 'execute')
    q.chain(mark, call(q, 'AbortArrival'))
    q.comment('For world teardown, the lease component handles native EndPlay after the visual stop.')

    compile_bp(bp)
    return bp


def audit_graph(bp):
    assert bp.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE
    graph = BP.get_graph(bp, 'EventGraph')
    nodes = BP.get_node_infos(BP.find_nodes(graph))
    types = sorted(str(info.type_id) for info in nodes)
    normalized = [re.sub(r'[^a-z0-9]', '', name.lower()) for name in types]
    for token in ('BeginPlay', 'IsStage2PortalArrival', 'AcquireExitLease', 'ReleaseExitLease',
                  'AddBindingByTag', 'SetDisableCameraCuts', 'SetViewTargetWithBlend', 'EndPlay'):
        assert any(token.lower() in name for name in normalized), ('Missing director node', token, types)
    assert all('CommitExitTravel' not in name and 'RequestExitCheckpointSave' not in name for name in types)
    return {'status': str(bp.get_editor_property('status')), 'nodes': types}


def arrival_timing(bp, update=False):
    """Identify the monitor threshold and active-play watchdog, leaving readiness alone."""
    graph = BP.get_graph(bp, 'EventGraph')
    infos = BP.get_node_infos(BP.find_nodes(graph))
    thresholds = [i.node for i in infos if str(i.type_id).endswith('float>=float')
                  and float(pin(i.node, 'B').get_pin_value()) > 1.]
    watchdogs = [i.node for i in infos if str(i.type_id).endswith('SetTimerbyFunctionName')
                 and str(pin(i.node, 'FunctionName').get_pin_value()).strip('"') == 'AbortArrival'
                 and float(pin(i.node, 'Time').get_pin_value()) > 2.]
    assert len(thresholds) == len(watchdogs) == 1
    fields = [(thresholds[0], 'B', 10., 14.8), (watchdogs[0], 'Time', 14., 18.8)]
    values = [float(pin(node, name).get_pin_value()) for node, name, _, _ in fields]
    assert all(abs(value - old) < .001 for value, (_, _, old, _) in zip(values, fields)) or all(
        abs(value - new) < .001 for value, (_, _, _, new) in zip(values, fields)), values
    if update and abs(values[0] - 10.) < .001:
        bp.modify()
        for node, name, _, new in fields:
            literal(node, name, new)
        compile_bp(bp)
        return arrival_timing(bp)
    return values
