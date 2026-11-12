"""Patch Stage2 checkpoint eye state and audit the Gate11 spawn in both saved maps.

Run with CATRUN_CHECKPOINT_VISUALS_MODE set to probe, author, or audit.
Only author saves a package, and that package is BP_StatuePresentation.
"""

import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import traceback

import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


ROOT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
sys.path.insert(0, str(ROOT / "Scripts/Menu"))
from menu_graph import Graph, compile_bp, entry, pin, wire


MODE = globals().get("CATRUN_CHECKPOINT_VISUALS_MODE") or os.environ.get(
    "CATRUN_CHECKPOINT_VISUALS_MODE", "probe")
OUT = ROOT / "Saved/GameplayRepair20261112/CheckpointVisuals" / (
    datetime.datetime.now().strftime("%H%M%S-%f") + "-" + str(os.getpid()))
PRES = "/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation"
MAPS = ("/Game/Maps/Stage2", "/Game/Maps/SoundTest_Stage2")
REFRESH = "RefreshCheckpointEyes"
REFRESH_PATH = PRES + ".BP_StatuePresentation_C:" + REFRESH
PUZZLE = "/Script/Catrun.CatrunStatuePuzzle:"
SYSTEM = "/Script/Engine.KismetSystemLibrary:"
MATH = "/Script/Engine.KismetMathLibrary:"
MID = "/Script/Engine.MaterialInstanceDynamic:"
NO_DEBUG = u.DrawDebugTrace.NONE
BLOCK = u.CollisionResponseType.ECR_BLOCK
PAWN = u.CollisionChannel.ECC_PAWN
OBJECTS = [getattr(u.ObjectTypeQuery, f"OBJECT_TYPE_QUERY{i}") for i in range(1, 7)]


def dirty():
    return sorted(p.get_name() for p in (
        list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages()) +
        list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages())))


def content_file(package):
    suffix = ".umap" if package in MAPS else ".uasset"
    return ROOT / "Content" / (package.removeprefix("/Game/") + suffix)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hashes():
    return {package: sha(content_file(package)) for package in (PRES, *MAPS)}


def node_rows(graph, excluded=()):
    rows = {}
    for info in BP.get_node_infos(BP.find_nodes(graph)):
        node = info.node
        if node.get_name() in excluded:
            continue
        pins = []
        for edge in node.list_all_pins():
            links = sorted((other.get_owning_node().get_name(), str(other.get_pin_name()))
                           for other in edge.list_connected_pins()
                           if other.get_owning_node().get_name() not in excluded)
            pins.append([str(edge.get_pin_direction()), str(edge.get_pin_name()),
                         str(edge.get_pin_value()), links])
        rows[node.get_name()] = {
            "type": str(info.type_id), "position": [info.position.x, info.position.y], "pins": pins}
    return rows


def snapshot(bp, exclude_new=()):
    return {g.get_name(): node_rows(g, exclude_new if g.get_name() == "EventGraph" else ())
            for g in BP.list_graphs(bp) if g.get_name() != REFRESH}


def find_node(graph, suffix):
    nodes = [info.node for info in BP.get_node_infos(BP.find_nodes(graph))
             if str(info.type_id).endswith("|" + suffix)]
    assert len(nodes) == 1, (graph.get_name(), suffix, [n.get_name() for n in nodes])
    return nodes[0]


def find_action(q, suffixes):
    choices = sorted({str(action) for action in q.e.list_available_nodes([])
                      if str(action).rsplit("|", 1)[-1] in suffixes})
    assert len(choices) == 1, (suffixes, choices)
    return choices[0]


def result(node):
    return node, "ReturnValue"


def build_refresh(bp):
    graph = BP.add_function_graph(bp, REFRESH)
    assert graph
    BP.add_function_param(graph, "PuzzleId", "name", True)
    q = Graph(graph)
    start = entry(q)
    director = q.ref("Director")
    own_id = q.ref("PuzzleId")
    eyes = q.ref("EyeMID")
    same = q.fn(MATH + "EqualEqual_NameName", A=(start, "PuzzleId"), B=own_id)
    valid_director = q.fn(SYSTEM + "IsValid", Object=director)
    valid_eyes = q.fn(SYSTEM + "IsValid", Object=eyes)
    valid_refs = q.fn(MATH + "BooleanAND", A=result(valid_director), B=result(valid_eyes))
    addressed = q.fn(MATH + "BooleanAND", A=result(same), B=result(valid_refs))
    ready = q.branch(result(addressed))
    seated = q.branch(result(q.fn(PUZZLE + "IsPuzzleSeated", target=director, PuzzleId=own_id)))
    color = q.fn(MID + "SetVectorParameterValue", target=eyes,
                 ParameterName=q.ref("EyeParameter"), Value=q.ref("SeatedEyeColor"))
    strength = q.fn(MID + "SetScalarParameterValue", target=eyes,
                    ParameterName=q.ref("EyeStrengthParameter"), Value=q.ref("SeatedEyeStrength"))
    q.chain(start, ready, seated, color, strength)
    compile_bp(bp)


