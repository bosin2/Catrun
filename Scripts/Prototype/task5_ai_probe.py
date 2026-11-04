"""Bounded Task5 PIE probe; no production edits, collision toggles, saves or travel.
Run only with root's editor lease. Reads Task5/AIProbeControl.json once for run name,
then run/control.json for numbered commands. Native movement is API-driven, not OS input.
Commands: audit, stage (checked), move (native AddMovementInput, <=12s), bell,
sound (explicit synthetic hearing stimulus), shot, finish. All staging is logged.
"""
import json, math, time, traceback
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_saved_dir()).resolve() / "Prototype20261104/Task5"
CONFIG = json.loads((ROOT / "AIProbeControl.json").read_text(encoding="utf-8-sig"))
assert CONFIG["run"].replace("_", "").isalnum()
OUT = ROOT / CONFIG["run"]
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / "observations.json").exists(), "Preserve old run; use a fresh name"
ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ED.get_game_world(), "Root must start the intended fresh PIE world first"
STATE = {"start": time.monotonic(), "samples": [], "events": [], "last_id": 0,
         "provenance": "Read-only inspection plus explicitly logged runtime API staging; no OS-key claim"}


def v(x): return [x.x, x.y, x.z]
def actors(w): return unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
def name(a): return a.get_name() if a else None

def hit_data(hit):
    if not hit: return None
    d = hit.to_dict()
    return {k: v(x) if isinstance(x, unreal.Vector) else str(x) for k, x in d.items()}

def capsule(a): return a.get_component_by_class(unreal.CapsuleComponent)

def capsule_info(a):
    c = capsule(a)
    return {"name": a.get_name(), "label": a.get_actor_label(), "position": v(a.get_actor_location()),
            "center": v(c.get_world_location()), "radius": c.get_scaled_capsule_radius(),
            "half_height": c.get_scaled_capsule_half_height(), "collision": str(c.get_collision_enabled()),
            "actor_collision": a.get_actor_enable_collision(),
            "pawn_response": str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))} if c else None

def clearance(a, b):
    ca, cb = capsule(a), capsule(b)
    x, y = ca.get_world_location(), cb.get_world_location()
    ra, rb = ca.get_scaled_capsule_radius(), cb.get_scaled_capsule_radius()
    z = max(0., abs(x.z-y.z)-(ca.get_scaled_capsule_half_height()-ra)-(cb.get_scaled_capsule_half_height()-rb))
    return math.sqrt((x.x-y.x)**2+(x.y-y.y)**2+z*z)-ra-rb

def sweep(w, a, start, end, profile="Pawn", ignore=None):
    c = capsule(a)
    return unreal.SystemLibrary.capsule_trace_single_by_profile(w, start, end,
        c.get_scaled_capsule_radius(), c.get_scaled_capsule_half_height(), profile, False,
        ignore if ignore is not None else [a], unreal.DrawDebugTrace.NONE, False)

def floor_at(w, a, point):
    return unreal.SystemLibrary.line_trace_single_by_profile(w, point+unreal.Vector(0,0,80),
        point-unreal.Vector(0,0,160), "Pawn", False, [a], unreal.DrawDebugTrace.NONE, False)

def event(kind, **data):
    STATE["events"].append({"epoch": time.time(), "kind": kind, **data})

def save(final=False, error=None):
    result = {k: x for k,x in STATE.items() if k not in ("handle", "move", "samples")}
    result.update(final=final, error=error, samples=STATE["samples"] if final else STATE["samples"][-20:])
    (OUT / ("observations.json" if final else "progress.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")

def finish(error=None):
    unreal.unregister_slate_post_tick_callback(STATE["handle"])
    save(True, error)
    print("TASK5_AI_PROBE_FINISHED", error)

def find_actor(w, selector):
    found = [a for a in actors(w) if selector in (a.get_name(), a.get_actor_label())]
    assert len(found)==1, (selector, len(found))
    return found[0]

def audit(w, cat):
    subjects = [a for a in actors(w) if capsule(a) and (a==cat or isinstance(a, (unreal.CatrunArmor, unreal.CatrunCandle)))]
    result = {"world": w.get_path_name(), "subjects": [capsule_info(a) for a in subjects], "pairs": [], "baskets": []}
    for i,a in enumerate(subjects):
        for b in subjects[i+1:]: result["pairs"].append({"a": name(a), "b": name(b), "clearance": clearance(a,b)})
    actions = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
    for basket in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.CatrunHideBasket):
        center = basket.get_hidden_location()
        row = {"name": name(basket), "label": basket.get_actor_label(), "center": v(center), "candidates": []}
        limit = actions.get_editor_property("InteractionRange")
        entry_distance = actions.get_editor_property("EntryDistance")
        # Visibility is the current native ObstacleChannel; explicitly record it for validation.
        row["obstacle_channel"] = str(actions.get_editor_property("ObstacleChannel"))
        for degrees in range(0,360,15):
            direction = unreal.Vector(math.cos(math.radians(degrees)),math.sin(math.radians(degrees)),0)
            target = center+direction*95
            floor = floor_at(w, cat, target)
            if not floor: continue
            fd = floor.to_dict()
            if fd["impact_normal"].z<.65: continue
            target.z = fd["impact_point"].z+capsule(cat).get_scaled_capsule_half_height()+2.25
            distance = (target-center).length()
            if not 50<distance<limit: continue
            endpoint = sweep(w,cat,target,target+unreal.Vector(0,0,.1))
            entry = center+direction*entry_distance
            transit = unreal.SystemLibrary.capsule_trace_single(w,target,entry,
                capsule(cat).get_scaled_capsule_radius(),capsule(cat).get_scaled_capsule_half_height(),
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[cat],unreal.DrawDebugTrace.NONE,False)
            sight = unreal.SystemLibrary.line_trace_single(w,entry,center,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                False,[cat],unreal.DrawDebugTrace.NONE,False)
            support = unreal.SystemLibrary.line_trace_single(w,entry,entry-unreal.Vector(0,0,50),
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[cat],unreal.DrawDebugTrace.NONE,False)
            row["candidates"].append({"angle": degrees,"target":v(target),"distance":distance,
                "endpoint":hit_data(endpoint),"entry_transit":hit_data(transit),"entry_sight":hit_data(sight),
                "entry_support":hit_data(support)})
        result["baskets"].append(row)
    (OUT / ("audit-"+str(STATE["last_id"])+".json")).write_text(json.dumps(result,indent=2),encoding="utf-8")
    event("read-only-audit", subjects=len(subjects), baskets=len(result["baskets"]))

