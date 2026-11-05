"""Isolated Stage2 basket probe/author/cold audit; root alone invokes this script.

Set CATRUN_STAGE2_BASKET_MODE to probe (default), author, or audit. Author needs
CATRUN_STAGE2_BASKET_PROOF pointing at a successful probe report; audit needs
that variable pointing at the author report. No PIE or shared asset writes.
Run with -run=pythonscript -catrunStage2BasketsIsolated and the calibrated four
async/deferred physics CVars disabled (root's run_editor_script.ps1 -Geometry).
"""
import datetime
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import shutil
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayRepair20261105/Stage2Baskets' / datetime.datetime.now().strftime('%H%M%S-%f')
MODE = str(globals().get('CATRUN_STAGE2_BASKET_MODE', 'probe')).lower()
MAPS = ('Stage2', 'SoundTest_Stage2')
OWN_TAG = 'Stage2HideBaskets20261105'
# Current-layout candidates; changing ANY value invalidates previous proof.
PLACEMENTS = (
    ('Room4', 1680., 2300., 0., -1.),
    ('Room3', 2400., 1970., -1., -1.),
    ('Room2', 2390., 2820., -1., -1.),
)
BASE = '/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/'
BP_PATH = '/Game/Systems/Interaction/Hiding/BP_HideBasket'
BODY_PATH = BASE + 'Meshes/SM_HideBasket'
CLOTH_PATH = BASE + 'Meshes/SK_HideBasket_Cloth'
MAT_BODY = BASE + 'Materials/M_HideBasket_AgedRattan_001'
MAT_CLOTH = BASE + 'Materials/M_HideBasket_Cloth_Linen'
ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
NONE = unreal.DrawDebugTrace.NONE
PAWN = unreal.CollisionChannel.ECC_PAWN
BLOCK = unreal.CollisionResponseType.ECR_BLOCK
CHANNELS = [getattr(unreal.CollisionChannel, 'ECC_' + n) for n in
            ('WORLD_STATIC', 'WORLD_DYNAMIC', 'PAWN', 'PHYSICS_BODY', 'VEHICLE', 'DESTRUCTIBLE')]
