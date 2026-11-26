"""One bounded, native-movement Tutorial traversal; run only with editor lease.

Arm on MainMenu before root's actual OS Play/Start. This script does not start PIE,
click Start, load maps, relocate actors, alter collision/AI, or complete a stage.
After the original intro + 27s observation boundary it drives AddMovementInput
(force=False) and calls original BP_CatActions.TryBell, including its animation,
timers and movement lock. Bell calls are API actions, not physical Space claims.
Final success requires real stair overlap/cinematic and automatic Stage1 travel.
"""
import json
import math
import time
import traceback
from pathlib import Path

import unreal


EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not EDITOR.get_game_world(), "Arm before root starts PIE"
assert EDITOR.get_editor_world().get_name() == "MainMenu", "Original menu required"
BASE = Path(unreal.Paths.project_saved_dir()).resolve() / "Prototype20261104/Task5"
RUN = next(f"TutorialCompleteRoute{i:02d}" for i in range(1, 1000)
           if not (BASE / f"TutorialCompleteRoute{i:02d}").exists())
OUT = BASE / RUN
OUT.mkdir(parents=True)
STATE = {"armed": time.monotonic(), "phase": "menu", "events": [], "samples": [],
         "worlds": [], "menu_seen": False, "intro_seen": False,
         "scope": "Actual UI menu start external; native movement and original BP bell via API; no relocation"}


def vec(p):
    return [p.x, p.y, p.z]


def actors(world):
    return unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)


def event(kind, **data):
    STATE["events"].append({"kind": kind, "epoch": time.time(), **data})


def save(final=False, error=None):
    data = {k: value for k, value in STATE.items() if k not in ("handle", "samples")}
    data.update(final=final, success=final and error is None, error=error,
                sample_count=len(STATE["samples"]),
                samples=STATE["samples"] if final else STATE["samples"][-20:])
    target = OUT / ("observations.json" if final else "progress.json")
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def finish(error=None):
    unreal.unregister_slate_post_tick_callback(STATE["handle"])
    save(True, error)
    print("TUTORIAL_COMPLETE_ROUTE_FINISHED", str(OUT), error)


def hit_info(hit):
    if not hit:
        return None
    fields = hit.to_dict()
    result = {}
    for key in ("blocking_hit", "initial_overlap", "distance", "location", "impact_point", "impact_normal"):
        value = fields.get(key)
        result[key] = vec(value) if isinstance(value, unreal.Vector) else value
    for key in ("hit_actor", "hit_component"):
        obj = fields.get(key)
        result[key] = obj.get_path_name() if obj else None
    return result


def capsule(cat):
    return cat.get_component_by_class(unreal.CapsuleComponent)


def sweep(world, cat, start, end):
    shape = capsule(cat)
    return unreal.SystemLibrary.capsule_trace_single_by_profile(
        world, start, end, shape.get_scaled_capsule_radius(), shape.get_scaled_capsule_half_height(),
        "Pawn", False, [cat], unreal.DrawDebugTrace.NONE, False)


def supported_center(world, cat, point):
    hit = unreal.SystemLibrary.line_trace_single_by_profile(
        world, point + unreal.Vector(0, 0, 100), point - unreal.Vector(0, 0, 250),
        "Pawn", False, [cat], unreal.DrawDebugTrace.NONE, False)
    assert hit, ("No supporting floor", vec(point))
    fields = hit.to_dict()
    assert fields["impact_normal"].z >= .65, ("Unsupported slope", hit_info(hit))
    center = unreal.Vector(point.x, point.y,
                           fields["impact_point"].z + capsule(cat).get_scaled_capsule_half_height() + 2.25)
    return center, hit_info(hit)


def walkable(hit):
    fields = hit.to_dict()
    return fields["impact_normal"].z >= .65 and not isinstance(fields.get("hit_actor"), unreal.Pawn)