def extend_begin_play(bp):
    graph = BP.get_graph(bp, "EventGraph")
    old_phase_bind = find_node(graph, "BindEventtoOnPhaseChanged")
    assert not pin(old_phase_bind, "then", True).list_connected_pins()
    pos = old_phase_bind.get_node_pos()
    q = Graph(graph, pos.x + 320, pos.y)
    bind = q.placed(BP.create_node(
        graph, find_action(q, ("BindEventtoOnCheckpointRestored",)), u.IntPoint(0, 0),
        u.CatrunStatuePuzzle.static_class()))
    wire(*q.ref("Director"), bind, "self")
    callback = q.placed(BP.create_node(
        graph, find_action(q, ("이벤트생성", "CreateEvent")), u.IntPoint(0, 0), None))
    wire(callback, "OutputDelegate", bind, "Delegate")
    BP.set_create_event_function(callback, REFRESH)
    initial = q.fn(REFRESH_PATH, PuzzleId=q.ref("PuzzleId"))
    q.chain(old_phase_bind, bind, initial)
    compile_bp(bp)
    return [node.get_name() for node in q.nodes]


def assert_single_input(node, name, expected):
    sources = pin(node, name).list_connected_pins()
    actual = [(src.get_owning_node().get_name(), str(src.get_pin_name())) for src in sources]
    assert actual == [(expected[0].get_name(), expected[1])], (node.get_name(), name, actual)


def input_node(node, name):
    source, = pin(node, name).list_connected_pins()
    return source.get_owning_node()


def audit_graph(bp):
    events = BP.get_graph(bp, "EventGraph")
    refresh = BP.get_graph(bp, REFRESH)
    assert refresh, REFRESH
    phase_bind = find_node(events, "BindEventtoOnPhaseChanged")
    bind = find_node(events, "BindEventtoOnCheckpointRestored")
    initial = find_node(events, REFRESH)
    assert_single_input(bind, "execute", (phase_bind, "then"))
    assert_single_input(initial, "execute", (bind, "then"))
    callback, = [p.get_owning_node() for p in pin(bind, "Delegate").list_connected_pins()]
    assert callback.get_class().get_name() == "K2Node_CreateDelegate"
    assert str(u.BlueprintEditorLibrary.get_create_delegate_function(callback)) == REFRESH
    for n, p, variable in ((bind, "self", "Director"), (initial, "PuzzleId", "PuzzleId")):
        source, = pin(n, p).list_connected_pins()
        assert str(source.get_pin_name()) == variable
        assert source.get_owning_node().get_class().get_name() == "K2Node_VariableGet"

    vector = find_node(refresh, "SetVectorParameterValue")
    scalar = find_node(refresh, "SetScalarParameterValue")
    seated = find_node(refresh, "IsPuzzleSeated")
    branch = input_node(vector, "execute")
    ready = input_node(branch, "execute")
    assert branch.get_class().get_name() == "K2Node_IfThenElse"
    assert ready.get_class().get_name() == "K2Node_IfThenElse"
    start = entry(Graph(refresh))
    assert_single_input(ready, "execute", (start, "then"))
    assert_single_input(branch, "execute", (ready, "then"))
    assert_single_input(branch, "Condition", (seated, "ReturnValue"))
    assert_single_input(vector, "execute", (branch, "then"))
    assert_single_input(scalar, "execute", (vector, "then"))
    addressed = input_node(ready, "Condition")
    equal = input_node(addressed, "A")
    references = input_node(addressed, "B")
    director_valid = input_node(references, "A")
    eyes_valid = input_node(references, "B")
    assert_single_input(equal, "A", (start, "PuzzleId"))
    for n, p, variable in ((equal, "B", "PuzzleId"), (seated, "PuzzleId", "PuzzleId"),
                           (director_valid, "Object", "Director"), (eyes_valid, "Object", "EyeMID"),
                           (seated, "self", "Director"), (vector, "self", "EyeMID"),
                           (scalar, "self", "EyeMID"), (vector, "ParameterName", "EyeParameter"),
                           (scalar, "ParameterName", "EyeStrengthParameter"),
                           (vector, "Value", "SeatedEyeColor"), (scalar, "Value", "SeatedEyeStrength")):
        source, = pin(n, p).list_connected_pins()
        assert str(source.get_pin_name()) == variable
        assert source.get_owning_node().get_class().get_name() == "K2Node_VariableGet"
    expected_calls = {n.get_name() for n in (
        equal, addressed, references, director_valid, eyes_valid, seated, vector, scalar)}
    calls = {i.node.get_name(): str(i.type_id) for i in BP.get_node_infos(BP.find_nodes(refresh))
             if i.node.get_class().get_name() in ("K2Node_CallFunction", "K2Node_PromotableOperator",
                                                 "K2Node_CommutativeAssociativeBinaryOperator")}
    assert set(calls) == expected_calls, calls
    return {"event_graph": node_rows(events), "refresh_graph": node_rows(refresh),
            "calls": calls, "callback": callback.get_name()}


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def capture_hit(hit):
    if not hit:
        return None
    d = hit.to_dict()
    actor = d["hit_actor"]
    return {"actor": actor.get_actor_label() if actor else None, "location": vec(d["location"]),
            "point": vec(d["impact_point"]), "normal": vec(d["impact_normal"]),
            "blocking": d["blocking_hit"], "initial_overlap": d["initial_overlap"]}