OBJECTS = [getattr(unreal.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
REPORT = {'mode': MODE, 'maps': {}, 'completed': False, 'errors': [], 'query_count': 0,
          'limits': ['Geometry is saved-scene evidence, not actual TryInteract/cloth/mark gameplay evidence.',
                     'Snapshots cover actor/component transforms, references, collision, meshes/materials, patrols, puzzle links and cameras; not every private native field.',
                     'Native full grid rebuild follows current geometry; relocation increases are bounded to old bodies and decreases to new bodies.',
                     'Static-grid BFS does not simulate runtime gates, patrols, or puzzle completion.']}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def v(p):
    return [round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6)]


def rot(p):
    return [round(float(p.pitch), 6), round(float(p.yaw), 6), round(float(p.roll), 6)]


def encode(value):
    if isinstance(value, unreal.Object):
        return value.get_path_name()
    if isinstance(value, unreal.Vector):
        return v(value)
    if isinstance(value, unreal.Rotator):
        return rot(value)
    if isinstance(value, (list, tuple, unreal.Array)):
        return [encode(i) for i in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'export_text'):
        return value.export_text()
    return str(value)


def dirty():
    return sorted(p.get_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def require_clean():
    assert not ED.get_game_world(), 'Refuse active gameplay'
    assert not dirty(), ('Unexpected dirty packages; never auto-save', dirty())


def all_actors():
    return list(ACTORS.get_all_level_actors())


def refs(obj):
    result = {}
    for name in dir(obj):
        if name.startswith('_'):
            continue
        try:
            value = getattr(obj, name)
            if isinstance(value, unreal.Object):
                result[name] = encode(value)
            elif isinstance(value, unreal.Array) and value and all(isinstance(i, unreal.Object) or i is None for i in value):
                result[name] = encode(value)
        except Exception:
            pass
    return result


def properties(obj, names):
    result = {}
    for name in names:
        try:
            result[name] = encode(obj.get_editor_property(name))
        except Exception:
            pass  # Heterogeneous actors do not expose all these fields.
    return result


def component(c):
    row = {'class': encode(c.get_class()), 'references': refs(c)}
    if isinstance(c, unreal.SceneComponent):
        row.update(location=v(c.get_world_location()), rotation=rot(c.get_world_rotation()),
                   scale=v(c.get_world_transform().scale3d), relative=properties(c, ('relative_location', 'relative_rotation', 'relative_scale3d')),
                   visible=c.is_visible(), mobility=str(c.get_editor_property('mobility')))
    if isinstance(c, unreal.PrimitiveComponent):
        row.update(profile=str(c.get_collision_profile_name()), collision=str(c.get_collision_enabled()),
                   object_type=str(c.get_collision_object_type()),
                   responses={str(ch): str(c.get_collision_response_to_channel(ch)) for ch in CHANNELS})
    if isinstance(c, unreal.MeshComponent):
        row['materials'] = [encode(c.get_material(i)) for i in range(c.get_num_materials())]
    if isinstance(c, unreal.StaticMeshComponent):
        row['mesh'] = encode(c.get_editor_property('static_mesh'))
    if isinstance(c, unreal.SkeletalMeshComponent):
        row.update(mesh=encode(c.get_editor_property('skeletal_mesh_asset')), animation_mode=str(c.get_animation_mode()))
    if isinstance(c, unreal.CameraComponent):
        row['camera'] = properties(c, ('projection_mode', 'ortho_width', 'field_of_view', 'aspect_ratio'))
    if isinstance(c, unreal.SpringArmComponent):
        row['arm'] = properties(c, ('target_arm_length', 'socket_offset', 'target_offset'))
    return row


def snapshot(owned=False):
    result = {}
    for a in all_actors():
        if (OWN_TAG in [str(t) for t in a.tags]) != owned:
            continue
        result[a.get_name()] = {
            'label': a.get_actor_label(), 'class': encode(a.get_class()),
            'location': v(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation()),
            'scale': v(a.get_actor_scale3d()), 'tags': [str(t) for t in a.tags],
            'references': refs(a), 'properties': properties(a, (
                'OpenDirectionLocal', 'ExternalBody', 'ExternalCloth', 'PatrolPoints', 'PatrolRelativePoints',
                'bPatrolEnabled', 'bPatrolLoop', 'PatrolSpeed', 'PatrolPauseSeconds', 'Settings', 'Links',
                'bStartOpen', 'OpenYaw', 'OpenDuration', 'ArmorPassageHalfWidth', 'player_bell_budget_override')),
            'components': {c.get_name(): component(c) for c in a.get_components_by_class(unreal.ActorComponent)}}
    return result


def count():
    REPORT['query_count'] += 1
    assert REPORT['query_count'] <= 1000, 'Basket-only query budget exceeded'


def hitdata(hit):
    return {k: encode(value) for k, value in hit.to_dict().items()} if hit else None


def floor(w, x, y, ignore):
    count()
    hit = unreal.SystemLibrary.line_trace_single_by_profile(w, unreal.Vector(x, y, 150),
        unreal.Vector(x, y, -100), 'Pawn', False, ignore, NONE, False)
    assert hit, ('No actual collision floor', x, y)
    d = hit.to_dict()
    assert d['blocking_hit'] and not d['initial_overlap'] and d['impact_normal'].z >= .65
    assert 'SoundFloor' in [str(t) for t in d['hit_actor'].tags], ('Not a tagged map floor', hitdata(hit))
    return d['impact_point'].z, hitdata(hit)


def support(w, surface, cap, ignore, above=50., below=100.):
    reference = surface + unreal.Vector(0, 0, cap.get_scaled_capsule_half_height())
    count()
    hit = unreal.SystemLibrary.capsule_trace_single_by_profile(w, reference + unreal.Vector(0, 0, above),
        reference - unreal.Vector(0, 0, below), cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(),
        'Pawn', False, ignore, NONE, False)
    if not hit:
        return None, None
    d = hit.to_dict()
    p, center = d['impact_point'], d['location']
    if not d['blocking_hit'] or d['initial_overlap'] or d['impact_normal'].z < .65 or isinstance(d['hit_actor'], unreal.Pawn) \
            or math.hypot(p.x-center.x, p.y-center.y) > max(0., cap.get_scaled_capsule_radius()-.15) \
            or p.z > surface.z+above+.01 or p.z < surface.z-below-.01:
        return hitdata(hit), None
    return hitdata(hit), unreal.Vector(surface.x, surface.y, center.z + 2.)


def blocked(w, center, cap, ignore):
    count()
    comps = unreal.SystemLibrary.capsule_overlap_components(w, center, cap.get_scaled_capsule_radius(),
        cap.get_scaled_capsule_half_height(), OBJECTS, unreal.PrimitiveComponent, ignore) or []
    return [encode(c) for c in comps if c.get_collision_response_to_channel(PAWN) == BLOCK
            and cap.get_collision_response_to_channel(c.get_collision_object_type()) == BLOCK]


def sweep(w, start, end, cap, ignore, visibility=False):
    count()
    if visibility:
        return unreal.SystemLibrary.capsule_trace_single(w, start, end, cap.get_scaled_capsule_radius(),
            cap.get_scaled_capsule_half_height(), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore, NONE, False)
    return unreal.SystemLibrary.capsule_trace_single_by_profile(w, start, end, cap.get_scaled_capsule_radius(),
        cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, NONE, False)


def validate_geometry(w, basket, body, cap, action, camera_yaw):
    anchor = next(c for c in basket.get_components_by_class(unreal.SceneComponent) if c.get_name() == 'HiddenPoint')
    origin = anchor.get_world_location()
    local = basket.get_editor_property('OpenDirectionLocal')
    front = basket.get_actor_forward_vector()*local.x + basket.get_actor_right_vector()*local.y
    front_angle = math.degrees(math.atan2(front.y, front.x))
    sector = math.floor((((front_angle-camera_yaw+180.) % 360.-180.)+22.5)/45.) % 8
    ignore = [cap.get_owner(), basket, body]
    start_hit, start = support(w, origin, cap, ignore)
    assert start is not None, ('No full-capsule hidden-origin floor support', start_hit)
    exits = []
    for offset in (-2, -1, 0, 1, 2):
        angle = math.radians(camera_yaw + (sector + offset)*45.)
        direction = unreal.Vector(math.cos(angle), math.sin(angle), 0)
        target = origin + direction * action.get_editor_property('ExitDistance')
        floor_hit, landing = support(w, target, cap, ignore)
        row = {'sector_offset': offset, 'direction': v(direction), 'support': floor_hit, 'safe': False}
        if landing is not None:
            transit = sweep(w, start, landing, cap, ignore)
            restored = blocked(w, landing, cap, [cap.get_owner()])
            row.update(landing=v(landing), transit=hitdata(transit), restore_blockers=restored,
                       safe=not transit and not restored)
        exits.append(row)
    # Native entry is supported with its narrower [surface-50,surface] window;
    # support/LOS include the basket, exactly as TestEntry does.
    entry_surface = origin + front * action.get_editor_property('EntryDistance')
    entry_hit, entry = support(w, entry_surface, cap, [cap.get_owner()], 0., 50.)
    approach_hit, approach = support(w, origin + front * 100., cap, [cap.get_owner()], 0., 50.)
    entry_row = {'support': entry_hit, 'approach_support': approach_hit, 'safe': False}
    if entry is not None and approach is not None:
        travel = sweep(w, approach, entry, cap, [cap.get_owner()], True)
        count()
        sight = unreal.SystemLibrary.line_trace_single(w, entry, origin, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [cap.get_owner()], NONE, False)
        sight_actor = sight.to_dict()['hit_actor'] if sight else None
        distance = (approach-origin).length()
        entry_row.update(approach=v(approach), entry=v(entry), approach_distance=distance,
                         transit=hitdata(travel), sight=hitdata(sight),
                         safe=not travel and (not sight or sight_actor in (basket, body))
                              and 50. < distance < action.get_editor_property('InteractionRange'))
    return {'anchor': encode(anchor), 'hidden': v(origin), 'front_world': v(front),
            'origin_support': start_hit, 'entry': entry_row, 'exits': exits,
            'safe': entry_row['safe'] and all(r['safe'] for r in exits)}


def load(path):
    asset = unreal.load_asset(path)
    assert asset, ('Missing existing asset', path)
    return asset


def owned_trio(room):
    label = 'S2_Basket_' + room
    actors = all_actors()
    found = []
    for suffix in ('', '_Body', '_Cloth'):
        matches = [a for a in actors if a.get_actor_label() == label+suffix]
        assert len(matches) <= 1, ('Duplicate owned label', label+suffix)
        if matches:
            assert OWN_TAG in [str(t) for t in matches[0].tags], 'Refuse to adopt an unrelated actor'
        found.append(matches[0] if matches else None)
    assert all(found) or not any(found), ('Incomplete owned trio; inspect manually', label)
    return found


def place(w, spec, cat):
    room, x, y, fx, fy = spec
    trio = owned_trio(room)
    z, floor_hit = floor(w, x, y, [cat] + [a for a in trio if a])
    # Root's working first Stage1 template: body yaw0, BP yaw90, local front
    # (0,-1) => world +X. Keep the internal -90-degree meshes aligned as well.
    theta = math.degrees(math.atan2(fy, fx))
    # Unreal Python's positional constructor is roll,pitch,yaw. Use names so
    # heading can never accidentally tilt a body or HiddenPoint into the floor.
    body_rot = unreal.Rotator(pitch=0., yaw=theta, roll=0.)
    bp_rot = unreal.Rotator(pitch=0., yaw=theta+90., roll=0.)
    loc = unreal.Vector(x, y, z)
    if not trio[0]:
        trio = [ACTORS.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH), loc, bp_rot),
                ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, loc, body_rot),
                ACTORS.spawn_actor_from_class(unreal.SkeletalMeshActor, loc+unreal.Vector(0,0,2.5), body_rot)]
        assert all(trio), 'Basket trio spawn failed'
    basket, body, cloth = trio
    trace = {}
    assert isinstance(basket, unreal.CatrunHideBasket) and isinstance(body, unreal.StaticMeshActor) \
        and isinstance(cloth, unreal.SkeletalMeshActor)
    for actor, suffix in zip(trio, ('', '_Body', '_Cloth')):
        actor.set_actor_label('S2_Basket_' + room + suffix)
        actor.set_folder_path('Gameplay/Hiding/Stage2')
        actor.set_editor_property('tags', [OWN_TAG] + (['InteriorProp', 'SoundObstacle'] if actor == body else []))
        actor.set_actor_scale3d(unreal.Vector(1,1,1))
        actor.set_actor_location_and_rotation(loc+unreal.Vector(0,0,2.5 if actor == cloth else 0),
                                               bp_rot if actor == basket else body_rot, False, False)
    trace['after_initial_transform'] = [
        {'actor': encode(a), 'location': v(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation())} for a in trio]
    bc = body.get_component_by_class(unreal.StaticMeshComponent)
    bc.set_static_mesh(load(BODY_PATH))
    bc.set_material(0, load(MAT_BODY))
    bc.set_mobility(unreal.ComponentMobility.STATIC)
    bc.set_collision_profile_name('BlockAll')
    bc.set_simulate_physics(False)
    cc = cloth.get_component_by_class(unreal.SkeletalMeshComponent)
    cc.set_skeletal_mesh_asset(load(CLOTH_PATH))
    cc.set_material(0, load(MAT_CLOTH))
    cc.set_mobility(unreal.ComponentMobility.MOVABLE)
    cc.set_collision_profile_name('NoCollision')
    cc.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    basket.set_editor_property('ExternalBody', body)
    basket.set_editor_property('ExternalCloth', cc)
    basket.set_editor_property('OpenDirectionLocal', unreal.Vector(0,-1,0))
    trace['after_property_edits'] = [
        {'actor': encode(a), 'location': v(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation())} for a in trio]
    # Apply the intended transform after all actor property notifications too.
    for actor in trio:
        actor.set_actor_location_and_rotation(loc+unreal.Vector(0,0,2.5 if actor == cloth else 0),
                                               bp_rot if actor == basket else body_rot, False, False)
    # Actor property-change notifications may reconstruct BP components. Read
    # them AFTER the final actor-property edit, and configure the current ones.
    for c in basket.get_components_by_class(unreal.MeshComponent):
        c.set_visibility(False, False)
        c.set_hidden_in_game(True, False)
        c.set_collision_profile_name('NoCollision')
    anchor = next(c for c in basket.get_components_by_class(unreal.SceneComponent) if c.get_name() == 'HiddenPoint')
    anchor.set_relative_location(unreal.Vector(0,0,26.25), False, False)
    assert basket.get_editor_property('ExternalBody') == body and basket.get_editor_property('ExternalCloth') == cc
    assert cc.get_owner() == cloth and anchor.get_owner() == basket, {
        'cloth': encode(cloth), 'cloth_component': encode(cc), 'cloth_owner': encode(cc.get_owner()),
        'basket': encode(basket), 'anchor': encode(anchor), 'anchor_owner': encode(anchor.get_owner())}
    trace['final'] = [
        {'actor': encode(a), 'location': v(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation())} for a in trio]
    trace['local_front'] = v(basket.get_editor_property('OpenDirectionLocal'))
    actual_front = basket.get_actor_right_vector() * -1.
    expected_front = unreal.Vector(fx,fy,0) / math.hypot(fx,fy)
    assert (actual_front-expected_front).length() < .001, ('Unexpected actual front', trace, v(actual_front), v(expected_front))
    for actor, expected in ((basket,bp_rot),(body,body_rot),(cloth,body_rot)):
        actual = actor.get_actor_rotation()
        yaw_delta = (actual.yaw-expected.yaw+180.) % 360.-180.
        assert abs(actual.pitch) < .001 and abs(actual.roll) < .001 and abs(yaw_delta) < .001, ('Unexpected tilt/heading', trace)
    assert (anchor.get_world_location()-(loc+unreal.Vector(0,0,26.25))).length() < .001, ('HiddenPoint transform drifted', trace)
    return trio, floor_hit, trace


