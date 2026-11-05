"""Root-owned saved first-basket AS probe and narrowly gated front authoring.

Run in a NEW Python commandlet with -catrunBasketDirectionIsolated and the
previously calibrated process-only async mesh/skinned/deferred-physics flags.
Never runs PIE, ticks gameplay, injects input, captures frames or changes a view.
Default PROBE is read-only. Root may set CATRUN_BASKET_MODE='apply' only after
reviewing a prior probe, passing its report path and confirming camera-source
review. Run 'audit' in another fresh process after authoring for cold evidence.
"""
import datetime
import hashlib
import json
import math
import shutil
import traceback
from pathlib import Path

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUT = ROOT / 'Saved/GameplayRepair20261105/BasketDirection' / datetime.datetime.now().strftime('%H%M%S-%f')
MAPS = ('Stage1', 'SoundTest_Stage1')
TARGET = 'BP_HideBasket_C_1'
HISTORICAL_FRONT = unreal.Vector(-1, 1, 0)
MODE = str(globals().get('CATRUN_BASKET_MODE', 'probe')).lower()
ED = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
NONE = unreal.DrawDebugTrace.NONE
PAWN = unreal.CollisionChannel.ECC_PAWN
BLOCK = unreal.CollisionResponseType.ECR_BLOCK
OBJECTS = [getattr(unreal.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
CHANNELS = [getattr(unreal.CollisionChannel, 'ECC_' + n) for n in
            ('WORLD_STATIC', 'WORLD_DYNAMIC', 'PAWN', 'PHYSICS_BODY', 'VEHICLE', 'DESTRUCTIBLE')]
REPORT = {'mode': MODE, 'maps': {}, 'errors': [], 'completed': False, 'query_count': 0,
          'asset_application_complete': False,
          'limits': ['Saved geometry and current-process effective settings; no user gameplay state sampled',
                     'Saved camera/component transforms plus Blueprint source are recorded; no live camera cache sampled',
                     'Preview/CanExit fields in traces below are native-policy predictions; actual component regression is separate',
                     'Dynamic blockers, cloth animation and live override ownership require later human gameplay verification']}


def v(p):
    return [round(p.x, 6), round(p.y, 6), round(p.z, 6)]


def rot(r):
    return [round(r.pitch, 6), round(r.yaw, 6), round(r.roll, 6)]


def dirty():
    return sorted(p.get_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(x):
    if isinstance(x, unreal.Vector):
        return v(x)
    if isinstance(x, unreal.Object):
        return x.get_path_name()
    return x if isinstance(x, (str, int, float, bool)) or x is None else str(x)


def hit_dict(hit):
    return {k: encode(value) for k, value in hit.to_dict().items()} if hit else None


def count():
    REPORT['query_count'] += 1
    assert REPORT['query_count'] <= 400, 'Bounded basket-only probe exceeded its query budget'


def floor(w, point, ignore):
    count()
    return unreal.SystemLibrary.line_trace_single(w, point + unreal.Vector(0, 0, 50),
        point - unreal.Vector(0, 0, 100), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore, NONE, False)


def endpoint(w, point, cap, ignore):
    count()
    components = unreal.SystemLibrary.capsule_overlap_components(w, point, cap.get_scaled_capsule_radius(),
        cap.get_scaled_capsule_half_height(), OBJECTS, unreal.PrimitiveComponent, ignore) or []
    rows = [{'component': c.get_path_name(), 'actor': c.get_owner().get_path_name(),
             'other_to_pawn': str(c.get_collision_response_to_channel(PAWN)),
             'capsule_to_other': str(cap.get_collision_response_to_channel(c.get_collision_object_type())),
             'blocking': c.get_collision_response_to_channel(PAWN) == BLOCK
                         and cap.get_collision_response_to_channel(c.get_collision_object_type()) == BLOCK}
            for c in components]
    return {'overlaps': rows, 'blocked': any(r['blocking'] for r in rows)}


def direction(yaw, forward_axis, right_axis):
    a = math.radians(yaw)
    x = math.cos(a) * forward_axis - math.sin(a) * right_axis
    y = math.sin(a) * forward_axis + math.cos(a) * right_axis
    length = math.hypot(x, y)
    return unreal.Vector(x / length, y / length, 0) if length > 1.e-8 else unreal.Vector()


def world_front(actor, local):
    d = actor.get_actor_forward_vector() * local.x + actor.get_actor_right_vector() * local.y
    length = math.hypot(d.x, d.y)
    return unreal.Vector(d.x / length, d.y / length, 0) if length > 1.e-8 else unreal.Vector()


def sector(d, yaw):
    angle = (math.degrees(math.atan2(d.y, d.x)) - yaw + 180) % 360 - 180
    return math.floor((angle + 22.5) / 45) % 8


def allowed(d, front, yaw):
    if math.hypot(d.x, d.y) < 1.e-8 or math.hypot(front.x, front.y) < 1.e-8:
        return False
    delta = abs(sector(d, yaw) - sector(front, yaw))
    return min(delta, 8 - delta) <= 2


def capsule_support(w, reference, cap, ignore, above=50., below=100.):
    """CatrunGround::FindSupport equivalent for the asserted current Pawn responses.

    Native uses explicit actual object channel/responses. This script refuses a
    capsule that differs from the verified Pawn profile; it never substitutes
    that profile for custom native responses.
    """
    count()
    hit = unreal.SystemLibrary.capsule_trace_single_by_profile(w, reference + unreal.Vector(0, 0, above),
        reference - unreal.Vector(0, 0, below), cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(),
        'Pawn', False, ignore, NONE, False)
    if not hit:
        return hit, None
    data = hit.to_dict()
    if not data['blocking_hit'] or data['initial_overlap'] or data['impact_normal'].z < .65 \
            or isinstance(data['hit_actor'], unreal.Pawn):
        return hit, None
    contact, center = data['impact_point'], data['location']
    if math.hypot(contact.x - center.x, contact.y - center.y) > max(0., cap.get_scaled_capsule_radius() - .15) \
            or center.z < reference.z - below - .01 or center.z > reference.z + above + .01:
        return hit, None
    return hit, unreal.Vector(reference.x, reference.y, center.z + 2.)


def surface_support(w, reference, cap, ignore, above=50., below=100.):
    """Match basket callers' former surface-ray window without extending drops."""
    hit, center = capsule_support(w, reference + unreal.Vector(0, 0, cap.get_scaled_capsule_half_height()),
                                  cap, ignore, above, below)
    if center is None:
        return hit, None
    contact_z = hit.to_dict()['impact_point'].z
    if contact_z > reference.z + above + .01 or contact_z < reference.z - below - .01:
        return hit, None
    return hit, center


def geometry(w, origin, desired, distance, cap, ignore):
    candidate = origin + desired * distance
    start_hit, start = surface_support(w, origin, cap, ignore)
    end_hit, landing = surface_support(w, candidate, cap, ignore)
    row = {'candidate_before_floor': v(candidate), 'origin_floor': hit_dict(start_hit),
           'landing_floor': hit_dict(end_hit), 'support_policy': 'CatrunGround::FindSupport + original surface-window conversion/check',
           'origin_center_ray_diagnostic': hit_dict(floor(w, origin, ignore)),
           'landing_center_ray_diagnostic': hit_dict(floor(w, candidate, ignore)), 'safe': False}
    if start is None or landing is None:
        return row
    transit_endpoint = endpoint(w, landing, cap, ignore)
    # Full restoration profile intentionally ignores ONLY the cat, including basket/body again.
    restore_endpoint = endpoint(w, landing, cap, [cap.get_owner()])
    count()
    transit = unreal.SystemLibrary.capsule_trace_single_by_profile(w, start, landing,
        cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, NONE, False)
    row.update(grounded_start=v(start), exact_landing=v(landing), transit_endpoint=transit_endpoint,
               full_restore_endpoint=restore_endpoint, transit=hit_dict(transit),
               safe=not transit_endpoint['blocked'] and not restore_endpoint['blocked'] and not transit)
    return row


def actor_snapshot(a):
    return {'path': a.get_path_name(), 'location': v(a.get_actor_location()), 'rotation': rot(a.get_actor_rotation()),
            'scale': v(a.get_actor_scale3d()), 'front': v(a.get_editor_property('OpenDirectionLocal')),
            'body': encode(a.get_editor_property('ExternalBody')), 'cloth': encode(a.get_editor_property('ExternalCloth'))}


def support_diagnostic(w, origin, desired, distance, cap, ignore):
    """Retain the bounded seam samples alongside the current common support policy."""
    target = origin + desired * distance
    rays = []
    for dx in (-4, -2, 0, 2, 4):
        for dy in (-4, -2, 0, 2, 4):
            h = floor(w, target + unreal.Vector(dx, dy, 0), ignore)
            rays.append({'offset': [dx, dy], 'hit': hit_dict(h)})
    for radius in (10, 18, 20):
        for i in range(8):
            a = i * math.pi / 4
            h = floor(w, target + unreal.Vector(radius * math.cos(a), radius * math.sin(a), 0), ignore)
            rays.append({'radius': radius, 'angle_index': i, 'hit': hit_dict(h)})
    down, landing = surface_support(w, target, cap, ignore)
    row = {'support_samples': rays, 'capsule_floor_hit': hit_dict(down), 'shape_supported': False,
           'production_support_policy': 'CatrunGround::FindSupport + original surface-window conversion/check'}
    if landing is None:
        return row
    source, start = surface_support(w, origin, cap, ignore)
    if start is None:
        return row
    count()
    transit = unreal.SystemLibrary.capsule_trace_single_by_profile(w, start, landing,
        cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(), 'Pawn', False, ignore, NONE, False)
    restored = endpoint(w, landing, cap, [cap.get_owner()])
    row.update(shape_supported=True, landing=v(landing), grounded_start=v(start), transit=hit_dict(transit),
               full_restore_endpoint=restored, diagnostic_clear=not transit and not restored['blocked'])
    return row


def graph_snapshot(bp):
    return [{'name': g.get_name(), 'nodes': [
        {'name': i.node.get_name(), 'type': i.type_id,
         'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in i.input_pins],
         'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in i.output_pins]}
        for i in BP.get_node_infos(BP.find_nodes(g))]} for g in BP.list_graphs(bp)]


def mapping_snapshot(context):
    result = []
    for mapping in context.get_editor_property('DefaultKeyMappings').get_editor_property('Mappings'):
        action = mapping.get_editor_property('Action')
        modifiers = []
        for modifier in mapping.get_editor_property('Modifiers'):
            row = {'path': modifier.get_path_name(), 'class': modifier.get_class().get_name()}
            if isinstance(modifier, unreal.InputModifierNegate):
                row['axes'] = {n: modifier.get_editor_property(n) for n in ('bX', 'bY', 'bZ')}
            elif isinstance(modifier, unreal.InputModifierSwizzleAxis):
                row['order'] = str(modifier.get_editor_property('Order'))
            modifiers.append(row)
        result.append({'action': encode(action),
                       'key': str(mapping.get_editor_property('Key').get_editor_property('KeyName')),
                       'modifiers': modifiers,
                       'triggers': [encode(t) for t in mapping.get_editor_property('Triggers')]})
    return result


def probe(w, name):
    aa = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
    by = {a.get_name(): a for a in aa}
    basket, cat = by[TARGET], by['BP_Cat_C_0']
    cap = cat.get_component_by_class(unreal.CapsuleComponent)
    action = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
    cameras = [a for a in aa if a.get_class().get_name() == 'BP_QuarterViewCamera_C']
    assert len(cameras) == 1, 'Expected exactly one authored gameplay camera'
    camera = cameras[0]
    camera_component = camera.get_component_by_class(unreal.CameraComponent)
    assert camera_component, 'Missing actual gameplay CameraComponent'
    yaw = camera_component.get_world_rotation().yaw
    camera_row = {'actor': camera.get_path_name(), 'actor_rotation': rot(camera.get_actor_rotation()),
                  'component': camera_component.get_path_name(), 'world_rotation': rot(camera_component.get_world_rotation()),
                  'relative_rotation': rot(camera_component.get_editor_property('relative_rotation')), 'arms': []}
    for arm in camera.get_components_by_class(unreal.SpringArmComponent):
        camera_row['arms'].append({'path': arm.get_path_name(), 'world_rotation': rot(arm.get_world_rotation()),
            'relative_rotation': rot(arm.get_editor_property('relative_rotation')),
            'use_pawn_control_rotation': arm.get_editor_property('bUsePawnControlRotation'),
            'absolute_rotation': arm.get_editor_property('bAbsoluteRotation')})
    assert str(action.get_editor_property('ObstacleChannel')) == str(unreal.CollisionChannel.ECC_VISIBILITY)
    assert cap.get_collision_object_type() == PAWN and all(cap.get_collision_response_to_channel(c) == BLOCK for c in CHANNELS), \
        'Pawn-profile sweep differs from actual capsule responses; native custom-response probe required'
    assert abs(cap.get_world_rotation().pitch) < .001 and abs(cap.get_world_rotation().roll) < .001
    anchor = next(c for c in basket.get_components_by_class(unreal.SceneComponent) if c.get_name() == 'HiddenPoint')
    origin = anchor.get_world_location()
    body = basket.get_editor_property('ExternalBody')
    ignore = [cat, basket] + ([body] if body else [])
    floor_calibration = floor(w, unreal.Vector(origin.x - 82, origin.y, 50), [cat])
    count()
    blocker_calibration = unreal.SystemLibrary.line_trace_single_by_profile(w,
        unreal.Vector(origin.x, origin.y - 10, origin.z + 180), unreal.Vector(origin.x, origin.y - 10, origin.z - 60),
        'Pawn', False, [cat], NONE, False)
    assert floor_calibration and 'StaticMeshActor_4' in str(hit_dict(floor_calibration)), 'Saved floor calibration failed'
    assert blocker_calibration and body.get_name() in str(hit_dict(blocker_calibration)), 'Positive physical blocker calibration failed'
    front = world_front(basket, basket.get_editor_property('OpenDirectionLocal'))
    candidate_front = world_front(basket, HISTORICAL_FRONT)
    keys = {slot: unreal.CatrunInputBindings.get_effective_key(getattr(unreal.CatrunInputSlot, slot.upper()))
            for slot in ('Forward', 'Back', 'Left', 'Right', 'Interact')}
    physical = ('A', 'S')
    key_names = {slot: str(key.get_editor_property('KeyName')) for slot, key in keys.items()}
    axes = [int(key_names['Forward'] in physical) - int(key_names['Back'] in physical),
            int(key_names['Right'] in physical) - int(key_names['Left'] in physical)]
    desired = direction(yaw, *axes)
    assert math.hypot(desired.x, desired.y) > 0, 'Physical AS is not a directional input under effective settings'
    # WA is explicitly the prior selection for this trace; AS geometry is queried separately.
    previous = direction(yaw, 1, -1)
    actual_geom = geometry(w, origin, desired, action.get_editor_property('ExitDistance'), cap, ignore)
    support = support_diagnostic(w, origin, desired, action.get_editor_property('ExitDistance'), cap, ignore)
    previous_geom = geometry(w, origin, previous, action.get_editor_property('ExitDistance'), cap, ignore)
    variants = {}
    for title, opening in (('saved_front', front), ('historical_A_front_candidate', candidate_front)):
        allow = allowed(desired, opening, yaw)
        selected = desired if allow else previous
        if not allowed(selected, opening, yaw):
            selected = opening
        selected_geometry = actual_geom if v(selected) == v(desired) else previous_geom if v(selected) == v(previous) else \
            geometry(w, origin, selected, action.get_editor_property('ExitDistance'), cap, ignore)
        mask = [allowed(direction(yaw + i * 45, 1, 0), opening, yaw) for i in range(8)]
        assert sum(mask) == 5, 'Per-instance five-sector policy changed'
        variants[title] = {'front_world': v(opening), 'front_sector': sector(opening, yaw), 'allowed_sector_mask': mask,
                           'desired_allowed': allow, 'selected_before': v(previous), 'selected_after': v(selected),
                           'predicted_CanExit': selected_geometry['safe'], 'predicted_preview_visible': selected_geometry['safe']}
    row = {'basket': actor_snapshot(basket), 'all_baskets': [actor_snapshot(a) for a in aa if isinstance(a, unreal.CatrunHideBasket)],
           'camera': camera_row, 'capsule': {'radius': cap.get_scaled_capsule_radius(), 'half_height': cap.get_scaled_capsule_half_height(),
               'profile': str(cap.get_collision_profile_name()), 'responses': {str(c): str(cap.get_collision_response_to_channel(c)) for c in CHANNELS}},
           'hidden_component': anchor.get_path_name(), 'hidden_world': v(origin), 'native_cached_hidden': v(basket.get_hidden_location()),
           'calibration': {'floor': hit_dict(floor_calibration), 'positive_blocker': hit_dict(blocker_calibration)},
           'effective_keys': {k: {'key': str(value.get_editor_property('KeyName')), 'display': str(unreal.InputLibrary.key_get_display_name(value))} for k, value in keys.items()},
           'physical_input': ['A', 'S'], 'semantic_axes_forward_right': axes, 'camera_yaw': yaw, 'AS_world_direction': v(desired),
           'AS_sector': sector(desired, yaw), 'AS_geometry': actual_geom, 'AS_support_diagnostic': support,
           'WA_previous_geometry': previous_geom, 'selection_trace': variants}
    REPORT['maps'][name] = row
    return row, basket


def main():
    command = unreal.SystemLibrary.get_command_line().lower()
    assert '-run=pythonscript' in command and '-catrunbasketdirectionisolated' in command, 'Root-owned isolated commandlet only'
    assert MODE in ('probe', 'apply', 'audit')
    assert not ED.get_game_world() and not dirty(), 'Fresh commandlet must be idle and clean'
    REPORT['process_cvars'] = {c: unreal.SystemLibrary.get_console_variable_int_value(c) for c in (
        'Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
        'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')}
    assert all(value == 0 for value in REPORT['process_cvars'].values())
    REPORT['dirty_before'] = dirty()
    settings = unreal.CatrunUserSettings.get_catrun_user_settings()
    REPORT['effective_settings_object'] = encode(settings)
    REPORT['effective_settings_source'] = 'current engine settings singleton' if settings else 'native default fallback; persisted user binding state unproven'
    REPORT['source_hashes'] = {p: digest(ROOT / p) for p in (
        'Source/Catrun/Interaction/BasketExitMath.h', 'Source/Catrun/Interaction/CatrunBasketInteractionComponent.cpp',
        'Source/Catrun/Perception/CatrunGroundSupport.h', 'Source/Catrun/Perception/CatrunGroundSupport.cpp',
        'Source/Catrun/Perception/CatrunSafeRestore.cpp',
        'Source/Catrun/Settings/CatrunInputBindings.cpp', 'Source/Catrun/LevelFlow/CatrunLevelFlow.cpp')}
    REPORT['blueprint_graphs'] = {}
    for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game', True):
        if str(data.asset_name) in ('BP_QuarterViewCamera', 'BP_Cat', 'BP_CatActions'):
            bp = data.get_asset()
            REPORT['blueprint_graphs'][bp.get_path_name()] = graph_snapshot(bp)
    REPORT['mapping_contexts'] = {}
    for path in ('/Game/Input/Contexts/IMC_Default', '/Game/Input/Contexts/IMC_CatInteraction'):
        context = unreal.load_asset(path)
        REPORT['mapping_contexts'][path] = mapping_snapshot(context)
    if MODE == 'apply':
        proof = json.loads(Path(globals()['CATRUN_BASKET_PROBE_REPORT']).read_text(encoding='utf-8'))
        assert globals().get('CATRUN_BASKET_CAMERA_SOURCE_REVIEWED') is True, 'Root must resolve applied camera source first'
        assert proof['completed'] and proof['mode'] == 'probe' and not proof['errors']
        assert proof['source_hashes'] == REPORT['source_hashes'], 'Native source changed after reviewed probe'
        REPORT['reviewed_probe'] = str(globals()['CATRUN_BASKET_PROBE_REPORT'])
        # Back up BOTH exact packages before the first mutation.
        REPORT['backups'] = []
        for name in MAPS:
            path = ROOT / ('Content/Maps/' + name + '.umap')
            assert digest(path) == proof['maps'][name]['map_sha256'], 'Saved map changed after reviewed probe'
            saved = OUT / 'Before' / path.relative_to(ROOT)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
            assert digest(path) == digest(saved)
            REPORT['backups'].append({'file': str(path.relative_to(ROOT)), 'sha256': digest(saved)})
    for name in MAPS:
        path = ROOT / ('Content/Maps/' + name + '.umap')
        assert not dirty(), 'Refuse to leave an unexpectedly dirty package'
        assert LEVEL.load_level('/Game/Maps/' + name)
        assert not dirty(), 'Map load dirtied an existing package; no auto-save'
        w = ED.get_editor_world()
        assert w.get_path_name().split('.')[0] == '/Game/Maps/' + name
        row, basket = probe(w, name)
        row['map_sha256'] = digest(path)
        if MODE == 'apply':
            assert row['AS_geometry']['safe'], 'AS exact landing/transit is physically blocked; do not repair by bypassing safety'
            assert row['selection_trace']['historical_A_front_candidate']['desired_allowed']
            assert row['basket'] == proof['maps'][name]['basket'] and row['camera'] == proof['maps'][name]['camera']
            basket.set_editor_property('OpenDirectionLocal', HISTORICAL_FRONT)
            after, _ = probe(w, name)
            assert after['selection_trace']['saved_front']['desired_allowed']
            assert after['selection_trace']['saved_front']['predicted_CanExit']
            expected = dict(row['basket'], front=v(HISTORICAL_FRONT))
            assert after['basket'] == expected, 'Unexpected target transform/reference mutation'
            other_before = [a for a in row['all_baskets'] if a['path'] != row['basket']['path']]
            other_after = [a for a in after['all_baskets'] if a['path'] != after['basket']['path']]
            assert other_before == other_after, 'Another basket changed'
            assert set(dirty()) <= {'/Game/Maps/' + name}, 'Unexpected package dirtied before map save'
            assert LEVEL.save_current_level()
            REPORT['maps'][name].update(before=row, map_sha256=digest(path), saved=True)
        elif MODE == 'audit':
            assert row['basket']['front'] == v(HISTORICAL_FRONT)
            assert row['AS_geometry']['safe'] and row['selection_trace']['saved_front']['desired_allowed']
            row['cold_saved_audit_passed'] = True
    REPORT['dirty_after'] = dirty()
    assert not REPORT['dirty_after'], 'Unexpected dirty package; never silently save unrelated work'
    REPORT['asset_application_complete'] = MODE == 'apply'
    REPORT['completed'] = True


OUT.mkdir(parents=True, exist_ok=True)
try:
    main()
except Exception:
    REPORT['errors'].append(traceback.format_exc())
finally:
    report_path = OUT / 'report.json'
    report_path.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CATRUN_BASKET_DIRECTION_REPORT', str(report_path), 'mode', MODE, 'completed', REPORT['completed'])
if REPORT['errors']:
    raise RuntimeError(REPORT['errors'][-1])
