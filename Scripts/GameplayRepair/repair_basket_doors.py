"""Inspect saved basket groups and doorway geometry in an isolated commandlet.

Default mode is a read-only probe. The verify mode stages changes in memory,
then discards them. Apply requires the separate verify report; audit reloads
the saved changes in another process and checks them against the apply report.
Use -run=pythonscript -catrunBasketDoorsIsolated with all four geometry CVars at 0.
Set CATRUN_BASKET_DOORS_MODE/PROOF/OUT as Python globals in a launcher wrapper.
"""

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
OUT = Path(globals().get('CATRUN_BASKET_DOORS_OUT') or
           ROOT / 'Saved/GameplayRepair20261111/BasketDoors' / datetime.now().strftime('%H%M%S-%f')).resolve()
MODE = str(globals().get('CATRUN_BASKET_DOORS_MODE', 'probe'))
MAPS = ('Tutorial', 'SoundTest_Tutorial', 'Stage1', 'SoundTest_Stage1', 'Stage2', 'SoundTest_Stage2')
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
NONE = u.DrawDebugTrace.NONE
PAWN = u.CollisionChannel.ECC_PAWN
BLOCK = u.CollisionResponseType.ECR_BLOCK
OBJECTS = [getattr(u.ObjectTypeQuery, f'OBJECT_TYPE_QUERY{i}') for i in range(1, 7)]
CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
         'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')
CORRIDOR = 'Door_Tutorial_Corridor'
BEDROOM = 'Door_Tutorial_Bedroom'
CORRIDOR_FRAME = 'SM_Tutorial_Annex_DoorFrame_Corridor'
CORRIDOR_OLD_LEAF = 'SM_Tutorial_Annex_Door_Corridor_Closed'
STAGE2_OPEN = ('S2_Gate_04_Bars', 'S2_Gate_07_Bars')
STAGE2_PUZZLE = ('S2_Gate_02_Bars', 'S2_Gate_05_Bars', 'S2_Gate_11_Bars')
# x, y, visible mouth yaw. Probe candidates; the authored plan is separate.
CANDIDATES = {
    'BP_Tutorial_HideBasket': ((330, 60, 180), (315, 60, 180), (325, 95, 180), (310, 105, 180)),
    'BP_S1_banquet_Exit_HideBasket_Interaction': ((75, 350, 0), (70, 375, 0), (60, 350, 0)),
    'BP_S1_storage_HideBasket_26_Interaction': ((710, 1750, 0), (708, 1745, 0), (710, 1755, 0), (715, 1750, 0),
                                               (710, 1738, 0), (780, 1760, 0)),
    'S2_Basket_Room4': ((1680, 2360, -90), (1680, 2330, -90), (1660, 2355, -90), (1680, 2300, -90)),
    'S2_Basket_Room3': ((2400, 2070, -90), (2400, 2045, -90), (2350, 2070, -90),
                         (2440, 2040, -90), (2520, 1970, 180), (2400, 1970, -90)),
    'S2_Basket_Room2': ((2390, 2950, -90), (2350, 2930, -90), (2390, 2900, -90),
                         (2530, 2810, 180), (2500, 2800, 180), (2390, 2820, -90)),
}
PREFERRED = {
    'BP_Tutorial_HideBasket': ((330, 60, 180), (315, 60, 180), (325, 95, 180), (310, 105, 180)),
    'BP_S1_banquet_Exit_HideBasket_Interaction': ((75, 350, 0), (70, 375, 0)),
    'BP_S1_storage_HideBasket_26_Interaction': CANDIDATES['BP_S1_storage_HideBasket_26_Interaction'][:-1],
    'S2_Basket_Room4': ((1680, 2330, -90), (1660, 2355, -90)),
    'S2_Basket_Room3': ((2400, 2045, -90), (2440, 2040, -90), (2520, 1970, 180)),
    'S2_Basket_Room2': ((2390, 2950, -90), (2350, 2930, -90), (2530, 2810, 180)),
}


def path(obj):
    return obj.get_path_name() if obj else None


def v(vec):
    return [round(float(i), 4) for i in (vec.x, vec.y, vec.z)]


def rotation(rot):
    return [round(float(i), 4) for i in (rot.pitch, rot.yaw, rot.roll)]


