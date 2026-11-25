"""Root-only incremental Annex basket clearance correction; inert import.

apply() moves the existing linked actor trio 16 cm east, never vertically.
Requires the diagnosed Wall60 decorative overlap to exist first. Performs no
package/map saves; root saves its integrated transaction and runs native QA.
"""
import hashlib
import json
import os
import traceback
from pathlib import Path

LABEL = 'S3_Placement_Basket_ControlAnnex'
OLD = (-320., -2045., 0.)
TARGET = (-304., -2045., 0.)
DECOR = ('S3_Gothic_Wall60_Base', 'S3_Gothic_Wall60_Bundle0',
         'S3_Gothic_Wall60_Bundle1', 'S3_Gothic_Wall60_Bundle2')


def apply():
    import unreal as u
    root = Path(u.Paths.project_dir()).resolve()
    suffix = os.environ.get('CATRUN_STAGE3_BASKET_HEIGHT_FIX_PASS', '01')
    assert suffix.replace('_', '').isalnum()
    out = root / 'Saved/Stage3BasketHeightRevision20261125' / ('Prepare' + suffix + '.json')
    assert not out.exists(), 'Preserve previous correction evidence; select a fresh pass'
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not ed.get_game_world(), 'Root writer must run outside PIE'
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    by_label = {a.get_actor_label(): a for a in actors}
    basket, body, cloth_actor = [by_label[LABEL+s] for s in ('', '_Body', '_Cloth')]
    trio = (basket, body, cloth_actor)
    decorations = [by_label[label] for label in DECOR]
    cloth = cloth_actor.get_component_by_class(u.SkeletalMeshComponent)
    body_component = body.get_component_by_class(u.StaticMeshComponent)
    assert basket.get_editor_property('ExternalBody') == body
    assert basket.get_editor_property('ExternalCloth') == cloth
    assert all((a.get_actor_location()-u.Vector(*OLD)).length() < .01 for a in trio), 'Unexpected existing position; do not blindly move'
    originals = {a: a.get_actor_transform() for a in trio}
    others = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors if a not in trio}
    mapfile = root / 'Content/Maps/Stage3.umap'
    map_hash = hashlib.sha256(mapfile.read_bytes()).hexdigest()
    r = {'success': False, 'packages_saved': False, 'scope': __doc__, 'map_sha256_before': map_hash,
         'old_world_cm': OLD, 'target_world_cm': TARGET, 'checks': [],
         'limitations': ['This corrects reproduced Annex decorative overlap, not a measured below-floor pivot.',
                         'If the user meant a different basket, that case still needs reproduction.',
                         'AABB separation and static clearance are not native F/cloth/play-camera proof; run the sixteen native basket cases after saving.']}

    def v(p):
        return [float(p.x), float(p.y), float(p.z)]

    def check(name, ok, detail=None):
        r['checks'].append({'name': name, 'passed': bool(ok), 'detail': detail})
        assert ok, (name, detail)

    def box(actor):
        c, e = actor.get_actor_bounds(False, False)
        return {'min': v(c-e), 'max': v(c+e)}

    def state():
        return {a.get_actor_label(): {'transform': a.get_actor_transform().export_text(), 'bounds': box(a)} for a in trio}

    def identity():
        action = by_label['S3_Player'].get_component_by_class(u.CatrunBasketInteractionComponent)
        animation = cloth.get_editor_property('animation_data')
        clip = animation.get_editor_property('anim_to_play')
        return {'links': [basket.get_editor_property('ExternalBody').get_path_name(), basket.get_editor_property('ExternalCloth').get_path_name()],
                'body_mesh': body_component.static_mesh.get_path_name(),
                'cloth_mesh': cloth.get_skinned_asset().get_path_name(),
                'materials': [[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())] for c in (body_component, cloth)],
                'enter': [a.get_path_name() if a else None for a in basket.get_editor_property('ClothEnterDirections')],
                'exit': [a.get_path_name() if a else None for a in basket.get_editor_property('ClothExitDirections')],
                'idle': str(basket.get_editor_property('ClothIdleAnimation')),
                'hidden': str(basket.get_editor_property('ClothHiddenAnimation')),
                'cloth_animation_data': {'asset': clip.get_path_name() if clip else None,
                                         **{name: animation.get_editor_property(name) for name in ('saved_playing', 'saved_looping', 'saved_position', 'saved_play_rate')}},
                'interaction_range': float(action.get_editor_property('InteractionRange')),
                'entry_distance': float(action.get_editor_property('EntryDistance')),
                'exit_distance': float(action.get_editor_property('ExitDistance'))}

    def overlaps():
        rows = []
        for target in (body, cloth_actor):
            a = box(target)
            for decor in decorations:
                b = box(decor)
                depth = [min(a['max'][i], b['max'][i])-max(a['min'][i], b['min'][i]) for i in range(3)]
                rows.append({'basket_actor': target.get_actor_label(), 'decor': decor.get_actor_label(),
                             'depth_cm': depth, 'positive_volume_aabb_overlap': min(depth) > .01})
        return rows

    def hit_record(hit):
        if not hit:
            return None
        d = hit.to_dict()
        return {'actor': d['hit_actor'].get_actor_label() if d['hit_actor'] else None,
                'impact': v(d['impact_point']), 'normal': v(d['impact_normal']),
                'blocking': bool(d['blocking_hit']), 'initial_overlap': bool(d['initial_overlap'])}

    def floors(radius=30.):
        p = body.get_actor_location()
        rows = []
        for dx, dy in ((0,0),(-radius,-radius),(-radius,0),(-radius,radius),(0,-radius),(0,radius),(radius,-radius),(radius,0),(radius,radius)):
            hit = u.SystemLibrary.line_trace_single_by_profile(world, u.Vector(p.x+dx,p.y+dy,150),
                     u.Vector(p.x+dx,p.y+dy,-150), 'Pawn', False, list(trio), u.DrawDebugTrace.NONE, False)
            data = hit_record(hit)
            rows.append({'offset': [dx,dy], 'hit': data,
                         'valid': bool(data and data['blocking'] and not data['initial_overlap'] and data['actor'].startswith('S3_Floor_') and abs(data['impact'][2]) < .05 and data['normal'][2] > .999)})
        return rows

    def corridor():
        # Preserve the established x=-200 upper-corridor/Annex limb. Ignore
        # dynamic NPCs only, so authored static furniture and walls still block.
        ignore = [a for a in actors if isinstance(a, (u.Pawn, u.CatrunArmor, u.CatrunCandle))]
        rows = []
        for name in ('S3_Player', 'S3_Armor_ControlPatrol'):
            pawn = by_label[name]
            cap = pawn.get_component_by_class(u.CapsuleComponent)
            radius, half = cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()
            profile = str(cap.get_collision_profile_name())
            if profile in ('Custom', '', 'None', 'NoCollision'):
                template = u.get_default_object(u.Character).get_editor_property('CapsuleComponent')
                channels = {c.get_collision_object_type() for a in actors for c in a.get_components_by_class(u.PrimitiveComponent)}
                equivalent = cap.get_collision_object_type() == template.get_collision_object_type() and all(cap.get_collision_response_to_channel(ch) == template.get_collision_response_to_channel(ch) for ch in channels)
                check(name+' query profile response equivalence', equivalent)
                profile = str(template.get_collision_profile_name())
            check(name+' registered query profile', profile not in ('Custom', '', 'None', 'NoCollision'), profile)
            start, end = u.Vector(-200,-2220,half+2.2), u.Vector(-200,-2045,half+2.2)
            hits = [hit_record(u.SystemLibrary.capsule_trace_single_by_profile(world, a,b,radius,half,profile,False,ignore,u.DrawDebugTrace.NONE,False)) for a,b in ((start,end),(end,start))]
            visual_gap = -200-box(body)['max'][0]-radius
            rows.append({'pawn': name, 'radius': radius, 'half_height': half, 'profile': profile,
                         'body_to_capsule_gap_cm': visual_gap, 'start': v(start), 'end': v(end),
                         'hits': hits, 'clear': not any(hits) and visual_gap > 0.})
        return rows

    changed = False
    try:
        original_identity = identity()
        check('Eight enter and eight exit clips preserved', len(original_identity['enter']) == len(original_identity['exit']) == 8)
        r['before'] = state()
        r['decor_bounds'] = {a.get_actor_label(): box(a) for a in decorations}
        r['before_overlaps'] = overlaps()
        check('Reproduced Annex body versus Wall60 Base overlap', any(row['basket_actor'] == body.get_actor_label() and row['decor'] == 'S3_Gothic_Wall60_Base' and row['positive_volume_aabb_overlap'] for row in r['before_overlaps']), r['before_overlaps'])
        # These shared basket materials were never given the Stage3 cutaway
        # bounds contract. Refuse if that has changed rather than corrupt CPD.
        for comp in (body_component, cloth):
            cpd = list(comp.get_editor_property('custom_primitive_data').get_editor_property('data'))
            sources = [u.EditorAssetLibrary.get_metadata_tag(comp.get_material(i), 'Stage3ReadabilitySource') for i in range(comp.get_num_materials()) if comp.get_material(i)]
            check('No unhandled static cutaway bounds', not any(sources) and not any(abs(n) > .001 for n in cpd[16:24]), {'component': comp.get_path_name(), 'cpd': cpd, 'sources': sources})
        r['before_floor'] = floors()
        check('Original basket footprint supported on Z0 floor', all(row['valid'] for row in r['before_floor']), r['before_floor'])
        r['before_corridor'] = corridor()
        check('Original x=-200 static capsule corridor clear', all(row['clear'] for row in r['before_corridor']), r['before_corridor'])
        changed = True
        for actor in trio:
            actor.set_actor_location(actor.get_actor_location()+u.Vector(16,0,0), False, True)
        r['after'] = state()
        r['after_overlaps'] = overlaps()
        check('Body and cloth separated from all four wall decorations', not any(row['positive_volume_aabb_overlap'] for row in r['after_overlaps']), r['after_overlaps'])
        check('Trio moved together horizontally only', all((a.get_actor_location()-u.Vector(*TARGET)).length() < .01 for a in trio))
        r['after_floor'] = floors(40.)
        check('New basket footprint remains supported on Z0 floor', all(row['valid'] for row in r['after_floor']), r['after_floor'])
        r['after_corridor'] = corridor()
        check('Existing x=-200 cat and armor capsule corridor preserved', all(row['clear'] for row in r['after_corridor']), r['after_corridor'])
        check('All other actor transforms preserved', others == {a.get_path_name(): a.get_actor_transform().export_text() for a in actors if a not in trio})
        check('Meshes materials animation links and interaction settings preserved', original_identity == identity())
        check('No package save', map_hash == hashlib.sha256(mapfile.read_bytes()).hexdigest())
        r['success'] = True
    except Exception:
        r['error'] = traceback.format_exc()
        if changed:
            for actor, transform in originals.items():
                actor.set_actor_transform(transform, False, True)
            r['rolled_back'] = all(a.get_actor_transform().export_text() == t.export_text() for a,t in originals.items())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding='utf8')
    assert r['success'], r.get('error', 'Basket correction failed')
    return r