def gate_spawn_probe(package, bp):
    assert not dirty(), dirty()
    assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(package), package
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    cat, = [a for a in actors if a.get_class().get_name() == "BP_Cat_C"]
    puzzle, = [a for a in actors if isinstance(a, u.CatrunStatuePuzzle)]
    rows = {str(link.get_editor_property("PuzzleId")): link for link in puzzle.get_editor_property("Links")}
    assert set(rows) == {"A", "B", "C"}, (package, rows)
    link = rows["C"]
    gate, statue, plate = [link.get_editor_property(name) for name in ("Gate", "Statue", "Plate")]
    assert gate.get_actor_label() == "S2_Gate_11_Bars", gate.get_actor_label()
    presenters = [a for a in actors if a.get_class() == bp.generated_class()]
    assert {str(a.get_editor_property("PuzzleId")) for a in presenters} == {"A", "B", "C"}
    presentation, = [a for a in presenters if str(a.get_editor_property("PuzzleId")) == "C"]
    assert presentation.get_editor_property("Director") == puzzle
    assert presentation.get_editor_property("Statue") == statue and presentation.get_editor_property("Gate") == gate
    seated_color = presentation.get_editor_property("SeatedEyeColor")
    seated_eyes = {"color": [float(getattr(seated_color, channel)) for channel in "rgba"],
                   "strength": float(presentation.get_editor_property("SeatedEyeStrength"))}
    settings = puzzle.get_editor_property("Settings")
    assert settings

    gate_pos, statue_pos, plate_pos = [actor.get_actor_location() for actor in (gate, statue, plate)]
    gate_center, gate_extent = gate.get_actor_bounds(False)
    statue_center, _ = statue.get_actor_bounds(False)
    plate_center, _ = plate.get_actor_bounds(False)
    assert abs(gate_extent.y) < abs(gate_extent.x), vec(gate_extent)
    travel = max(settings.get_editor_property("GateTravel"),
                 2. * gate_extent.z - link.get_editor_property("GateFloorOffset") +
                 max(.1, settings.get_editor_property("GateFloorClearance")))
    pressed_plate = plate_pos - u.Vector(0, 0, settings.get_editor_property("PlateTravel"))
    seat = u.Vector(plate_center.x - (statue_center.x - statue_pos.x),
                    plate_center.y - (statue_center.y - statue_pos.y), statue_pos.z)
    open_gate = gate_pos - u.Vector(0, 0, travel)
    assert gate_center.z + gate_extent.z - travel < 0., (package, travel)

    cap = cat.get_component_by_class(u.CapsuleComponent)
    movement = cat.get_component_by_class(u.CharacterMovementComponent)
    assert str(cap.get_collision_profile_name()) == "Pawn"
    assert cap.get_collision_object_type() == PAWN and cap.get_up_vector().z > .99
    radius, half_height = cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()
    reference_z = cat.get_actor_location().z

    def sweep(start, end):
        return u.SystemLibrary.capsule_trace_single_by_profile(world, start, end, radius, half_height,
            cap.get_collision_profile_name(), False, [cat], NO_DEBUG, False)

    def find_support(y):
        reference = u.Vector(gate_pos.x, y, reference_z)
        hit = sweep(reference + u.Vector(0, 0, 40), reference - u.Vector(0, 0, 80))
        report = {"reference": vec(reference), "floor": capture_hit(hit)}
        if not hit:
            return None, report
        d = hit.to_dict()
        center, contact = d["location"], d["impact_point"]
        if not d["blocking_hit"] or d["initial_overlap"] or d["impact_normal"].z < .65 \
                or isinstance(d["hit_actor"], u.Pawn) or not movement.is_walkable(hit) \
                or math.hypot(contact.x - center.x, contact.y - center.y) > max(0., radius - .15):
            return None, report
        result = u.Vector(reference.x, reference.y, center.z + 2.)
        overlaps = u.SystemLibrary.capsule_overlap_components(world, result, radius, half_height,
            OBJECTS, u.PrimitiveComponent, [cat]) or []
        blockers = sorted(comp.get_path_name() for comp in overlaps
                          if comp.get_collision_response_to_channel(PAWN) == BLOCK
                          and cap.get_collision_response_to_channel(comp.get_collision_object_type()) == BLOCK)
        report.update(center=vec(result), blockers=blockers)
        return (None if blockers else result), report

    # Change transforms only in this isolated editor world, then restore every pose.
    original = ((gate, gate_pos), (statue, statue_pos), (plate, plate_pos))
    try:
        for actor, location in ((gate, open_gate), (statue, seat), (plate, pressed_plate)):
            assert actor.set_actor_location(location, False, True), actor.get_actor_label()
        assert (gate.get_actor_location() - open_gate).length() < .01
        points, evidence = [], []
        for distance in (110., 80., 140.):
            point, query = find_support(gate_pos.y - distance)
            evidence.append({"distance": distance, **query})
            points.append(point)
        assert points[0] is not None, (package, evidence)
        before_gate, approach = find_support(gate_pos.y + 80.)
        assert before_gate is not None, (package, approach)
        passage = capture_hit(sweep(before_gate, points[0]))
        assert not passage, (package, passage)
    finally:
        for actor, location in original:
            actor.set_actor_location(location, False, True)
            assert (actor.get_actor_location() - location).length() < .01, actor.get_actor_label()
    assert not dirty(), (package, dirty())
    return {"gate": vec(gate_pos), "gate_open": vec(open_gate), "statue_seat": vec(seat),
            "plate_pressed": vec(pressed_plate), "capsule": [radius, half_height],
            "seated_eyes": seated_eyes,
            "cat_start": vec(cat.get_actor_location()), "candidates": evidence,
            "approach": approach, "passage_block": passage, "selected": vec(points[0])}