def preflight_leg(world, cat, start, xy):
    """Physics shortlist only; native traversal remains the acceptance evidence."""
    target = unreal.Vector(xy[0], xy[1], start.z)
    distance = math.hypot(target.x - start.x, target.y - start.y)
    count = max(1, math.ceil(distance / 25.))
    previous = start
    max_step = cat.get_component_by_class(unreal.CharacterMovementComponent).get_editor_property("MaxStepHeight")
    floors = []
    for index in range(1, count + 1):
        alpha = index / count
        probe = unreal.Vector(start.x + (target.x-start.x)*alpha,
                              start.y + (target.y-start.y)*alpha, previous.z)
        current, floor = supported_center(world, cat, probe)
        assert abs(current.z - previous.z) <= max_step + 3., ("Unexpected floor step/drop", vec(previous), vec(current), floor)
        endpoint = sweep(world, cat, current, current + unreal.Vector(0, 0, .1))
        # 2026-11-26: a capsule touching a walkable surface (door threshold seam, stair
        # tread) is floor contact, not an obstacle; it is recorded, walls still fail.
        assert not endpoint or walkable(endpoint), ("Occupied planned endpoint", vec(current), hit_info(endpoint))
        # Horizontal clearance above a supported step, followed by an endpoint fit.
        # No diagonal sweep through tread corners or false constant-Z stair descent.
        height = max(previous.z, current.z)
        hit = sweep(world, cat, unreal.Vector(previous.x, previous.y, height),
                    unreal.Vector(current.x, current.y, height))
        assert not hit or walkable(hit), ("Blocked planned segment", vec(previous), vec(current), hit_info(hit))
        if endpoint or hit:
            event("physics-preflight-walkable-contact", point=vec(current),
                  endpoint=hit_info(endpoint), segment=hit_info(hit))
        floors.append({"xy": [current.x, current.y], "center_z": current.z, "floor": floor})
        previous = current
    event("physics-preflight-only", start=vec(start), target=xy, samples=floors)
    return previous


def no_bell(world, cat):
    """Same XY circle/box calculation as native Touches; no collision queries on invisible zones."""
    radius = capsule(cat).get_scaled_capsule_radius()
    for zone in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunNoBellZone):
        box = zone.get_component_by_class(unreal.BoxComponent)
        delta = cat.get_actor_location() - box.get_world_location()
        rotation = box.get_world_rotation()
        assert abs(rotation.pitch) < .01 and abs(rotation.roll) < .01, "Unexpected tilted no-bell volume"
        yaw = math.radians(rotation.yaw)
        x = delta.x*math.cos(yaw) + delta.y*math.sin(yaw)
        y = -delta.x*math.sin(yaw) + delta.y*math.cos(yaw)
        extent = box.get_scaled_box_extent()
        if math.hypot(max(0., abs(x)-extent.x), max(0., abs(y)-extent.y)) <= radius:
            return True
    return False


def bp_actions(cat):
    matches = [c for c in cat.get_components_by_class(unreal.ActorComponent)
               if c.get_class().get_name() == "BP_CatActions_C"]
    assert len(matches) == 1, "Original BP_CatActions must be present exactly once"
    return matches[0]


def clip_name(cat):
    mesh = cat.get_component_by_class(unreal.SkeletalMeshComponent)
    instance = mesh.get_anim_instance()
    if isinstance(instance, unreal.AnimSingleNodeInstance):
        asset = instance.get_animation_asset()
        return asset.get_name() if asset else None
    return None


def candle_view(candle):
    plane = next((c for c in candle.get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_name()=="Sight_VisionPlane"), None)
    if not plane:
        return None
    center = plane.get_world_location()
    position = candle.get_actor_location()
    return math.degrees(math.atan2(position.y-center.y, position.x-center.x))


def stamina(cat):
    """Read-only sprint stamina (sprint stamina was added after this route was authored)."""
    sprint = cat.get_component_by_class(unreal.CatrunSprintComponent)
    return sprint.get_stamina() if sprint else None


def authored_run(cat, game):
    STATE["want_run"] = True
    event("api-EnhancedInput-IA_Run", game=game, asset="/Game/Input/Actions/IA_Run",
          scope="Original action injection, no speed/property override")



def change(phase, game):
    STATE["phase"] = phase
    STATE["changed_game"] = game
    STATE.pop("motion_window", None)
    event("phase", phase=phase, game=game)


def queue(phase, points, next_phase, game, gaits=None):
    """gaits: optional per-waypoint "run"/"walk"; None keeps the current IA_Run state."""
    STATE["points"] = [list(p) for p in points]
    STATE["gaits"] = list(gaits) if gaits else None
    STATE["point_index"] = 0
    STATE["next_phase"] = next_phase
    STATE.pop("checked_point", None)
    change(phase, game)


def request_bell(world, cat, ordinal, game):
    assert not no_bell(world, cat), "Requested bell point is forbidden"
    assert not bp_actions(cat).get_editor_property("Busy"), "Cat action already owns input"
    event("api-original-BP-TryBell", ordinal=ordinal, game=game, cat=vec(cat.get_actor_location()))
    bp_actions(cat).call_method("TryBell")
    STATE["bell_clip_seen"] = False
    STATE["bell_ordinal"] = ordinal
    change(f"bell_{ordinal}", game)