def grid(manager):
    return json.loads(manager.call_method('ExportBakedGridSnapshot'))


def grid_diff(before, after):
    """Persist the actual changed cells/values, including failures, for review."""
    result = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        if isinstance(old,list) and isinstance(new,list) and key != 'Origin' and len(old) == len(new):
            changes = []
            for i, (a,b) in enumerate(zip(old,new)):
                if a != b:
                    changes.append({'cell': i, 'before': a, 'after': b,
                        'center': [before['Origin'][0]+(i % before['Width']+.5)*before['CellSize'],
                                   before['Origin'][1]+(i // before['Width']+.5)*before['CellSize']]})
            result[key] = {'count': len(changes), 'changes': changes}
        else:
            result[key] = {'before': old, 'after': new}
    return result


def segment_clear(a, b, body, margin):
    """Conservative 2D swept-circle corridor against the actual body AABB."""
    center, extent = body.get_actor_bounds(False)
    low = (center.x-extent.x-margin, center.y-extent.y-margin)
    high = (center.x+extent.x+margin, center.y+extent.y+margin)
    enter, leave = 0., 1.
    for start, end, lo, hi in zip((a.x,a.y), (b.x,b.y), low, high):
        delta = end-start
        if abs(delta) < 1.e-8:
            if start < lo or start > hi:
                return True
            continue
        near, far = sorted(((lo-start)/delta, (hi-start)/delta))
        enter, leave = max(enter,near), min(leave,far)
        if enter > leave:
            return True
    return False


def route_clearance(bodies):
    rows = []
    for actor in all_actors():
        if isinstance(actor, (unreal.CatrunCandle, unreal.CatrunArmor)):
            points = list(actor.get_editor_property('PatrolPoints'))
            if isinstance(actor, unreal.CatrunCandle):
                if not actor.get_editor_property('bPatrolEnabled'):
                    continue
                if points:
                    route = [p.get_actor_location() for p in points if p]
                else:
                    route = [unreal.MathLibrary.transform_location(actor.get_actor_transform(), p)
                             for p in actor.get_editor_property('PatrolRelativePoints')]
            else:
                route = [p.get_actor_location() for p in points if p]
            if not route:
                route = [actor.get_actor_location()]
            else:
                route = [actor.get_actor_location()] + route
                if actor.get_editor_property('bPatrolLoop'):
                    route.append(route[1])
            capsules = actor.get_components_by_class(unreal.CapsuleComponent)
            margin = max([c.get_scaled_capsule_radius() for c in capsules] or [35.]) + 5.
            for i in range(max(1,len(route)-1)):
                a, b = route[i], route[min(i+1,len(route)-1)]
                clear = all(segment_clear(a,b,body,margin) for body in bodies)
                rows.append({'actor': encode(actor), 'segment': [v(a),v(b)], 'margin': margin, 'clear': clear,
                             'authored_patrol_point_count': len(points),
                             'route_source': 'PatrolPoints' if points else ('PatrolRelativePoints' if len(route)>1 else 'stationary authored post')})
        if isinstance(actor, unreal.CatrunStatuePuzzle):
            for link in actor.get_editor_property('Links'):
                statue, plate = link.get_editor_property('Statue'), link.get_editor_property('Plate')
                assert statue and plate
                e = statue.get_actor_bounds(False)[1]
                margin = math.hypot(e.x,e.y) + 25.
                a, b = statue.get_actor_location(), plate.get_actor_location()
                clear = all(segment_clear(a,b,body,margin) for body in bodies)
                rows.append({'statue': encode(statue), 'plate': encode(plate), 'segment': [v(a),v(b)],
                             'margin': margin, 'clear': clear})
    assert rows, 'No existing routes/puzzle corridors found to validate'
    return rows


def verify_changed_edges(w, manager, before, control):
    settings = manager.get_editor_property('Settings')
    assert settings
    z = control['Origin'][2] + settings.get_editor_property('TraceHeight')
    wall_tag = str(settings.get_editor_property('WallTag'))
    rows = []
    width, height = int(control['Width']), int(control['Height'])
    assert before['Width'] == width and before['Height'] == height
    for cell in range(width*height):
        for bit, dx, dy in ((0,1,0),(2,0,1)):
            nx, ny = cell % width+dx, cell // width+dy
            if nx >= width or ny >= height:
                continue
            other = ny*width+nx
            if not control['Walkable'][cell] or not control['Walkable'][other]:
                continue
            old_open = bool(int(before['EdgeMask'][cell]) & (1 << bit))
            current_open = bool(int(control['EdgeMask'][cell]) & (1 << bit))
            if old_open == current_open:
                continue
            start = unreal.Vector(control['Origin'][0]+(cell % width+.5)*control['CellSize'],
                                  control['Origin'][1]+(cell // width+.5)*control['CellSize'],z)
            end = start+unreal.Vector(dx*control['CellSize'],dy*control['CellSize'],0)
            count()
            hits = unreal.SystemLibrary.line_trace_multi_for_objects(w,start,end,[OBJECTS[0]],True,[],NONE,False) or []
            walls = [encode(h.to_dict()['hit_actor']) for h in hits if h.to_dict()['hit_actor']
                     and wall_tag in [str(t) for t in h.to_dict()['hit_actor'].tags]]
            rows.append({'cell': cell, 'other': other, 'before_open': old_open, 'control_open': current_open,
                         'start': v(start), 'end': v(end), 'tagged_walls': walls,
                         'matches_geometry': current_open == (not walls)})
    return rows


def grid_paths(g):
    """Bounded static-grid reachability, explicitly excluding dynamic gate state."""
    width, height = int(g['Width']), int(g['Height'])
    size, ox, oy = g['CellSize'], g['Origin'][0], g['Origin'][1]
    def center(cell):
        return [ox+(cell % width+.5)*size,oy+(cell // width+.5)*size]
    def in_bounds(p, bounds):
        return bounds is None or bounds[0] <= p[0] <= bounds[2] and bounds[1] <= p[1] <= bounds[3]
    def cell_for(point, clearance, bounds):
        x, y = math.floor((point[0]-ox)/size),math.floor((point[1]-oy)/size)
        candidates = []
        for dy in range(-2,3):
            for dx in range(-2,3):
                nx,ny = x+dx,y+dy
                if 0 <= nx < width and 0 <= ny < height:
                    c = ny*width+nx
                    if g['Walkable'][c] and g['WallDistance'][c] >= clearance and in_bounds(center(c),bounds):
                        candidates.append(c)
        assert candidates, ('No nearby walkable anchor',point,clearance)
        return min(candidates,key=lambda c:math.hypot(center(c)[0]-point[0],center(c)[1]-point[1]))
    rows = []
    def check(label, a, b, clearance=0., bounds=None):
        first,last = cell_for(a,clearance,bounds),cell_for(b,clearance,bounds)
        todo, parents = deque([first]),{first:None}
        while todo and last not in parents:
            c = todo.popleft()
            for bit,dx,dy in ((0,1,0),(1,-1,0),(2,0,1),(3,0,-1)):
                if not int(g['EdgeMask'][c]) & (1 << bit):
                    continue
                x,y = c % width+dx,c // width+dy
                if not 0 <= x < width or not 0 <= y < height:
                    continue
                n = y*width+x
                if n not in parents and g['Walkable'][n] and g['WallDistance'][n] >= clearance and in_bounds(center(n),bounds):
                    parents[n] = c
                    todo.append(n)
            assert len(parents) <= width*height
        row = {'label':label,'requested':[a,b],'snapped':[center(first),center(last)],'clearance':clearance,
               'bounds':bounds,'reachable':last in parents,'visited':len(parents),
               'assumption':'Static baked cardinal graph only; runtime door/gate/puzzle state is not simulated.'}
        rows.append(row)
    drawing = json.loads((ROOT/'Saved/Stage2BuildOct07/drawing.json').read_text(encoding='utf-8'))
    rooms = {r['id']:[p*100. for p in r['lab']] for r in drawing['rooms']}
    for room,point in rooms.items():
        check('hall_to_'+room,rooms['hall'],point)
    for index,opening in enumerate(drawing['openings']):
        if opening['t'] != 'cat':
            continue
        x,y,length = opening['x']*100.,opening['y']*100.,opening['len']*100.
        if opening['o'] == 'h':
            x += length*.5
            a,b,bounds = [x,y-50.],[x,y+50.],[x-length*.5-20,y-80,x+length*.5+20,y+80]
        else:
            y += length*.5
            a,b,bounds = [x-50.,y],[x+50.,y],[x-80,y-length*.5-20,x+80,y+length*.5+20]
        check('cat_hole_'+str(index)+'_local_crossing',a,b,0.,bounds)
    # The drawing's room2 armor route is design intent, not an authored patrol.
    planned = drawing['armors'][1]['path']
    for i in range(len(planned)-1):
        check('drawing_planned_room2_armor_'+str(i),[v*100 for v in planned[i]],
              [v*100 for v in planned[i+1]],35.,[1750,2460,2650,3060])
    for room,x,y,fx,fy in PLACEMENTS:
        angle = math.atan2(fy,fx)
        a,b = [[x+170*math.cos(angle+d),y+170*math.sin(angle+d)] for d in (-math.pi/4,math.pi/4)]
        check('planned_armor_clearance_in_front_of_'+room,a,b,35.,[x-210,y-210,x+210,y+210])
    return rows


def body_bounds(body):
    center,extent = body.get_actor_bounds(False)
    return {'actor':encode(body),'center':v(center),'extent':v(extent)}


def refresh_grid(manager, before, baseline, bodies, old_bounds, row):
    manager.build_grid()
    after = grid(manager)
    # Record complete native outputs and both deltas BEFORE any validation.
    row['grid_after_native_rebake'] = after
    row['grid_saved_to_post_diff'] = grid_diff(before,after)
    row['grid_baseline_to_post_diff'] = grid_diff(baseline,after)
    assert before.keys() == after.keys()
    for key in before:
        if key != 'WallDistance':
            assert baseline[key] == after[key], ('Basket insertion changed freshly rebuilt grid topology/floor/edge; refuse save', key)
    # Root authorizes the existing native full bake against current geometry.
    # Separate old-derived-data drift from the isolated insertion impact.
    assert before['Origin'] == baseline['Origin'] and before['CellSize'] == baseline['CellSize']
    assert before['Width'] == baseline['Width'] and before['Height'] == baseline['Height']
    assert len(before['WallDistance']) == len(baseline['WallDistance']) == len(after['WallDistance'])
    new_bounds = [body_bounds(body) for body in bodies]
    row['old_body_bounds'],row['new_body_bounds'] = old_bounds,new_bounds
    changes = []
    for i, (old, new) in enumerate(zip(baseline['WallDistance'], after['WallDistance'])):
        if abs(old-new) <= .001:
            continue
        x = before['Origin'][0] + (i % before['Width'] + .5)*before['CellSize']
        y = before['Origin'][1] + (i // before['Width'] + .5)*before['CellSize']
        influence = old_bounds if new > old else new_bounds
        assert any(math.hypot(x-b['center'][0],y-b['center'][1])
                   <= baseline['WallProbeLength']+math.hypot(b['extent'][0],b['extent'][1])+1.
                   for b in influence), ('Nonlocal relocation clearance delta',i,old,new)
        changes.append({'cell':i,'center':[x,y],'before':old,'after':new,
                        'cause':'old_body_removal' if new > old else 'new_body_placement'})
    row['grid_body_insertion_changes'] = changes
    return after, changes


def discard():
    # Explicitly discard probe-only world/dirty packages; never save them.
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    require_clean()


def main():
    assert MODE in ('probe', 'author', 'audit')
    command = unreal.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and '-catrunstage2basketsisolated' in command, 'Fresh isolated root commandlet only'
    require_clean()
    REPORT['pid'] = __import__('os').getpid()
    REPORT['cvars'] = {k: unreal.SystemLibrary.get_console_variable_int_value(k) for k in (
        'Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
        'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')}
    assert all(value == 0 for value in REPORT['cvars'].values())
    source_paths = ['Scripts/Stage2/place_hide_baskets.py', 'Saved/Stage2BuildOct07/drawing.json',
                    'Saved/GameplayRepair20261105/Stage2Baskets/template-inspection.json']
    source_paths += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'Source/Catrun/Interaction').glob('*Basket*') if p.is_file()]
    source_paths += ['Source/Catrun/Perception/CatrunGroundSupport.cpp', 'Source/Catrun/Perception/CatrunSafeRestore.cpp',
                     'Source/Catrun/Grid/CatrunGridData.cpp', 'Source/Catrun/Sound/SoundGridManager.cpp']
    REPORT['source_hashes'] = {p: digest(ROOT/p) for p in source_paths}
    REPORT['placements'] = [list(s) for s in PLACEMENTS]
    # Hash all content so no protected asset save can slip through unnoticed.
    content_before = {str(p.relative_to(ROOT)).replace('\\','/'): digest(p)
                      for p in sorted((ROOT/'Content').rglob('*')) if p.suffix in ('.uasset','.umap')}
    REPORT['content_before'] = content_before
    proof = None
    if MODE != 'probe':
        proof_path = Path(globals()['CATRUN_STAGE2_BASKET_PROOF']).resolve()
        proof = json.loads(proof_path.read_text(encoding='utf-8'))
        assert proof['completed'] and not proof['errors']
        assert proof['mode'] == ('probe' if MODE == 'author' else 'author')
        assert proof['source_hashes'] == REPORT['source_hashes'] and proof['placements'] == REPORT['placements']
        assert proof['pid'] != REPORT['pid'], 'Proof/audit must run in independent processes'
        expected_hashes = proof['content_before'] if MODE == 'author' else proof['content_after']
        assert content_before == expected_hashes, 'Saved content changed after proof; rerun probe'
        REPORT['proof'] = str(proof_path)
    if MODE == 'author':
        # BOTH exact maps backed up and hashed before any map mutation/save.
        REPORT['backups'] = {}
        for name in MAPS:
            source = ROOT / ('Content/Maps/'+name+'.umap')
            target = OUT / 'Before/Content/Maps' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            assert digest(target) == digest(source)
            REPORT['backups'][name] = {'path': str(target), 'sha256': digest(target)}
    for name in MAPS:
        require_clean()
        assert LEVEL.load_level('/Game/Maps/'+name)
        require_clean()
        w = ED.get_editor_world()
        aa = all_actors()
        cats = [a for a in aa if a.get_class().get_name() == 'BP_Cat_C']
        managers = [a for a in aa if isinstance(a, unreal.SoundGridManager)]
        cameras = [a for a in aa if a.get_class().get_name() == 'BP_QuarterViewCamera_C']
        assert len(cats) == len(managers) == len(cameras) == 1
        cat, manager = cats[0], managers[0]
        cap = cat.get_component_by_class(unreal.CapsuleComponent)
        action = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
        assert cap and action
        assert cap.get_collision_object_type() == PAWN and all(cap.get_collision_response_to_channel(c) == BLOCK for c in CHANNELS)
        assert str(action.get_editor_property('ObstacleChannel')) == str(unreal.CollisionChannel.ECC_VISIBILITY)
        camera_yaw = cameras[0].get_component_by_class(unreal.CameraComponent).get_world_rotation().yaw
        before, before_grid = snapshot(), grid(manager)
        row = {'nonowned_before': before, 'owned_before':snapshot(True), 'grid_before': before_grid, 'baskets': {}, 'camera_yaw': camera_yaw,
               'capsule': {'radius': cap.get_scaled_capsule_radius(), 'half_height': cap.get_scaled_capsule_half_height()}}
        REPORT['maps'][name] = row
        # This revision relocates the existing nine owned actors, never respawns.
        existing = [owned_trio(spec[0]) for spec in PLACEMENTS]
        assert all(all(trio) for trio in existing), 'Relocation requires all three complete existing trios'
        old_bounds = [body_bounds(trio[1]) for trio in existing]
        row['old_body_bounds'] = old_bounds
        if MODE != 'audit':
            # Diagnose an already stale bake separately from the new baskets.
            manager.build_grid()
            row['grid_baseline_rebaked'] = grid(manager)
            row['grid_saved_to_baseline_diff'] = grid_diff(before_grid,row['grid_baseline_rebaked'])
            manager.build_grid()
            row['grid_control_repeat'] = grid(manager)
            assert row['grid_control_repeat'] == row['grid_baseline_rebaked'], 'Pre-basket native control bake is nondeterministic'
            row['changed_edge_geometry'] = verify_changed_edges(w,manager,before_grid,row['grid_baseline_rebaked'])
            assert all(r['matches_geometry'] for r in row['changed_edge_geometry']), 'Rebuilt changed cardinal edge contradicts current tagged-wall physics'
        if MODE == 'audit':
            assert snapshot(True) == proof['maps'][name]['owned_after'], 'Cold owned actor/reference/numeric snapshot differs'
            assert before == proof['maps'][name]['nonowned_before'], 'Cold unrelated actor snapshot differs'
            assert before_grid == proof['maps'][name]['grid_after'], 'Cold saved grid differs'
        bodies = []
        for spec in PLACEMENTS:
            if MODE == 'audit':
                trio = owned_trio(spec[0])
                assert all(trio), 'Saved trio absent'
                basket, body, cloth = trio
                assert basket.get_editor_property('ExternalBody') == body
                assert basket.get_editor_property('ExternalCloth') == cloth.get_component_by_class(unreal.SkeletalMeshComponent)
                floor_hit = None
                transform_trace = None
            else:
                trio, floor_hit, transform_trace = place(w, spec, cat)
                basket, body, cloth = trio
            bodies.append(body)
            geom = validate_geometry(w, basket, body, cap, action, camera_yaw)
            row['baskets'][spec[0]] = {'actors': [encode(a) for a in trio], 'floor': floor_hit, 'geometry': geom,
                                     'transform_trace': transform_trace}
        row['route_clearance'] = route_clearance(bodies)
        assert all(r['geometry']['safe'] for r in row['baskets'].values()), ('Basket entry or one of five allowed exits unsafe; never bypass', name)
        assert all(r['clear'] for r in row['route_clearance']), ('Existing AI/statue route corridor intersects a basket body', name)
        assert len([a for a in all_actors() if OWN_TAG in [str(t) for t in a.tags]]) == 9
        if MODE != 'audit':
            row['grid_after'], row['grid_changes'] = refresh_grid(manager, before_grid, row['grid_baseline_rebaked'], bodies, old_bounds, row)
        else:
            row['grid_after'] = before_grid
        row['grid_reachability'] = grid_paths(row['grid_after'])
        assert all(r['reachable'] for r in row['grid_reachability']), 'Required static-grid room/cat-hole/planned-armor reachability failed'
        row['owned_after'] = snapshot(True)
        assert set(row['owned_after']) == set(row['owned_before']), 'Relocation replaced or duplicated an owned actor'
        assert snapshot() == before, 'Unrelated actor/component/reference state changed'
        if MODE == 'author':
            baseline = proof['maps'][name]
            assert before == baseline['nonowned_before'] and before_grid == baseline['grid_before']
            assert row['owned_before'] == baseline['owned_before'], 'Owned actor state changed after relocation probe'
            assert row['owned_after'] == baseline['owned_after'] and row['grid_after'] == baseline['grid_after'], 'Author differs from validated probe'
            assert set(dirty()) <= {'/Game/Maps/'+name}, ('Shared package dirtied', dirty())
            assert LEVEL.save_current_level()
            require_clean()
            row['saved'] = True
        else:
            discard()
    content_after = {str(p.relative_to(ROOT)).replace('\\','/'): digest(p)
                     for p in sorted((ROOT/'Content').rglob('*')) if p.suffix in ('.uasset','.umap')}
    assert content_before.keys() == content_after.keys(), 'Unexpected new/deleted content'
    changed = [p for p in content_before if content_before[p] != content_after[p]]
    allowed = ['Content/Maps/'+name+'.umap' for name in MAPS] if MODE == 'author' else []
    assert set(changed) <= set(allowed), ('Out-of-scope asset save', changed)
    REPORT['content_after'], REPORT['changed_files'] = content_after, changed
    require_clean()
    REPORT['completed'] = True


OUT.mkdir(parents=True, exist_ok=True)
try:
    main()
except Exception:
    REPORT['errors'].append(traceback.format_exc())
finally:
    (OUT/'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CATRUN_STAGE2_BASKETS_REPORT', str(OUT/'report.json'), 'completed', REPORT['completed'])
if REPORT['errors']:
    raise RuntimeError(REPORT['errors'][-1])