OUT.mkdir(parents=True, exist_ok=False)
report = {"mode": MODE, "pid": os.getpid(), "complete": False}
try:
    assert MODE in ("probe", "author", "audit"), MODE
    assert "-run=pythonscript" in u.SystemLibrary.get_command_line().lower(), "Use the isolated Unreal Python commandlet"
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() and not dirty(), dirty()
    assert hasattr(u.CatrunStatuePuzzle, "is_puzzle_seated"), "Rebuild Catrun before running this script"
    bp = u.EditorAssetLibrary.load_asset(PRES)
    assert bp
    report["hashes_before"] = content_hashes()
    report["graphs_before"] = snapshot(bp)
    event_graph = BP.get_graph(bp, "EventGraph")
    if MODE == "probe":
        q = Graph(event_graph)
        report["bind_action"] = find_action(q, ("BindEventtoOnCheckpointRestored",))
        report["create_action"] = find_action(q, ("이벤트생성", "CreateEvent"))
    if MODE != "author":
        report["maps"] = {}
        for package in MAPS:
            report["maps"][package] = gate_spawn_probe(package, bp)
    if MODE == "author":
        assert REFRESH not in {g.get_name() for g in BP.list_graphs(bp)}, "Use audit for an already authored Blueprint"
        backup = OUT / "Before" / content_file(PRES).name
        backup.parent.mkdir()
        shutil.copy2(content_file(PRES), backup)
        assert sha(backup) == report["hashes_before"][PRES]
        report["backup"] = str(backup)
        build_refresh(bp)
        new_nodes = extend_begin_play(bp)
        assert snapshot(bp, new_nodes) == report["graphs_before"], "Existing presentation graph changed"
        report["graph_audit"] = audit_graph(bp)
        assert set(dirty()) <= {PRES}, dirty()
        assert u.EditorAssetLibrary.save_loaded_asset(bp, False)
    elif MODE == "audit":
        assert bp.get_editor_property("status") == u.BlueprintStatus.BS_UP_TO_DATE
        report["graph_audit"] = audit_graph(bp)
    report["hashes_after"] = content_hashes()
    changed = {package for package in report["hashes_before"]
               if report["hashes_before"][package] != report["hashes_after"][package]}
    assert changed == ({PRES} if MODE == "author" else set()), changed
    assert not dirty(), dirty()
    report["complete"] = True
    u.log("CATRUN_CHECKPOINT_VISUALS_" + MODE.upper() + "_OK")
except Exception:
    report["error"] = traceback.format_exc()
    raise
finally:
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