def diagnostic(world, cat, xy, doors):
    start = cat.get_actor_location()
    direction = unreal.Vector(xy[0]-start.x, xy[1]-start.y, 0)
    length = direction.length()
    end = start + direction / max(length, .001) * min(length, 60.)
    return {"position": vec(start), "target": xy, "blocking_hit": hit_info(sweep(world, cat, start, end)),
            "doors": [{"name": d.get_name(), "open": d.is_open(),
                       "leaf_collision": str(d.get_editor_property("DoorMesh").get_collision_enabled())}
                      for d in doors]}


def move_queue(world, cat, pc, actions, game, doors):
    if actions.get_editor_property("Busy") or pc.is_move_input_ignored():
        STATE.pop("motion_window", None)
        return
    points, index = STATE["points"], STATE["point_index"]
    gaits = STATE.get("gaits")
    if gaits and index < len(gaits) and STATE.get("want_run") != (gaits[index] == "run"):
        # Walking = no IA_Run injection (original walk speed and smaller footstep).
        STATE["want_run"] = gaits[index] == "run"
        event("api-EnhancedInput-IA_Run-" + ("held" if STATE["want_run"] else "released"), game=game, waypoint=points[index])
    if STATE.get("want_run") and not cat.get_editor_property("IsRunning"):
        return
    if index >= len(points):
        change(STATE["next_phase"], game)
        return
    xy = points[index]
    position = cat.get_actor_location()
    direction = unreal.Vector(xy[0]-position.x, xy[1]-position.y, 0)
    distance = direction.length()
    if distance <= 5.:
        event("waypoint-reached-by-movement", game=game, target=xy, actual=vec(position))
        STATE["point_index"] += 1
        STATE.pop("motion_window", None)
        return
    key = [STATE["phase"], index]
    if STATE.get("checked_point") != key:
        preflight_leg(world, cat, position, xy)
        STATE["checked_point"] = key
    window = STATE.setdefault("motion_window", {"game": game, "position": vec(position)})
    if game-window["game"] >= 1.5:
        old = window["position"]
        if math.hypot(position.x-old[0], position.y-old[1]) < 2.:
            event("native-movement-stall", **diagnostic(world, cat, xy, doors))
            raise RuntimeError("1.5s native movement stall; blocking component recorded")
        STATE["motion_window"] = {"game": game, "position": vec(position)}
    cat.add_movement_input(direction / distance, 1., False)