def command(w, cat, cmd):
    op=cmd["op"]
    if op=="finish": finish(); return False
    if op=="audit": audit(w,cat)
    elif op=="shot":
        unreal.SystemLibrary.execute_console_command(w,'Shot showui filename="'+str(OUT/(str(STATE["last_id"])+'.png')).replace(chr(92),'/')+'"')
    elif op=="stage":
        a=find_actor(w,cmd["actor"]) if cmd.get("actor") else cat
        target=unreal.Vector(*cmd["position"])
        f=floor_at(w,a,target); assert f and f.to_dict()["impact_normal"].z>=.65, "No supported staging floor"
        # Actor origin may differ from capsule center (candle root is at its feet).
        offset=capsule(a).get_world_location()-a.get_actor_location()
        target.z=f.to_dict()["impact_point"].z+capsule(a).get_scaled_capsule_half_height()+2.25-offset.z
        h=sweep(w,a,target+offset,target+offset+unreal.Vector(0,0,.1))
        assert not h, ("Occupied staging capsule",hit_data(h))
        before=v(a.get_actor_location());a.set_actor_location(target,False,True)
        event("api-clear-checkpoint",actor=name(a),before=before,after=v(a.get_actor_location()))
    elif op=="move":
        assert 0<float(cmd["seconds"])<=12
        STATE["move"]={"until":time.monotonic()+float(cmd["seconds"]),"direction":cmd["direction"]}
        event("api-native-movement-start",**cmd)
    elif op=="bell":
        bell=cat.get_component_by_class(unreal.CatrunBellComponent)
        event("api-native-bell",position=v(cat.get_actor_location()),accepted=bell.try_ring())
    elif op=="sound":
        a=find_actor(w,cmd["actor"]);e=unreal.CatrunSoundEvent();e.location=unreal.Vector(*cmd["target"])
        e.kind=unreal.CatrunSoundKind.FOOTSTEP;e.size=unreal.CatrunSoundSize.LARGE
        a.on_sound_heard(e,1000);event("synthetic-hearing-stimulus",**cmd)
    else: raise ValueError(op)
    return True

def tick(delta):
    try:
        now=time.monotonic()
        if now-STATE["start"]>240: finish("Bounded observer timeout");return
        w=ED.get_game_world()
        if not w: finish("PIE ended");return
        cat=unreal.GameplayStatics.get_player_pawn(w,0)
        if not cat:return
        control=OUT/"control.json"
        cmd=json.loads(control.read_text(encoding="utf-8-sig")) if control.exists() else {}
        if int(cmd.get("id",0))>STATE["last_id"]:
            STATE["last_id"]=int(cmd["id"])
            if not command(w,cat,cmd):return
        move=STATE.get("move")
        if move:
            if now<move["until"]:cat.add_movement_input(unreal.Vector(*move["direction"]),1.,False)
            else:STATE.pop("move");event("api-native-movement-end",position=v(cat.get_actor_location()))
        if now-STATE.get("last_sample",0)>=.05:
            STATE["last_sample"]=now
            aa=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunArmor)
            candles=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CatrunCandle)
            subjects=[cat]+list(aa)+list(candles)
            row={"epoch":time.time(),"game":unreal.GameplayStatics.get_time_seconds(w),"world":w.get_path_name(),
                 "cat":capsule_info(cat),"move_ignored":unreal.GameplayStatics.get_player_controller(w,0).is_move_input_ignored(),
                 "armor":[],"pairs":[]}
            for a in aa:
                m=a.get_component_by_class(unreal.SkeletalMeshComponent);capture=a.get_editor_property("CapturePresentation")
                row["armor"].append({**capsule_info(a),"action":str(a.get_action()),"destination":a.has_destination(),
                    "pelvis":v(m.get_socket_location("pelvis")),"phase":str(capture.get_editor_property("Phase"))})
            for i,a in enumerate(subjects):
                for b in subjects[i+1:]:
                    if (a.get_actor_location()-b.get_actor_location()).length()<350:
                        row["pairs"].append({"a":name(a),"b":name(b),"clearance":clearance(a,b)})
            STATE["samples"].append(row)
        if now-STATE.get("last_save",0)>2:STATE["last_save"]=now;save()
    except Exception:finish(traceback.format_exc())

STATE["handle"]=unreal.register_slate_post_tick_callback(tick)
print("TASK5_AI_PROBE_ARMED",str(OUT))
