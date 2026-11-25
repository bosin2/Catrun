"""Root-only Stage3 D1/D2 cosmetic impact preparation. Never saves packages.

Call prepare() once in Stage3 editor, inspect/compile, then root explicitly saves.
Retry in a fresh package generation via CATRUN_GATE_FX_GENERATION=Run02.
No production C++, old BP, gameplay actor or camera property is written.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.actor import ActorTools

ROOT = Path(u.Paths.project_dir()).resolve()
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'Saved/Stage3GateFXRevision20261125'
OWNER = 'Stage3GateFXRevision20261125'
MATH = '/Script/Engine.KismetMathLibrary:'
SYSTEM = '/Script/Engine.KismetSystemLibrary:'
REVEAL = '/Script/Catrun.CatrunPuzzleRevealComponent'
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import Graph, compile_bp, entry, wire, editor, pin


def special(graph, suffix, cls=None):
    choices = list(dict.fromkeys(str(n) for n in editor(graph).list_available_nodes([])
                                if str(n).endswith('|' + suffix)))
    assert len(choices) == 1, (suffix, choices)
    result = BP.create_node(graph, choices[0], u.IntPoint(0, 0), cls)
    assert result
    return result


def author(folder, dust, rumble):
    name = 'BP_S3GateImpact'
    path = folder + '/' + name
    assert not u.EditorAssetLibrary.does_asset_exist(path), path
    bp = BP.create(folder, name, u.Actor.static_class())
    u.EditorAssetLibrary.set_metadata_tag(bp, 'Stage3GateFXOwner', OWNER)
    for key, cls in {'Director': u.CatrunStatuePuzzle, 'Gate': u.Actor,
                     'Reveal': u.CatrunPuzzleRevealComponent,
                     'RumbleMID': u.MaterialInstanceDynamic}.items():
        BP.add_object_variable(bp, key, cls.static_class())
    variables = {'PuzzleId': 'name', 'ExpectedOpenZ': 'float', 'ImpactAge': 'float',
                 'RumbleStrength': 'float', 'OriginSessionId': 'int', 'LastRevision': 'int',
                 'ImpactCount': 'int', 'Armed': 'bool', 'SessionActive': 'bool', 'DustActive': 'bool'}
    for key, kind in variables.items():
        BP.add_variable(bp, key, kind)
    for key in ('Director', 'Gate', 'Reveal', 'PuzzleId', 'ExpectedOpenZ', 'RumbleStrength'):
        BP.set_variable_instance_editable(bp, key, True)
    # A scene root keeps the dust pool's anchor fixed at the authored floor.
    ActorTools.add_component(bp, u.SceneComponent.static_class(), 'ImpactRoot')
    pp = ActorTools.add_component(bp, u.PostProcessComponent.static_class(), 'ImpactPostProcess')
    pp.set_editor_property('unbound', True)
    pp.set_editor_property('blend_weight', 1.)
    for index in range(8):
        c = ActorTools.add_component(bp, u.StaticMeshComponent.static_class(), 'Dust%02d' % index)
        c.set_static_mesh(u.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Plane'))
        c.set_material(0, dust)
        c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        for key, value in {'cast_shadow': False, 'hidden_in_game': True,
                           'generate_overlap_events': False}.items():
            c.set_editor_property(key, value)
        c.set_editor_property('relative_location', u.Vector(-80 + index * 23, (-1 if index % 2 else 1) * 7, 14))
        c.set_editor_property('relative_rotation', u.Rotator(pitch=35, yaw=-135, roll=0))
        c.set_editor_property('relative_scale3d', u.Vector(.28, .32, .28))
    graph = BP.get_graph(bp, 'EventGraph')
    # Remove only automatically created unconnected events on this fresh BP.
    initial = [r.node for r in BP.get_node_infos(BP.find_nodes(graph))]
    if initial:
        editor(graph).remove_nodes(initial)
    for fname in ('StartDust', 'StopDust', 'ClearImpact', 'InitializeImpact'):
        BP.add_function_graph(bp, fname)
    fg = BP.add_function_graph(bp, 'UpdateImpact')
    BP.add_function_param(fg, 'DeltaSeconds', 'float', True)
    for fname, enum_name, param in (('HandlePhase', 'Phase', 'SessionId'),
                                    ('HandlePuzzle', 'Event', 'Revision')):
        fg = BP.add_function_graph(bp, fname)
        BP.add_function_param(fg, 'PuzzleId', 'name', True)
        if enum_name == 'Phase':
            probe = editor(graph).add_get_member_variable_node('Phase', REVEAL)
            typ = pin(probe, 'Phase', True).get_pin_type()
        else:
            probe = special(graph, 'SwitchonECatrunStatueEvent')
            typ = pin(probe, 'Selection').get_pin_type()
        assert editor(fg).add_graph_input_parameter(enum_name, typ, '')
        editor(graph).remove_nodes([probe])
        BP.add_function_param(fg, param, 'int', True)
    compile_bp(bp)
    own = path + '.' + name + '_C:'

    def new(fname):
        q = Graph(BP.get_graph(bp, fname))
        return q, entry(q)

    def call(q, fname):
        return q.fn(own + fname)

    def valid(q, last, member, cleanup=False):
        result = q.fn(SYSTEM + 'IsValid', Object=q.ref(member))
        branch = q.branch((result, 'ReturnValue'))
        q.chain(last, branch)
        if cleanup:
            wire(branch, 'else', call(q, 'ClearImpact'), 'execute')
        return branch

    def session(q, last, cleanup=False):
        branch = q.branch(q.ref('SessionActive'))
        q.chain(last, branch)
        if cleanup:
            wire(branch, 'else', call(q, 'ClearImpact'), 'execute')
        last = valid(q, branch, 'Reveal', cleanup)
        sid = q.get('SessionId', REVEAL)
        wire(*q.ref('Reveal'), sid, 'self')
        same = q.fn(MATH + 'EqualEqual_IntInt', A=(sid, 'SessionId'), B=q.ref('OriginSessionId'))
        branch = q.branch((same, 'ReturnValue'))
        q.chain(last, branch)
        if cleanup:
            wire(branch, 'else', call(q, 'ClearImpact'), 'execute')
        return branch

    def scalar(q, value):
        return q.fn('/Script/Engine.MaterialInstanceDynamic:SetScalarParameterValue',
                    target=q.ref('RumbleMID'), ParameterName='Rumble', Value=value)

    for fname, active in (('StartDust', True), ('StopDust', False)):
        q, start = new(fname)
        last = q.chain(start, q.set('ImpactAge', value=0), q.set('DustActive', value=str(active).lower()))
        if active:
            add = q.fn(MATH + 'Add_IntInt', A=q.ref('ImpactCount'), B=1)
            last = q.chain(last, q.set('ImpactCount', source=(add, 'ReturnValue')))
        for index in range(8):
            member = 'Dust%02d' % index
            if active:
                time = q.fn('/Script/Engine.GameplayStatics:GetTimeSeconds')
                settime = q.fn('/Script/Engine.MeshComponent:SetScalarParameterValueOnMaterials',
                               target=q.ref(member), ParameterName='StartTime', ParameterValue=(time, 'ReturnValue'))
                last = q.chain(last, settime)
            hide = q.fn('/Script/Engine.SceneComponent:SetHiddenInGame', target=q.ref(member),
                        NewHidden=str(not active).lower(), bPropagateToChildren='false')
            last = q.chain(last, hide)
        last = valid(q, last, 'RumbleMID')
        q.chain(last, scalar(q, q.ref('RumbleStrength') if active else 0))
    q, start = new('ClearImpact')
    q.chain(start, q.set('Armed', value='false'), q.set('SessionActive', value='false'), call(q, 'StopDust'))
    q, start = new('InitializeImpact')
    mid = q.fn('/Script/Engine.KismetMaterialLibrary:CreateDynamicMaterialInstance', Parent=rumble.get_path_name())
    last = q.chain(start, mid, q.set('RumbleMID', source=(mid, 'ReturnValue')))
    last = valid(q, last, 'RumbleMID')
    blend = q.fn('/Script/Engine.PostProcessComponent:AddOrUpdateBlendable', target=q.ref('ImpactPostProcess'),
                 InBlendableObject=q.ref('RumbleMID'), InWeight=1)
    q.chain(last, blend, call(q, 'ClearImpact'))

    q, start = new('HandlePhase')
    same = q.fn(MATH + 'EqualEqual_NameName', A=(start, 'PuzzleId'), B=q.ref('PuzzleId'))
    mine = q.branch((same, 'ReturnValue'))
    q.chain(start, mine)
    last = valid(q, mine, 'Reveal')
    current = q.get('SessionId', REVEAL)
    wire(*q.ref('Reveal'), current, 'self')
    same = q.fn(MATH + 'EqualEqual_IntInt', A=(start, 'SessionId'), B=(current, 'SessionId'))
    check = q.branch((same, 'ReturnValue'))
    switch = special(q.g, 'SwitchonECatrunPuzzleRevealPhase')
    q.chain(last, check, switch)
    wire(start, 'Phase', switch, 'Selection')
    clear = call(q, 'ClearImpact')
    wire(switch, 'ToGate', clear, 'execute')
    q.chain(clear, q.set('OriginSessionId', source=(start, 'SessionId')), q.set('SessionActive', value='true'))
    wire(switch, 'Inactive', call(q, 'ClearImpact'), 'execute')
    # Returning deliberately does not cancel its independent one-shot age.

    q, start = new('HandlePuzzle')
    same = q.fn(MATH + 'EqualEqual_NameName', A=(start, 'PuzzleId'), B=q.ref('PuzzleId'))
    mine = q.branch((same, 'ReturnValue'))
    switch = special(q.g, 'SwitchonECatrunStatueEvent')
    q.chain(start, mine, switch)
    wire(start, 'Event', switch, 'Selection')
    wire(switch, 'Reset', call(q, 'ClearImpact'), 'execute')
    # Only an actual opening in the current reveal session arms completion.
    opening = q.set('Armed', value='false')
    wire(switch, 'GateOpening', opening, 'execute')
    ready = session(q, opening)
    q.chain(ready, q.set('LastRevision', source=(start, 'Revision')), q.set('Armed', value='true'))
    armed = q.branch(q.ref('Armed'))
    wire(switch, 'Completed', armed, 'execute')
    ready = session(q, armed)
    same = q.fn(MATH + 'EqualEqual_IntInt', A=(start, 'Revision'), B=q.ref('LastRevision'))
    check = q.branch((same, 'ReturnValue'))
    q.chain(ready, check)
    ready = valid(q, check, 'Gate')
    position = q.fn('/Script/Engine.Actor:K2_GetActorLocation', target=q.ref('Gate'))
    xyz = q.fn(MATH + 'BreakVector', InVec=(position, 'ReturnValue'))
    limit = q.fn(MATH + 'Add_FloatFloat', A=q.ref('ExpectedOpenZ'), B=.5)
    reached = q.fn(MATH + 'LessEqual_DoubleDouble', A=(xyz, 'Z'), B=(limit, 'ReturnValue'))
    check = q.branch((reached, 'ReturnValue'))
    q.chain(ready, check, q.set('Armed', value='false'), call(q, 'StartDust'))

    q, start = new('UpdateImpact')
    active = q.branch(q.ref('DustActive'))
    q.chain(start, active)
    last = session(q, active, True)
    last = valid(q, last, 'Gate', True)
    last = valid(q, last, 'RumbleMID', True)
    add = q.fn(MATH + 'Add_FloatFloat', A=q.ref('ImpactAge'), B=(start, 'DeltaSeconds'))
    age = q.set('ImpactAge', source=(add, 'ReturnValue'))
    q.chain(last, age)
    finished = q.fn(MATH + 'GreaterEqual_DoubleDouble', A=q.ref('ImpactAge'), B=.78)
    end = q.branch((finished, 'ReturnValue'))
    q.chain(age, end, call(q, 'StopDust'))
    scale = q.fn(MATH + 'MapRangeClamped', Value=q.ref('ImpactAge'), InRangeA=0, InRangeB=.26, OutRangeA=1, OutRangeB=0)
    square = q.fn(MATH + 'Multiply_FloatFloat', A=(scale, 'ReturnValue'), B=(scale, 'ReturnValue'))
    value = q.fn(MATH + 'Multiply_FloatFloat', A=(square, 'ReturnValue'), B=q.ref('RumbleStrength'))
    wire(end, 'else', scalar(q, (value, 'ReturnValue')), 'execute')
    compile_bp(bp)

    q = Graph(graph)
    begin = BP.add_event(bp, 'ReceiveBeginPlay')
    last = q.chain(begin, call(q, 'InitializeImpact'))
    last = valid(q, last, 'Director')
    last = valid(q, last, 'Reveal')
    for typeid, cls, member, handler in (
            ('Puzzle|BindEventtoOnPuzzleEvent', u.CatrunStatuePuzzle, 'Director', 'HandlePuzzle'),
            ('Puzzle|Reveal|BindEventtoOnPhaseChanged', u.CatrunPuzzleRevealComponent, 'Reveal', 'HandlePhase')):
        bind = BP.create_node(graph, typeid, u.IntPoint(0, 0), cls.static_class())
        q.chain(last, bind)
        wire(*q.ref(member), bind, 'self')
        create = special(graph, '이벤트생성')
        wire(create, 'OutputDelegate', bind, 'Delegate')
        BP.set_create_event_function(create, handler)
        assert str(u.BlueprintEditorLibrary.get_create_delegate_function(create)) == handler
        last = bind
    tick = BP.add_event(bp, 'ReceiveTick')
    update = call(q, 'UpdateImpact')
    q.chain(tick, update)
    wire(tick, 'DeltaSeconds', update, 'DeltaSeconds')
    q.chain(BP.add_event(bp, 'ReceiveEndPlay'), call(q, 'ClearImpact'))
    compile_bp(bp)
    cdo = u.get_default_object(bp.generated_class())
    cdo.set_editor_property('RumbleStrength', .00055)
    tick_settings = cdo.get_editor_property('primary_actor_tick')
    tick_settings.set_editor_property('start_with_tick_enabled', True)
    tick_settings.set_editor_property('tick_group', u.TickingGroup.TG_POST_UPDATE_WORK)
    return bp


def preserved_state(world):
    actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
    result = {}
    for actor in actors:
        label = actor.get_actor_label()
        if label.startswith('S3_GateImpact_'):
            continue
        # Python struct __str__ may include its wrapper address. ExportText is
        # value serialization; the numeric fields make any real delta readable.
        position, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        result[actor.get_path_name()] = {'label': label,
            'transform': actor.get_actor_transform().export_text(),
            'translation_cm': [position.x, position.y, position.z],
            'rotation_degrees': [rotation.pitch, rotation.yaw, rotation.roll],
            'scale3d': [scale.x, scale.y, scale.z],
            'collision': actor.get_actor_enable_collision()}
    return result


def reveal_tuning(reveal):
    result = {key: reveal.get_editor_property(key) for key in
              ('CameraTravelTime', 'CameraReturnTime', 'MaximumLockTime', 'bPreserveGameplayFraming')}
    offset = reveal.get_editor_property('GateCameraOffset')
    result['GateCameraOffset'] = [offset.x, offset.y, offset.z]
    return result


def preservation_diff(before, after):
    return {'added_existing_scope': sorted(set(after) - set(before)),
            'missing_existing_scope': sorted(set(before) - set(after)),
            'changed': [{'path': path, 'label': before[path]['label'],
                         'fields': {key: {'before': before[path][key], 'after': after[path].get(key)}
                                    for key in before[path] if before[path][key] != after[path].get(key)}}
                        for path in sorted(set(before) & set(after)) if before[path] != after[path]]}


def prepare():
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Stop PIE before preparing'
    world = ed.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    generation = os.environ.get('CATRUN_GATE_FX_GENERATION', 'Run01')
    assert re.fullmatch(r'[A-Za-z0-9_]+', generation)
    folder = '/Game/Environment/Stage3/GateFX_20261125/' + generation
    report_path = OUT / generation / 'prepared.json'
    assert not report_path.exists(), 'Use a new generation; never overwrite evidence'
    before_path = report_path.parent / 'preservation_before.json'
    assert not before_path.exists(), 'Prior partial preparation exists; use a fresh generation'
    actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
    assert not any(a.get_actor_label().startswith('S3_GateImpact_') for a in actors), 'Existing presenter set requires explicit review'
    director, = [a for a in actors if a.get_actor_label() == 'S3_StatuePuzzles']
    links = director.get_editor_property('Links')
    assert len(links) == 2
    reveal = director.get_editor_property('Reveal')
    tuning = reveal_tuning(reveal)
    assigned_settings = director.get_editor_property('Settings')
    # InitializePuzzle uses NewObject<UCatrunStatuePuzzleSettings>(this) when
    # Settings is null. Its CDO supplies the identical constructor defaults;
    # read it without initializing the puzzle or assigning/modifying a DA.
    settings = assigned_settings or u.get_default_object(u.CatrunStatuePuzzleSettings.static_class())
    assert settings, 'Native puzzle settings CDO unavailable'
    gate_settings = {key: float(settings.get_editor_property(key))
                     for key in ('GateTravel', 'GateFloorClearance')}
    settings_evidence = {'assigned_asset': assigned_settings.get_path_name() if assigned_settings else None,
                         'read_source': settings.get_path_name(), 'values': gate_settings,
                         'fallback_matches': 'CatrunStatuePuzzle.cpp InitializePuzzle null Settings -> NewObject native class defaults',
                         'settings_written': False}
    original = preserved_state(world)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    before_path.write_text(json.dumps({'actors': original, 'reveal_tuning': tuning}, indent=2), encoding='utf8')
    # Disk hashes prove no on-disk packages were changed by this preparation.
    protected = [ROOT / 'Content/Maps' / (stage + '.umap') for stage in ('Stage1', 'Stage2', 'Stage3')]
    protected += list((ROOT / 'Content/Systems/Interaction/Puzzles/Presentation').glob('*.uasset'))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()}
    spec = importlib.util.spec_from_file_location('s3_gate_fx_materials', HERE / 'materials.py')
    material_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(material_module)
    dust, rumble = material_module.build(folder)
    bp = author(folder, dust, rumble)
    records = []
    for index, link in enumerate(links):
        gate = link.get_editor_property('Gate')
        center, extent = gate.get_actor_bounds(False, False)
        initial = gate.get_actor_location()
        floor_offset = link.get_editor_property('GateFloorOffset')
        clearance = max(.1, gate_settings['GateFloorClearance'])
        travel = max(gate_settings['GateTravel'], 2 * extent.z - floor_offset + clearance)
        anchor = u.Vector(center.x, center.y, center.z - extent.z + floor_offset)
        instance = u.get_editor_subsystem(u.EditorActorSubsystem).spawn_actor_from_class(bp.generated_class(), anchor)
        assert instance
        instance.set_actor_label('S3_GateImpact_D%d' % (index + 1))
        instance.set_editor_property('tags', [OWNER])
        # Both D1/D2 span world X; fail rather than silently misorient a changed gate.
        assert extent.x > extent.y, ('Unexpected gate alignment', gate.get_actor_label(), extent)
        for key, value in {'Director': director, 'Reveal': reveal, 'Gate': gate,
                           'PuzzleId': link.get_editor_property('PuzzleId'),
                           'ExpectedOpenZ': initial.z - travel}.items():
            instance.set_editor_property(key, value)
        records.append({'label': instance.get_actor_label(), 'gate': gate.get_actor_label(),
                        'puzzle': str(link.get_editor_property('PuzzleId')), 'gate_initial_z': initial.z,
                        'expected_open_z': initial.z - travel, 'travel_cm': travel,
                        'floor_anchor': [anchor.x, anchor.y, anchor.z], 'component_pool': 8})
    after = preserved_state(world)
    after_tuning = reveal_tuning(reveal)
    difference = preservation_diff(original, after)
    difference['actor_state_equal'] = after == original
    difference['reveal_tuning_equal'] = tuning == after_tuning
    difference['reveal_tuning_before'] = tuning
    difference['reveal_tuning_after'] = after_tuning
    # Evidence is written BEFORE the guard. Never discard a real modification
    # or relax the assertion to make preparation appear successful.
    (report_path.parent / 'preservation_after.json').write_text(
        json.dumps({'actors': after, 'reveal_tuning': after_tuning}, indent=2), encoding='utf8')
    diff_path = report_path.parent / 'preservation_diff.json'
    diff_path.write_text(json.dumps(difference, indent=2), encoding='utf8')
    assert difference['actor_state_equal'], 'Existing actor state changed; inspect ' + str(diff_path)
    assert difference['reveal_tuning_equal'], 'Native reveal tuning changed; inspect ' + str(diff_path)
    assert director.get_editor_property('Settings') == assigned_settings
    assert gate_settings == {key: float(settings.get_editor_property(key)) for key in gate_settings}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    report = {'prepared': True, 'runtime_verified': False, 'source_stage2_script_reference':
        'C:/Users/whghk/.codex/workspaces/Stage2GameplayPolish_20261125_01a20e2d/GateFX',
        'scope': 'D1/D2 completion impact only; final sliding gate excluded',
        'actors': records, 'native_reveal_tuning_preserved': tuning,
        'preservation_diff_evidence': str(diff_path),
        'native_puzzle_settings_readonly': settings_evidence, 'protected_hashes': hashes,
        'save_performed': False, 'root_save_list_after_review': [dust.get_path_name(), rumble.get_path_name(), bp.get_path_name(), '/Game/Maps/Stage3'],
        'duration': {'dust_max_s': .78, 'rumble_s': .26, 'rumble_uv': .00055,
                     'inactive_can_end_early': True},
        'limits': ['Root must compile/run and inspect visible result.',
                   'No audio event is emitted; existing gameplay sound is unchanged.',
                   'No camera transform, projection, timing, gate collision, or trigger is changed.']}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf8')
    print('STAGE3_GATE_FX_PREPARED', str(report_path))
    return report
