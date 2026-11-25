"""Read-only current Stage3 basket/floor/pivot audit. Root invokes main().

No level loads, actor spawning, property changes, map or asset saves. Bounds
and support traces diagnose placement; they do not certify rendered visibility.
"""
import hashlib
import json
import os
from pathlib import Path


def main():
    import unreal as u
    root = Path(u.Paths.project_dir()).resolve()
    suffix = os.environ.get('CATRUN_STAGE3_BASKET_HEIGHT_PASS', '01')
    assert suffix.replace('_', '').isalnum()
    out = root / 'Saved/Stage3BasketHeightRevision20261125' / ('Probe' + suffix + '.json')
    assert not out.exists(), 'Use a fresh pass; preserve prior evidence'
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3'
    assert not ed.get_game_world(), 'Probe saved editor world, outside PIE'
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    by_label = {a.get_actor_label(): a for a in actors}
    mapfile = root / 'Content/Maps/Stage3.umap'
    before_hash = hashlib.sha256(mapfile.read_bytes()).hexdigest()
    before_transforms = {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
    def vec(v):
        return [float(v.x), float(v.y), float(v.z)]
    def bounds(actor):
        center, extent = actor.get_actor_bounds(False, False)
        return {'min': vec(center-extent), 'max': vec(center+extent)}
    def record(actor):
        row = {'label': actor.get_actor_label(), 'path': actor.get_path_name(),
               'transform': actor.get_actor_transform().export_text(), 'world': vec(actor.get_actor_location()),
               'bounds': bounds(actor), 'components': []}
        for comp in actor.get_components_by_class(u.MeshComponent):
            mesh = comp.static_mesh if isinstance(comp, u.StaticMeshComponent) else comp.get_skinned_asset() if isinstance(comp, u.SkinnedMeshComponent) else None
            item = {'name': comp.get_name(), 'mesh': mesh.get_path_name() if mesh else None,
                    'transform': comp.get_world_transform().export_text(),
                    'relative_transform': comp.get_relative_transform().export_text(),
                    'visible': bool(comp.get_editor_property('visible')),
                    'hidden_in_game': bool(comp.get_editor_property('hidden_in_game')),
                    'materials': [comp.get_material(i).get_path_name() if comp.get_material(i) else None for i in range(comp.get_num_materials())]}
            if mesh and isinstance(comp, u.StaticMeshComponent):
                b = mesh.get_bounds()
                item['asset_local_bounds'] = {'origin': vec(b.origin), 'extent': vec(b.box_extent),
                                              'min': vec(b.origin-b.box_extent), 'max': vec(b.origin+b.box_extent)}
            if isinstance(comp, u.SkeletalMeshComponent):
                item['animation_data'] = str(comp.get_editor_property('animation_data'))
                item['sockets_world'] = {name: vec(comp.get_socket_location(name)) for name in ('Edge_F', 'Edge_R')}
            row['components'].append(item)
        return row
    all_baskets = [a for a in actors if isinstance(a, u.CatrunHideBasket)]
    report = {'success': False, 'scope': __doc__, 'map_sha256': before_hash,
              'basket_actor_count': len(all_baskets), 'baskets': [], 'other_basket_mesh_actors': [], 'packages_saved': False}
    selected = set()
    for basket in all_baskets:
        body = basket.get_editor_property('ExternalBody')
        cloth = basket.get_editor_property('ExternalCloth')
        cloth_actor = cloth.get_owner() if cloth else None
        trio = list(dict.fromkeys(a for a in (basket, body, cloth_actor) if a))
        selected.update(trio)
        row = {'basket': record(basket), 'external_body': record(body) if body else None,
               'external_cloth': record(cloth_actor) if cloth_actor else None,
               'enter_clip_count': len(basket.get_editor_property('ClothEnterDirections')),
               'exit_clip_count': len(basket.get_editor_property('ClothExitDirections')),
               'floor_traces': [], 'overlapping_floor_bounds': [], 'nearby_static_mesh_bounds': []}
        hidden = [c for c in basket.get_components_by_class(u.SceneComponent) if c.get_name() == 'HiddenPoint']
        row['hidden_point_world'] = vec(hidden[0].get_world_location()) if hidden else None
        p = body.get_actor_location() if body else basket.get_actor_location()
        for dx, dy in ((0,0),(-30,-30),(-30,0),(-30,30),(0,-30),(0,30),(30,-30),(30,0),(30,30)):
            hit = u.SystemLibrary.line_trace_single_by_profile(world, u.Vector(p.x+dx,p.y+dy,p.z+150),
                       u.Vector(p.x+dx,p.y+dy,p.z-150), 'Pawn', False, trio, u.DrawDebugTrace.NONE, False)
            datum = {'offset_xy': [dx,dy], 'hit': None}
            if hit:
                h = hit.to_dict()
                datum['hit'] = {'actor': h['hit_actor'].get_actor_label() if h['hit_actor'] else None,
                                'impact': vec(h['impact_point']), 'normal': vec(h['impact_normal']),
                                'blocking': bool(h['blocking_hit']), 'initial_overlap': bool(h['initial_overlap'])}
            row['floor_traces'].append(datum)
        for a in actors:
            if a not in trio and isinstance(a, u.StaticMeshActor):
                other = bounds(a)
                if other['min'][0] <= p.x+100 and other['max'][0] >= p.x-100 and other['min'][1] <= p.y+100 and other['max'][1] >= p.y-100 and other['min'][2] < p.z+70 and other['max'][2] > p.z:
                    overlaps = {}
                    for role, target in (('body', body), ('cloth', cloth_actor)):
                        if not target:
                            continue
                        tb = bounds(target)
                        depth = [min(other['max'][i], tb['max'][i])-max(other['min'][i], tb['min'][i]) for i in range(3)]
                        if min(depth) > .01:
                            overlaps[role] = depth
                    row['nearby_static_mesh_bounds'].append({'label': a.get_actor_label(), 'bounds': other,
                                                             'positive_aabb_overlap_cm': overlaps,
                                                             'note': 'AABB overlap is a candidate, not triangle/collision intersection proof.'})
            if 'floor' not in a.get_actor_label().lower():
                continue
            b = bounds(a)
            if b['min'][0] <= p.x <= b['max'][0] and b['min'][1] <= p.y <= b['max'][1]:
                row['overlapping_floor_bounds'].append({'label': a.get_actor_label(), 'bounds': b})
        report['baskets'].append(row)
    for a in actors:
        if a in selected:
            continue
        if 'basket' in a.get_actor_label().lower() or any('hidebasket' in str(c.get_editor_property('static_mesh')).lower() for c in a.get_components_by_class(u.StaticMeshComponent)):
            report['other_basket_mesh_actors'].append(record(a))
    assert before_hash == hashlib.sha256(mapfile.read_bytes()).hexdigest()
    assert before_transforms == {a.get_path_name(): a.get_actor_transform().export_text() for a in actors}
    report['success'] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    return report