def encode(value):
    if isinstance(value, u.Object):
        return path(value)
    if isinstance(value, u.Vector):
        return v(value)
    if isinstance(value, u.Rotator):
        return rotation(value)
    if isinstance(value, (u.Array, list, tuple)):
        return [encode(i) for i in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return value.export_text() if hasattr(value, 'export_text') else str(value)


def props(obj, names):
    return {n: encode(obj.get_editor_property(n)) for n in names}


def transform(actor):
    return [v(actor.get_actor_location()), rotation(actor.get_actor_rotation()), v(actor.get_actor_scale3d())]


def sha(p):
    with p.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def dirty():
    return sorted(p.get_name() for p in list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages()) +
                  list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def mesh(c):
    if isinstance(c, u.StaticMeshComponent):
        return c.get_editor_property('static_mesh')
    if isinstance(c, u.SkeletalMeshComponent):
        return c.get_editor_property('skeletal_mesh_asset')
    return None


def component(c):
    row = {'class': path(c.get_class())}
    if isinstance(c, u.SceneComponent):
        row.update(relative=props(c, ('relative_location', 'relative_rotation', 'relative_scale3d')),
                   visible=c.is_visible(), mobility=encode(c.get_editor_property('mobility')))
    if isinstance(c, u.PrimitiveComponent):
        row.update(collision=str(c.get_collision_enabled()), profile=str(c.get_collision_profile_name()),
                   hidden=c.get_editor_property('hidden_in_game'),
                   responses=[str(c.get_collision_response_to_channel(ch)) for ch in
                              (PAWN, u.CollisionChannel.ECC_VISIBILITY, u.CollisionChannel.ECC_WORLD_STATIC)])
    if isinstance(c, u.MeshComponent):
        row.update(mesh=path(mesh(c)), materials=[path(c.get_material(i)) for i in range(c.get_num_materials())])
    return row


def actor_snapshot(a):
    center, extent = a.get_actor_bounds(False)
    row = dict(path=path(a), label=a.get_actor_label(), cls=path(a.get_class()), transform=transform(a),
               tags=[str(tag) for tag in a.tags], attached_to=path(a.get_attach_parent_actor()),
               bounds=[v(center), v(extent)],
               components={c.get_name(): component(c) for c in a.get_components_by_class(u.ActorComponent)})
    if isinstance(a, u.CatrunHideBasket):
        row['properties'] = props(a, ('OpenDirectionLocal', 'ExternalBody', 'ExternalCloth'))
    if isinstance(a, u.CatrunDoor):
        row['properties'] = props(a, ('bStartOpen', 'OpenYaw', 'OpenDuration', 'ArmorPassageHalfWidth'))
        row['gate_center'] = v(a.get_editor_property('GateBox').get_world_location())
    if isinstance(a, u.CatrunStatuePuzzle):
        row['puzzle'] = [props(link, ('PuzzleId', 'Statue', 'Plate', 'Gate', 'ContactHalfExtent', 'SocketAxis',
                                      'GateFloorOffset')) for link in a.get_editor_property('Links')]
    if isinstance(a, (u.CatrunCandle, u.CatrunArmor)):
        row['patrol'] = props(a, ('PatrolPoints', 'bPatrolLoop'))
        if isinstance(a, u.CatrunCandle):
            row['patrol'].update(props(a, ('bPatrolEnabled', 'PatrolRelativePoints')))
    if isinstance(a, u.SoundGridManager):
        row['properties'] = props(a, ('Settings',))
    return row


def group(a):
    body = a.get_editor_property('ExternalBody')
    cloth = a.get_editor_property('ExternalCloth')
    c = [c for c in a.get_components_by_class(u.SceneComponent) if c.get_name() == 'HiddenPoint']
    assert len(c) == 1, (path(a), 'missing HiddenPoint')
    internal_body = next(x for x in a.get_components_by_class(u.StaticMeshComponent) if x.get_name() == 'BasketBody')
    internal_cloth = next((x for x in a.get_components_by_class(u.SkeletalMeshComponent) if x.get_name() == 'BasketCloth'), None)
    body_mesh = body.get_component_by_class(u.StaticMeshComponent) if body else internal_body
    return a, body, cloth, c[0], body_mesh, cloth or internal_cloth


def hitinfo(hit):
    if not hit:
        return None
    d = hit.to_dict()
    return {k: encode(d[k]) for k in ('blocking_hit', 'initial_overlap', 'location', 'impact_point', 'impact_normal', 'hit_actor', 'hit_component')}


def line(w, start, end, ignore, profile=None):
    if profile:
        return u.SystemLibrary.line_trace_single_by_profile(w, start, end, profile, False, ignore, NONE, False)
    return u.SystemLibrary.line_trace_single(w, start, end, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore, NONE, False)


def sweep(w, start, end, cap, ignore):
    return u.SystemLibrary.capsule_trace_single_by_profile(w, start, end, cap.get_scaled_capsule_radius(),
        cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, NONE, False)


def supported(w, surface, cap, ignore, up, down):
    lift = u.Vector(0, 0, cap.get_scaled_capsule_half_height())
    h = sweep(w, surface + lift + u.Vector(0, 0, up), surface + lift - u.Vector(0, 0, down), cap, ignore)
    if not h:
        return None, None
    d = h.to_dict()
    p, center = d['impact_point'], d['location']
    okay = d['blocking_hit'] and not d['initial_overlap'] and d['impact_normal'].z >= .65 \
        and not isinstance(d['hit_actor'], u.Pawn) \
        and math.hypot(p.x-center.x, p.y-center.y) <= max(0., cap.get_scaled_capsule_radius()-.15) \
        and surface.z-down-.01 <= p.z <= surface.z+up+.01
    return (u.Vector(surface.x, surface.y, center.z+2.) if okay else None), hitinfo(h)


def overlap(w, p, cap, ignore):
    cc = u.SystemLibrary.capsule_overlap_components(w, p, cap.get_scaled_capsule_radius(),
         cap.get_scaled_capsule_half_height(), OBJECTS, u.PrimitiveComponent, ignore) or []
    return sorted(path(c) for c in cc if c.get_collision_response_to_channel(PAWN) == BLOCK and
                  cap.get_collision_response_to_channel(c.get_collision_object_type()) == BLOCK)


def at(yaw):
    r = math.radians(yaw)
    return u.Vector(math.cos(r), math.sin(r), 0)


def angle(vec):
    return math.degrees(math.atan2(vec.y, vec.x))


def basket_geometry(w, origin, yaw, camera, cap, action, members, proposed):
    cat = cap.get_owner()
    front = at(yaw)
    start, support = supported(w, origin, cap, [cat]+members, 50., 100.)
    ignore = [cat]+members if proposed else [cat]
    entry, entry_hit = supported(w, origin + front*action.get_editor_property('EntryDistance'), cap, ignore, 0., 50.)
    approach_dist = min(100., action.get_editor_property('InteractionRange')-2.)
    approach, approach_hit = supported(w, origin+front*approach_dist, cap, ignore, 0., 50.)
    entry_sweep = sweep(w, approach, entry, cap, ignore) if entry and approach else None
    entry_sight = line(w, entry, origin, ignore) if entry else None
    entry_ok = bool(entry and approach and not entry_sweep and
                    (not entry_sight or entry_sight.to_dict()['hit_actor'] in members))
    camera_yaw = camera.get_world_rotation().yaw
    sector = math.floor((yaw-camera_yaw+22.5)/45.)
    directions = [('front', yaw)] + [(str(i), camera_yaw+(sector+i)*45.) for i in range(-2, 3)]
    exits = {}
    for key, heading in directions:
        landing, contact = supported(w, origin+at(heading)*action.get_editor_property('ExitDistance'), cap,
                                     [cat]+members, 50., 100.)
        transit = sweep(w, start, landing, cap, [cat]+members) if start and landing else None
        endpoint = overlap(w, landing, cap, ignore) if landing else None
        exits[key] = dict(yaw=heading, landing=v(landing) if landing else None, contact=contact,
                          transit=hitinfo(transit), blockers=endpoint, safe=bool(start and landing and not transit and not endpoint))
    # Geometric occlusion diagnostic at the front lip. Editor camera orientation is
    # known; its final game location, material fading, and lighting are not simulated.
    mouth = origin+front*38.+u.Vector(0, 0, 24.)
    camera_forward = camera.get_forward_vector()
    sight = line(w, mouth-camera_forward*1100., mouth, [cat]+members)
    back = line(w, origin+u.Vector(0, 0, 20.), origin-front*245.+u.Vector(0, 0, 20.), [cat]+members, 'Pawn')
    return dict(origin_support=support, entry=dict(safe=entry_ok, support=entry_hit, approach=approach_hit,
                    sweep=hitinfo(entry_sweep), sight=hitinfo(entry_sight)), exits=exits,
                camera_sight=hitinfo(sight), wall_behind=hitinfo(back),
                safe=entry_ok and all(i['safe'] for i in exits.values()))


def read_basket(w, basket, camera, cap, action):
    a, body, cloth, hidden, body_mesh, cloth_mesh = group(basket)
    members = [a]+([body] if body else [])
    if cloth and cloth.get_owner() not in members:
        members.append(cloth.get_owner())
    mouth = body_mesh.get_forward_vector()
    local_front = a.get_editor_property('OpenDirectionLocal')
    front = a.get_actor_forward_vector()*local_front.x + a.get_actor_right_vector()*local_front.y
    front = at(angle(front)) if math.hypot(front.x, front.y) > .0001 else front
    origin = hidden.get_world_location()
    row = dict(actors=[path(m) for m in members], hidden=v(origin), visual_mouth=v(mouth), front=v(front),
               body=path(body_mesh), cloth=path(cloth_mesh), current=basket_geometry(w, origin, angle(front), camera, cap, action, members, False),
               candidates=[])
    # For proposed locations traces ignore the old basket. Author/audit must
    # retest with the real relocated meshes and full restoration collision.
    for x, y, yaw in CANDIDATES.get(basket.get_actor_label(), ()):
        floor = line(w, u.Vector(x, y, 150), u.Vector(x, y, -100), [cap.get_owner()]+members, 'Pawn')
        d = floor.to_dict() if floor else None
        valid = d and d['blocking_hit'] and not d['initial_overlap'] and d['impact_normal'].z >= .65 \
            and 'SoundFloor' in [str(t) for t in d['hit_actor'].tags]
        result = None
        if valid:
            base_z = a.get_actor_location().z
            result = basket_geometry(w, u.Vector(x,y,d['impact_point'].z+origin.z-base_z), yaw, camera, cap, action, members, True)
        row['candidates'].append(dict(spec=[x,y,yaw], floor=hitinfo(floor), geometry=result))
    return row


def required_geometry(w, basket, camera, cap, action):
    """Use the actual relocated meshes and keep full endpoint collision enabled."""
    a, body, cloth, hidden, body_mesh, cloth_mesh = group(basket)
    members = [a]+([body] if body else [])
    if cloth and cloth.get_owner() not in members:
        members.append(cloth.get_owner())
    origin = hidden.get_world_location()
    local = a.get_editor_property('OpenDirectionLocal')
    mouth = body_mesh.get_forward_vector()
    front = a.get_actor_forward_vector()*local.x + a.get_actor_right_vector()*local.y
    front = at(angle(front)) if math.hypot(front.x, front.y) > .0001 else front
    g = basket_geometry(w, origin, angle(front), camera, cap, action, members, False)
    g.update(hidden=v(origin), visible_front=v(mouth), logical_front=v(front), body=path(body_mesh), cloth=path(cloth_mesh))
    front_aligned = (front-mouth).length() <= .001 and min(abs(front.x), abs(front.y)) <= .001
    if cloth_mesh:
        front_aligned = front_aligned and (front-cloth_mesh.get_forward_vector()).length() <= .001
    g['alignment_ok'] = front_aligned and abs(origin.x-body_mesh.get_world_location().x) <= .01 \
        and abs(origin.y-body_mesh.get_world_location().y) <= .01
    g['safe'] = g['safe'] and g['alignment_ok'] and not g['camera_sight'] and bool(g['wall_behind'])
    return g


def floor_at(w, x, y, ignore):
    h = line(w, u.Vector(x,y,150), u.Vector(x,y,-100), ignore, 'Pawn')
    d = h.to_dict() if h else None
    if d and d['blocking_hit'] and not d['initial_overlap'] and d['impact_normal'].z >= .65 \
            and 'SoundFloor' in [str(t) for t in d['hit_actor'].tags]:
        return d['impact_point'].z, hitinfo(h)
    return None, hitinfo(h)


def set_pose(a, location, yaw):
    a.modify()
    a.get_editor_property('root_component').modify()
    a.set_actor_location_and_rotation(location, u.Rotator(pitch=0., yaw=yaw, roll=0.), False, False)
    assert (a.get_actor_location()-location).length() < .01, path(a)
    assert (a.get_actor_forward_vector()-at(yaw)).length() < .001, path(a)


def move_basket(w, a, cap, spec, old_height):
    _, body, cloth, hidden, body_mesh, cloth_mesh = group(a)
    cloth_actor = cloth.get_owner() if cloth else None
    assert not body or (cloth_actor and cloth_actor not in (a, body)), path(a)
    members = [a]+([body] if body else [])+([cloth_actor] if cloth_actor else [])
    x, y, yaw = spec
    floor, hit = floor_at(w, x, y, [cap.get_owner()]+members)
    if floor is None:
        return hit, False
    pose = u.Vector(x,y,floor+old_height)
    bp_yaw = a.get_actor_rotation().yaw + yaw-body_mesh.get_world_rotation().yaw
    body_z = body.get_actor_location().z if body else a.get_actor_location().z
    cloth_delta = cloth_actor.get_actor_location().z-body_z if cloth_actor else 0.
    # Persist the explicit interaction front in actor space. The visible mouth
    # is mesh +X; the Blueprint can carry a distinct authored component yaw.
    a.modify()
    a.set_editor_property('OpenDirectionLocal', at(yaw-bp_yaw))
    set_pose(a, pose, bp_yaw)
    if body:
        set_pose(body, pose, yaw)
    if cloth_actor:
        set_pose(cloth_actor, pose+u.Vector(0,0,cloth_delta), yaw)
    _, final_body, final_cloth, anchor, visible, _ = group(a)
    assert body == final_body and cloth == final_cloth, path(a)
    assert abs(anchor.get_world_location().z - (pose.z+anchor.get_editor_property('relative_location').z)) < .1
    assert abs(visible.get_world_location().z-pose.z) < .1
    return hit, True


def clear_component(c):
    c.modify()
    c.set_static_mesh(None)
    c.set_collision_profile_name('NoCollision')
    c.set_visibility(False, False)
    c.set_hidden_in_game(True, False)


def open_doors(w, name, aa, cap, before):
    by = {a.get_actor_label(): a for a in aa}
    changed = []
    if name.endswith('Tutorial'):
        door = by[CORRIDOR]
        assert isinstance(door, u.CatrunDoor) and not by[BEDROOM].get_editor_property('bStartOpen')
        assert isinstance(by[CORRIDOR_FRAME], u.StaticMeshActor)
        door.modify()
        door.set_editor_property('bStartOpen', True)
        clear_component(door.get_editor_property('DoorMesh'))
        changed.append(door)
        # Older maps retain a separate static original leaf. Keep the actor
        # identity and references, but strip the mesh and its collision too.
        legacy = by.get(CORRIDOR_OLD_LEAF)
        if legacy:
            assert isinstance(legacy, u.StaticMeshActor)
            legacy.modify()
            clear_component(legacy.get_component_by_class(u.StaticMeshComponent))
            legacy.set_editor_property('tags', [tag for tag in legacy.tags if str(tag) != 'SoundWall'])
            changed.append(legacy)
    if name.endswith('Stage2'):
        directors = [a for a in aa if isinstance(a, u.CatrunStatuePuzzle)]
        assert len(directors) == 1
        links = directors[0].get_editor_property('Links')
        puzzle_gates = [link.get_editor_property('Gate') for link in links]
        assert {a.get_actor_label() for a in puzzle_gates} == set(STAGE2_PUZZLE)
        for label in STAGE2_OPEN:
            bars = by[label]
            assert isinstance(bars, u.StaticMeshActor) and bars not in puzzle_gates and before[label]['first_hit']
            assert by[label.replace('_Bars', '_Frame')].get_component_by_class(u.StaticMeshComponent)
            c = bars.get_component_by_class(u.StaticMeshComponent)
            assert 'RisingGate_Bars' in path(mesh(c)), label
            location = bars.get_actor_location()
            threshold, hit = floor_at(w, location.x, location.y, [cap.get_owner(),bars])
            assert threshold is not None, (label, hit)
            center, extent = bars.get_actor_bounds(False)
            below = (center.z+extent.z) - threshold + 15.
            assert 200. < below < 400., (label, below)
            c.modify()
            c.set_collision_profile_name('NoCollision')
            set_pose(bars, location-u.Vector(0,0,below), bars.get_actor_rotation().yaw)
            bars.set_editor_property('tags', [tag for tag in bars.tags if str(tag) != 'SoundWall'])
            changed.append(bars)
    return changed


def door_probes(w, name, aa, cap):
    by = {a.get_actor_label(): a for a in aa}
    if name.endswith('Tutorial'):
        assert all(label in by for label in (CORRIDOR, BEDROOM, CORRIDOR_FRAME)), sorted(by)
        items = [(CORRIDOR, (-330, 662), (-146, 662)), (BEDROOM, (-128, 390), (-128, 528))]
    elif name.endswith('Stage2'):
        assert all(label in by for label in STAGE2_OPEN+STAGE2_PUZZLE)
        items = [(STAGE2_OPEN[0], (1645, 2720), (1855, 2720)), (STAGE2_OPEN[1], (2535, 2350), (2535, 2570))]
    else:
        return {}
    out = {}
    for label, start, end in items:
        a = by[label]
        extra = [by[CORRIDOR_OLD_LEAF]] if label == CORRIDOR and CORRIDOR_OLD_LEAF in by else []
        p, q = (u.Vector(x,y,cap.get_scaled_capsule_half_height()+2.) for x,y in (start,end))
        cat = cap.get_owner()
        out[label] = dict(actor=actor_snapshot(a), old_static_leaf=[actor_snapshot(leaf) for leaf in extra],
            first_hit=hitinfo(sweep(w,p,q,cap,[cat])), without_leaf_actor=hitinfo(sweep(w,p,q,cap,[cat,a]+extra)),
            threshold_support=[hitinfo(line(w, u.Vector(x,y,120), u.Vector(x,y,-80), [cat], 'Pawn')) for x,y in
                               (start, ((start[0]+end[0])/2.,(start[1]+end[1])/2.), end)])
    return out


def tutorial_graphs():
    from editor_toolset.toolsets.blueprint import BlueprintTools as bp
    result = {}
    for p in ('/Game/Systems/LevelFlow/BP_LevelExit', '/Game/Cinematics/Transitions/Blueprints/BP_StairDescentDirector'):
        asset = u.load_asset(p)
        assert asset, p
        result[p] = [{'name': graph.get_name(), 'nodes': [
            {'name': node.node.get_name(), 'type': node.type_id,
             'inputs': [{'name': pin.name, 'value': str(pin.value), 'links': str(pin.connected_pins)} for pin in node.input_pins],
             'outputs': [{'name': pin.name, 'links': str(pin.connected_pins)} for pin in node.output_pins]}
            for node in bp.get_node_infos(bp.find_nodes(graph))]} for graph in bp.list_graphs(asset)]
    return result


def menu_snapshot():
    sys.path.insert(0, str(ROOT/'Scripts/Menu'))
    try:
        from menu_graph import audit
        asset = u.load_asset('/Game/UI/WBP_MainMenu')
        assert asset, 'Missing MainMenu widget Blueprint'
        return audit(asset)
    finally:
        sys.path.pop(0)


def grid(manager):
    return json.loads(manager.call_method('ExportBakedGridSnapshot'))


def hash_data(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def grid_delta(before, after, doors):
    stable = ('Origin', 'CellSize', 'Width', 'Height', 'Walkable', 'CostMultiplier')
    assert all(before[key] == after[key] for key in stable), 'Floor grid changed'
    changed = {}
    for key in ('EdgeMask', 'WallDistance'):
        changed[key] = []
        assert len(before[key]) == len(after[key])
        for i, (old, new) in enumerate(zip(before[key], after[key])):
            if abs(old-new) <= .001:
                continue
            x = before['Origin'][0] + (i % before['Width']+.5)*before['CellSize']
            y = before['Origin'][1] + (i // before['Width']+.5)*before['CellSize']
            if key == 'EdgeMask':
                assert int(old) & ~int(new) == 0 and any(abs(x-dx) <= 175 and abs(y-dy) <= 175 for dx,dy in doors), \
                    ('Unexpected closing or distant sound edge', x,y,old,new,doors)
            changed[key].append([i,x,y,old,new])
    return changed


def projected_segment_clear(a, b, center, extent, margin):
    start_t, end_t = 0., 1.
    for first, last, coord, reach in ((a.x,b.x,center.x,extent.x), (a.y,b.y,center.y,extent.y)):
        low, high = coord-reach-margin, coord+reach+margin
        if abs(last-first) < .000001:
            if first < low or first > high:
                return True
            continue
        t0, t1 = sorted(((low-first)/(last-first),(high-first)/(last-first)))
        start_t, end_t = max(start_t,t0), min(end_t,t1)
        if start_t > end_t:
            return True
    return False


def stage2_route_checks(aa, baskets):
    bodies = [group(b)[1] for b in baskets]
    assert all(bodies)
    boxes = {b.get_actor_label(): b.get_actor_bounds(True) for b in bodies}
    rows = []
    for a in aa:
        segments = []
        if isinstance(a, (u.CatrunArmor, u.CatrunCandle)):
            if isinstance(a, u.CatrunCandle) and not a.get_editor_property('bPatrolEnabled'):
                continue
            route = [a.get_actor_location()] + [p.get_actor_location() for p in a.get_editor_property('PatrolPoints') if p]
            if len(route) == 1 and isinstance(a, u.CatrunCandle):
                route += [u.MathLibrary.transform_location(a.get_actor_transform(), p) for p in a.get_editor_property('PatrolRelativePoints')]
            if len(route) > 1 and a.get_editor_property('bPatrolLoop'):
                route.append(route[1])
            elif len(route) == 1:
                route.append(route[0])
            margin = max([c.get_scaled_capsule_radius() for c in a.get_components_by_class(u.CapsuleComponent)] or [35.])+5.
            segments.extend((p,q,margin) for p,q in zip(route,route[1:]))
        if isinstance(a, u.CatrunStatuePuzzle):
            for link in a.get_editor_property('Links'):
                statue, plate = (link.get_editor_property(k) for k in ('Statue','Plate'))
                extent = statue.get_actor_bounds(False)[1]
                segments.append((statue.get_actor_location(),plate.get_actor_location(),math.hypot(extent.x,extent.y)+25.))
        for p,q,margin in segments:
            blockers = [label for label,(center,extent) in boxes.items() if not projected_segment_clear(p,q,center,extent,margin)]
            rows.append(dict(actor=a.get_actor_label(), start=v(p), end=v(q), margin=margin, blockers=blockers))
    assert rows and not any(r['blockers'] for r in rows), rows
    return rows


def check_doors(name, doors, actors):
    opened = (CORRIDOR,) if name.endswith('Tutorial') else STAGE2_OPEN if name.endswith('Stage2') else ()
    for label in opened:
        row = doors[label]
        assert not row['first_hit'], (label,row['first_hit'])
        assert all(h and h['impact_normal'][2] > .65 for h in row['threshold_support']), (label,row['threshold_support'])
        assert 'NO_COLLISION' in row['actor']['components'][
            'DoorMesh' if label == CORRIDOR else 'StaticMeshComponent0']['collision'], label
    if name.endswith('Tutorial'):
        assert doors[CORRIDOR]['actor']['properties']['bStartOpen']
        assert doors[CORRIDOR]['actor']['components']['DoorMesh']['mesh'] is None
        assert all(x['components']['StaticMeshComponent0']['mesh'] is None for x in doors[CORRIDOR]['old_static_leaf'])
        assert not doors[BEDROOM]['actor']['properties']['bStartOpen']
        assert doors[BEDROOM]['first_hit']['hit_actor'] == doors[BEDROOM]['actor']['path']
        assert CORRIDOR_FRAME in [i['label'] for i in actors.values()]
    if name.endswith('Stage2'):
        for label in STAGE2_OPEN:
            a = doors[label]['actor']
            center, extent = a['bounds']
            floor = doors[label]['threshold_support'][1]['impact_point'][2]
            assert center[2]+extent[2] < floor-5. and 'SoundWall' not in a['tags'], (label, center, extent, floor)


def preserve_actors(before, after, owned):
    assert before.keys() == after.keys(), 'Actor added or removed'
    changed = [k for k in before if before[k] != after[k]]
    assert set(changed) <= set(owned), [(k,before[k]['label']) for k in changed if k not in owned]
    return [after[k]['label'] for k in changed]


def file_hashes():
    # Hash all content, including unsaved git edits, to catch accidental writes.
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'Content').rglob('*'))
            if p.suffix in ('.umap','.uasset')}