def tick(delta):
    try:
        now = time.monotonic()
        if now-STATE["armed"] > 300:
            finish("Wall watchdog expired; no completed route"); return
        world = EDITOR.get_game_world()
        if not world:
            if STATE.get("route_start_game") is not None:
                finish("PIE ended during route")
            return
        name = world.get_name()
        if not STATE["worlds"] or STATE["worlds"][-1] != name:
            STATE["worlds"].append(name)
            event("world-observed", world=world.get_path_name())
        if name.endswith("MainMenu"):
            STATE["menu_seen"] = True
            return
        cat = unreal.GameplayStatics.get_player_pawn(world, 0)
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        game = unreal.GameplayStatics.get_time_seconds(world)
        if not cat or not pc:
            return
        if name.endswith("Stage1"):
            assert STATE.get("saw_exit_overlap") and STATE.get("saw_stairs"), "Unexpected travel without original stair overlap/cinematic"
            STATE.setdefault("stage1_game", game)
            if game-STATE["stage1_game"] >= 1. and not pc.is_move_input_ignored():
                event("automatic-Stage1-arrival", game=game, cat=vec(cat.get_actor_location()), collision=cat.get_actor_enable_collision())
                finish()
            return
        assert name.endswith("Tutorial"), ("Unexpected map", name)
        STATE.setdefault("tutorial_seen_wall", now)
        all_actors = actors(world)
        armor = next(a for a in all_actors if a.get_actor_label() == "Armor_Tutorial")
        candle = next(a for a in all_actors if isinstance(a, unreal.CatrunCandle))
        beam = candle_view(candle)
        previous_beam = STATE.get("previous_beam")
        beam_delta = beam-previous_beam if beam is not None and previous_beam is not None else 0.
        STATE["previous_beam"] = beam
        marked = any(c.get_name()=="CatrunMarkOrb" for c in cat.get_components_by_class(unreal.StaticMeshComponent))
        doors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CatrunDoor))
        corridor = next(d for d in doors if d.get_actor_label() == "Door_Tutorial_Corridor")
        capture = armor.get_editor_property("CapturePresentation").get_editor_property("Phase")
        if "INACTIVE" not in str(capture):
            event("route-captured", game=game, phase=str(capture))
            finish("Normal AI capture: route failed; queued movement stopped"); return
        intro = next(a for a in all_actors if a.get_class().get_name() == "BP_TutorialIntro_C")
        player = intro.get_editor_property("IntroPlayer")
        playing = bool(player and player.is_playing())
        STATE["intro_seen"] = STATE["intro_seen"] or playing
        exit_actor = next(a for a in all_actors if a.get_actor_label() == "BP_Tutorial_ExitToStage1")
        director = next(a for a in all_actors if a.get_class().get_name() == "BP_StairDescentDirector_C")
        stair_player = director.get_editor_property("SequencePlayer")
        stairs = bool(stair_player and stair_player.is_playing())
        overlap = exit_actor.is_overlapping_actor(cat)
        if overlap and not STATE.get("saw_exit_overlap"):
            STATE["saw_exit_overlap"] = True
            event("actual-stair-overlap", game=game, cat=vec(cat.get_actor_location()))
            change("exit", game)
        if stairs:
            STATE["saw_stairs"] = True
        if STATE.get("want_run") and not STATE.get("saw_exit_overlap"):
            sub = next(s for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem) if s.get_world()==world)
            sub.inject_input_vector_for_action(unreal.load_asset("/Game/Input/Actions/IA_Run"), unreal.Vector(1,0,0), [], [])
        actions = bp_actions(cat)
        movement = cat.get_component_by_class(unreal.CharacterMovementComponent)
        position, enemy = cat.get_actor_location(), armor.get_actor_location()
        manager = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SoundGridManager)[0]
        if now-STATE.get("last_sample", 0) >= .05:
            STATE["last_sample"] = now
            STATE["samples"].append({"game": game, "epoch": time.time(), "phase": STATE["phase"],
                "cat": vec(position), "armor": vec(enemy), "armor_action": str(armor.get_action()),
                "armor_pelvis": vec(armor.get_component_by_class(unreal.SkeletalMeshComponent).get_socket_location("pelvis")),
                "capture": str(capture), "separation_xy": math.hypot(position.x-enemy.x, position.y-enemy.y),
                "cat_collision": cat.get_actor_enable_collision(), "armor_collision": armor.get_actor_enable_collision(),
                "marked": marked, "candle_center_yaw": beam, "running": cat.get_editor_property("IsRunning"), "stamina": stamina(cat), "max_walk_speed": movement.max_walk_speed,
                "movement": str(movement.get_editor_property("MovementMode")), "busy": actions.get_editor_property("Busy"),
                "move_ignored": pc.is_move_input_ignored(), "bell_forbidden": no_bell(world, cat), "clip": clip_name(cat),
                "doors": {d.get_name(): d.is_open() for d in doors}, "intro": playing, "exit_overlap": overlap,
                "stairs": stairs, "latest_grid_budget_at_armor": manager.get_remaining_budget_at(enemy)})
        phase = STATE["phase"]
        if phase == "menu":
            if STATE["intro_seen"] and not playing and not pc.is_move_input_ignored() and now-STATE["tutorial_seen_wall"] >= 27:
                assert STATE["menu_seen"], "Menu Start was not observed"
                assert math.hypot(position.x-170., position.y+95.) < 15., "Original playable spawn changed"
                settings = manager.get_editor_property("Settings")
                radius = settings.get_editor_property("ArmorDetectRadius") + settings.get_editor_property("CatSightRadius")
                STATE["detect_radius"] = radius
                assert radius >= 165., "Unexpected sight weakening; this run must preserve authored detection"
                gate = corridor.get_editor_property("GateBox").get_world_location()
                assert abs(gate.x+228)<1 and abs(gate.y-662)<1, "Saved doorway center changed"
                event("original-spawn-preflight", game=game, position=vec(position), radius=radius, corridor_center=vec(gate), actual_pov=str(pc.player_camera_manager.get_camera_rotation()),
                      candle=vec(candle.get_actor_location()), candle_yaw=candle.get_actor_rotation().yaw, armor=vec(enemy))
                STATE["route_start_game"] = game
                change("wait_candle_start", game)
        elif phase == "wait_candle_start":
            # 2026-11-26: run speed rose 124 -> 134, so the same 4.3s approach now reaches
            # (-180,-95) ~0.45s earlier in the sweep and meets the cone's trailing edge
            # (spotted at beam ~-93). Starting ~0.6s later restores the beam phase of the
            # successful 124-speed runs (arrival near beam -85 instead of -93).
            if beam is not None and -114 < beam < -108 and beam_delta < 0:
                authored_run(cat, game)
                queue("approach", [(-30,-95), (-30,-180), (-180,-180), (-180,-95), (-210,-95)], "wait_candle_west", game)
        elif phase == "wait_candle_west":
            # Sprint stamina (100, -20/s) is mostly spent by the approach; the west dash
            # waits at the safe corner for the next away-sweep with recovered stamina.
            if beam is not None and -86 < beam < -80 and beam_delta > 0 and (stamina(cat) or 100.) >= 90.:
                event("beam-away-west-dash", game=game, beam=beam, stamina=stamina(cat))
                queue("approach", [(-210,220), (-210,405)], "ring_first", game)
        elif phase.startswith("bell_"):
            STATE["bell_clip_seen"] = STATE["bell_clip_seen"] or "Bell" in (clip_name(cat) or "")
            elapsed = game-STATE["changed_game"]
            if elapsed > 1 and not STATE["bell_clip_seen"]:
                raise RuntimeError("Original BP TryBell did not start its bell clip")
            if STATE["bell_clip_seen"] and not actions.get_editor_property("Busy") and "WALKING" in str(movement.get_editor_property("MovementMode")):
                event("original-bell-finished", ordinal=STATE["bell_ordinal"], game=game)
                if STATE["bell_ordinal"] == 1:
                    queue("hole", [(-275,420), (-275,510), (-275,538)], "wait_looking", game)
                else:
                    queue("annex_wait_approach", [(-275,510), (-275,400)], "wait_lured", game)
        elif phase == "ring_first":
            request_bell(world, cat, 1, game)
        elif phase == "wait_looking":
            if "LOOKING" in str(armor.get_action()):
                request_bell(world, cat, 2, game)
        elif phase == "wait_lured":
            # Retreat through the cat-only hole, then use the native bedroom door
            # after the armor has committed to the annex. Real wall LOS remains active.
            # 2026-11-26: the old test (x<-230, y>575) fired while the armor was already
            # LEAVING the annex for its post (-80,760) via the corridor, and the running cat
            # was heard (11-23: "heard a sound (size 1, remaining 38)") and caught at the
            # corridor. Cross instead while the armor is still travelling to the bell on
            # the west passage: an armor investigating the bell (size 2) ignores the smaller
            # running footsteps until it starts LOOKING, by which time the cat is out of range.
            if corridor.is_open() and enemy.x < -340 and enemy.y > 250:
                event("armor-committed-to-annex", game=game, armor=vec(enemy), action=str(armor.get_action()))
                # Run away from the hole exit only while the armor is still on the west
                # passage; stop running at x=-150 before it nears the annex (11-26 Fix01/02:
                # the wave of a running step at (-130,400) reached it 0.3s after LOOKING
                # began, remaining 23). The walk's smaller footstep does not reach the annex
                # from the east half of the bedroom or the corridor; the stairs are run.
                queue("cross_and_corridor", [(-150,400), (-128,400), (-128,530), (-128,730), (-128,930)], "begin_stairs", game,
                      gaits=("run", "walk", "walk", "walk", "walk"))
        elif phase == "begin_stairs":
            queue("descend", [(-130,1050), (-130,1128), (-130,1200), (-130,1272), (-130,1344), (-130,1443), (-130,1548)], "wait_exit", game,
                  gaits=("run",)*7)
        elif phase in ("approach", "hole", "annex_wait_approach", "cross_and_corridor", "descend"):
            move_queue(world, cat, pc, actions, game, doors)
        # No movement commands after overlap, during original cinematic or after travel.
        if STATE.get("route_start_game") is not None:
            assert cat.get_actor_enable_collision() or STATE.get("saw_exit_overlap"), "Unexpected collision loss during locomotion"
            if game-STATE["route_start_game"] > 120:
                finish("120 gameplay-second route limit exceeded"); return
            if phase in ("wait_looking", "wait_lured", "wait_exit", "exit", "wait_candle_start", "wait_candle_west") and game-STATE["changed_game"] > 15:
                finish("Expected native state/exit did not arrive within 15s: "+phase); return
        if now-STATE.get("last_save", 0) >= 1:
            STATE["last_save"] = now
            save()
    except Exception:
        finish(traceback.format_exc())


STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
save()
print("TUTORIAL_COMPLETE_ROUTE_ARMED_WAITING_FOR_ROOT_OS_START", str(OUT))