def report_proof(report):
    proof_path = Path(globals()['CATRUN_BASKET_DOORS_PROOF']).resolve()
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    assert proof['completed'] and proof['mode'] == ('verify' if MODE == 'apply' else 'apply')
    assert proof['pid'] != report['pid'] and proof['script_sha256'] == report['script_sha256']
    assert proof['content_after'] == report['content_before'], 'Saved content changed after proof'
    report['proof'] = str(proof_path)
    return proof


def main(report):
    command = u.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and '-catrunbasketdoorsisolated' in command, 'Fresh commandlet only'
    assert not ED.get_game_world() and not dirty(), ('Unexpected dirty packages', dirty())
    report['cvars'] = {k: u.SystemLibrary.get_console_variable_int_value(k) for k in CVARS}
    assert all(i == 0 for i in report['cvars'].values()), report['cvars']
    assert MODE in ('probe','verify','apply','audit'), MODE
    report['pid'] = os.getpid()
    report['script_sha256'] = sha(ROOT/'Scripts/GameplayRepair/repair_basket_doors.py')
    if MODE == 'probe':
        report['tutorial_graphs'] = tutorial_graphs()
        try:
            report['main_menu'] = menu_snapshot()
        except Exception:
            report['main_menu_error'] = traceback.format_exc()
    else:
        report['content_before'] = file_hashes()
    proof = report_proof(report) if MODE in ('apply','audit') else None
    if MODE == 'apply':
        report['backups'] = {}
        for name in MAPS:
            rel = f'Content/Maps/{name}.umap'
            dest = OUT/'Before'/rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/rel, dest)
            assert sha(dest) == report['content_before'][rel]
            report['backups'][name] = {'file': str(dest), 'sha256': sha(dest)}
    for name in MAPS:
        assert not dirty() and LEVEL.load_level('/Game/Maps/'+name), name
        w = ED.get_editor_world()
        aa = list(ACTORS.get_all_level_actors())
        cat, = [a for a in aa if a.get_class().get_name() == 'BP_Cat_C']
        camera_actor, = [a for a in aa if a.get_class().get_name() == 'BP_QuarterViewCamera_C']
        cap = cat.get_component_by_class(u.CapsuleComponent)
        action = cat.get_component_by_class(u.CatrunBasketInteractionComponent)
        camera = camera_actor.get_component_by_class(u.CameraComponent)
        assert cap and action and camera, name
        mapfile = ROOT/'Content/Maps'/f'{name}.umap'
        baskets = [a for a in aa if isinstance(a, u.CatrunHideBasket)]
        assert len(baskets) == (1 if name.endswith('Tutorial') else 2 if name.endswith('Stage1') else 3), name
        row = dict(sha256=sha(mapfile), world=path(w), camera=dict(actor=path(camera_actor), rotation=rotation(camera.get_world_rotation())),
                   capsule=[cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()],
                   actors={}, baskets={}, doors={})
        report['maps'][name] = row
        row['actors'] = {a.get_name(): actor_snapshot(a) for a in aa}
        row['doors'] = door_probes(w, name, aa, cap)
        if MODE == 'probe':
            for basket in baskets:
                row['baskets'][basket.get_actor_label()] = read_basket(w, basket, camera, cap, action)
            assert not dirty() and sha(mapfile) == row['sha256'], (name, dirty())
            print('BASKET_DOORS_PROBED', name, len(baskets), len(row['doors']))
            continue
        manager, = [a for a in aa if isinstance(a, u.SoundGridManager)]
        saved_grid = grid(manager)
        row['grid_before_sha256'] = hash_data(saved_grid)
        if MODE == 'audit':
            expected = proof['maps'][name]
            assert row['actors'] == expected['actors_after'], ('Cold actor snapshot changed',name,
                [(k,row['actors'][k]['label']) for k in row['actors'].keys() & expected['actors_after'].keys()
                 if row['actors'][k] != expected['actors_after'][k]][:25])
            assert row['grid_before_sha256'] == expected['grid_after_sha256'], (name,'cold grid changed')
            check_doors(name, row['doors'], row['actors'])
            for b in baskets:
                g = required_geometry(w,b,camera,cap,action)
                row['baskets'][b.get_actor_label()] = g
                assert g['safe'], (name,b.get_actor_label(),g)
            if name.endswith('Stage2'):
                row['routes'] = stage2_route_checks(aa,baskets)
            assert not dirty() and sha(mapfile) == row['sha256'], (name, dirty())
            print('BASKET_DOORS_AUDITED', name, len(baskets))
            continue
        expected = proof['maps'][name] if MODE == 'apply' else None
        if expected:
            assert row['actors'] == expected['actors'] and row['grid_before_sha256'] == expected['grid_before_sha256'], name
        manager.build_grid()
        baseline = grid(manager)
        row['fresh_baseline_sha256'] = hash_data(baseline)
        row['baked_grid_preexisting_drift'] = [k for k in baseline if baseline[k] != saved_grid.get(k)]
        changed_doors = open_doors(w, name, aa, cap, row['doors'])
        owned = [a.get_name() for a in changed_doors]
        row['plan'] = {}
        for b in baskets:
            a, body, cloth, _, body_mesh, _ = group(b)
            members = [a]+([body] if body else [])+([cloth.get_owner()] if cloth else [])
            old = body_mesh.get_world_location()
            floor, hit = floor_at(w,old.x,old.y,[cat]+members)
            assert floor is not None, (name,a.get_actor_label(),hit)
            label = a.get_actor_label()
            tries = [expected['plan'][label]] if expected else PREFERRED[label]
            canonical = name.removeprefix('SoundTest_')
            if name != canonical:
                tries = [report['maps'][canonical]['plan'][label]]
            row['baskets'][label] = []
            owned.extend(m.get_name() for m in members)
            for spec in tries:
                hit, moved = move_basket(w, a, cap, spec, old.z-floor)
                g = required_geometry(w,a,camera,cap,action) if moved else None
                row['baskets'][label].append(dict(spec=list(spec),floor=hit,geometry=g))
                if g and g['safe']:
                    row['plan'][label] = list(spec)
                    break
            assert label in row['plan'], (name,label,'No complete aligned, visible, capsule-clear pose')
        if name.endswith('Stage2'):
            row['routes'] = stage2_route_checks(aa,baskets)
        manager.build_grid()
        after_grid = grid(manager)
        row['grid_after_sha256'] = hash_data(after_grid)
        doors = [(1750,2720),(2535,2460)] if name.endswith('Stage2') else [(-228,662)] if name.endswith('Tutorial') else []
        row['grid_changes'] = grid_delta(baseline,after_grid,doors)
        row['actors_after'] = {a.get_name(): actor_snapshot(a) for a in aa}
        row['changed_actors'] = preserve_actors(row['actors'],row['actors_after'],owned)
        row['doors_after'] = door_probes(w,name,aa,cap)
        check_doors(name,row['doors_after'],row['actors_after'])
        assert set(dirty()) <= {'/Game/Maps/'+name}, ('Unrelated dirty asset', dirty())
        if expected:
            assert row['plan'] == expected['plan'] and row['actors_after'] == expected['actors_after'] and \
                   row['grid_after_sha256'] == expected['grid_after_sha256'], ('Apply differs from verified plan', name)
            assert LEVEL.save_current_level(), name
            row['saved_sha256'] = sha(mapfile)
        else:
            u.EditorLoadingAndSavingUtils.new_blank_map(False)
            assert sha(mapfile) == row['sha256'], name
        assert not dirty(), (name, dirty())
        print('BASKET_DOORS_'+MODE.upper(), name, len(baskets), row['plan'])
    if MODE != 'probe':
        report['content_after'] = file_hashes()
        before,after = report['content_before'],report['content_after']
        assert before.keys() == after.keys(), 'Unexpected asset add/delete'
        report['changed_files'] = [key for key in before if before[key] != after[key]]
        expected = {f'Content/Maps/{name}.umap' for name in MAPS} if MODE == 'apply' else set()
        assert set(report['changed_files']) == expected, (MODE, report['changed_files'])


report = {'mode': MODE, 'maps': {}, 'completed': False, 'scope': 'Saved collision and authored configuration; no gameplay, renders, or input.'}
OUT.mkdir(parents=True, exist_ok=True)
try:
    main(report)
    report['completed'] = True
except Exception:
    report['error'] = traceback.format_exc()
finally:
    (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CATRUN_BASKET_DOORS_REPORT', str(OUT/'report.json'), report['completed'])
if not report['completed']:
    raise RuntimeError(report['error'])
