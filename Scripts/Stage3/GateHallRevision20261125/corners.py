"""Read-only corner audit plus an explicit root-only unsaved patch function.

Retired/hidden/collision-off walls and intentional apertures are not candidates.
Only canonical outer-polyline vertices with perpendicular active wall bodies
are inspected; no wholesale dressing regeneration.
"""
import collections
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GateHallRevision20261125'


def bounds(actor):
    c, e = actor['all_component_bounds']['center'], actor['all_component_bounds']['extent']
    return [c[0] - e[0], -c[1] - e[1], c[0] + e[0], -c[1] + e[1], c[2] - e[2], c[2] + e[2]]


def active_body(actor):
    return any(c.get('presentation', {}).get('visible', False)
               and not c.get('presentation', {}).get('hidden_in_game', False)
               and 'NO_COLLISION' not in c.get('collision', {}).get('enabled', 'NO_COLLISION')
               for c in actor['components'].values())


def audit():
    snapshot = json.loads((ROOT / 'Saved/Stage3ApprovalAudit20261125/QA/before/snapshot.json').read_text())
    by_label = {a['label']: a for a in snapshot['actors'].values()}
    walls = [(a['label'], bounds(a)) for a in snapshot['actors'].values()
             if a['label'].startswith('S3_Wall_') and active_body(a)]
    spec = importlib.util.spec_from_file_location('gate_corner_layout', ROOT / 'Scripts/Stage3/layout.py')
    layout = importlib.util.module_from_spec(spec); spec.loader.exec_module(layout)
    vertices = collections.defaultdict(list)
    for segment in layout.boundary_segments():
        orient, fixed, start, end, _ = segment
        for value in (start, end):
            vertices[(value, fixed) if orient == 'h' else (fixed, value)].append(segment)
    groups = json.loads((ROOT / 'Saved/Stage3GothicRevision20261125/occlusion_report.json').read_text())['groups']
    joins, trim_only, already_bridged = [], [], []
    added_missing_trim = set()
    for point, segments in vertices.items():
        if len(segments) != 2 or segments[0][0] == segments[1][0]:
            continue
        selected = {}
        for orient, fixed, _, _, _ in segments:
            for label, r in walls:
                x0, y0, x1, y1, _, _ = r
                if not (x0 - .05 <= point[0] <= x1 + .05 and y0 - .05 <= point[1] <= y1 + .05):
                    continue
                match = ((orient == 'h' and abs(y1 - y0 - 30) < .05 and min(abs(y0 - fixed), abs(y1 - fixed)) < .05)
                         or (orient == 'v' and abs(x1 - x0 - 30) < .05 and min(abs(x0 - fixed), abs(x1 - fixed)) < .05))
                if match:
                    selected[orient] = (label, r); break
        if len(selected) != 2:
            continue
        h, v = selected['h'], selected['v']
        dx = min(h[1][2], v[1][2]) - max(h[1][0], v[1][0])
        dy = min(h[1][3], v[1][3]) - max(h[1][1], v[1][1])
        if dx > .05 and dy > .05:
            continue  # Existing solid corner overlap; no repair necessary.
        row = {'corner_canonical_cm': list(point), 'walls': [h[0], v[0]],
               'measured_intersection_xy_cm': [max(0, dx), max(0, dy)],
               'wall_bounds': {h[0]: h[1], v[0]: v[1]}, 'trim_patches': []}
        point_join = abs(dx) < .05 and abs(dy) < .05
        if point_join:
            row['body_patch_canonical_bounds'] = [v[1][0], h[1][1], v[1][2], h[1][3], 0, 300]
            patch = row['body_patch_canonical_bounds']
            third = []
            for label, other in walls:
                if label in row['walls']:
                    continue
                overlap_x = min(patch[2], other[2]) - max(patch[0], other[0])
                overlap_y = min(patch[3], other[3]) - max(patch[1], other[1])
                if overlap_x > .05 and overlap_y > .05:
                    third.append({'label': label, 'covered_cm2': overlap_x * overlap_y})
            if third:
                row.pop('body_patch_canonical_bounds')
                row['bridging_walls'] = third
                row['diagnosis'] = 'Existing third wall already makes a15cm face connection. No automatic body or trim patch: stepped T-junction requires visual inspection, not a presumed missing corner.'
                already_bridged.append(row)
                continue
            row['diagnosis'] = 'Body AABBs touch at one point, with no shared end face. Fill the30x30 inside return; this is not a measured open30cm walk-through gap.'
        else:
            row['diagnosis'] = 'Body walls already share a30cm edge; only the5cm thick molding needs a short return.'
        for suffix in ('Plinth', 'String', 'Cornice'):
            def trim(wall):
                names = [name for name in groups[wall]['members'] if name.endswith('_' + suffix)]
                return names[0] if len(names) == 1 else None
            hn, vn = trim(h[0]), trim(v[0])
            if not vn:
                continue
            vr = bounds(by_label[vn])
            if hn:
                hr = bounds(by_label[hn])
            else:
                # The50cm wall0021 was skipped by the original dressing pass.
                # Add its missing short strip once, plus the two corner returns.
                hn = 'S3_Gothic_Wall4_' + suffix
                source_r = bounds(by_label[hn])
                side = next(seg[4] for seg in segments if seg[0] == 'h')
                ys = [h[1][3], h[1][3] + 5] if side > 0 else [h[1][1] - 5, h[1][1]]
                hr = [h[1][0], ys[0], h[1][2], ys[1], source_r[4], source_r[5]]
                key = (h[0], suffix)
                if key not in added_missing_trim:
                    row['trim_patches'].append({'source_label': hn, 'canonical_bounds': hr,
                                               'reason': 'missing original short-wall molding'})
                    added_missing_trim.add(key)
            x = point[0]
            # Extend the horizontal molding to the vertical molding face.
            patch = [min(x, vr[0]), hr[1], max(x, vr[2]), hr[3], hr[4], hr[5]]
            row['trim_patches'].append({'source_label': hn, 'canonical_bounds': patch})
            if point_join:
                y = point[1]
                patch = [vr[0], min(y, hr[1]), vr[2], max(y, hr[3]), vr[4], vr[5]]
                row['trim_patches'].append({'source_label': vn, 'canonical_bounds': patch})
        (joins if point_join else trim_only).append(row)
    report = {'status': 'READ_ONLY_AUDIT_NOT_APPLIED', 'coordinate_system': 'canonicalX,canonicalY=-worldY',
              'active_body_filter': 'visible and not hidden_in_game and collision enabled; old0001/0002 retired walls excluded',
              'body_joins': joins, 'trim_only': trim_only,
              'already_bridged_no_automatic_patch': already_bridged,
              'scope_note': 'Only outer polygon joins. Intentional doors, cat holes and approved B1 internal brackets are excluded.',
              'E23_note': 'No E23 actors are changed. Entrance corner actors0004/0005/0078/0079 are individually confirmed live; obsolete bottom0001/0002 are not used.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'corner_join_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def apply_corners(report_path=None):
    import unreal as u
    report = json.loads(Path(report_path or OUT / 'corner_join_audit.json').read_text())
    es = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    act = u.get_editor_subsystem(u.EditorActorSubsystem)
    world = es.get_editor_world()
    assert world.get_path_name() == '/Game/Maps/Stage3.Stage3' and not es.get_game_world()
    actors = {a.get_actor_label(): a for a in act.get_all_level_actors()}
    owner = 'Stage3CornerReturns20261125'
    assert not any(owner in map(str, a.tags) for a in actors.values()), 'Already patched'
    rows = report['body_joins'] + report['trim_only']
    for row in rows:
        for label, expected in row['wall_bounds'].items():
            actor = actors[label]; comp = actor.get_component_by_class(u.StaticMeshComponent)
            assert comp.get_editor_property('visible') and not comp.get_editor_property('hidden_in_game')
            assert comp.get_collision_enabled() != u.CollisionEnabled.NO_COLLISION
            c, e = actor.get_actor_bounds(False, False)
            actual = [c.x - e.x, -c.y - e.y, c.x + e.x, -c.y + e.y, c.z - e.z, c.z + e.z]
            assert max(abs(x - y) for x, y in zip(actual, expected)) < .1, label
    created = []

    def copy_fit(source, label, r, collision):
        source_c, source_e = source.get_actor_bounds(False, False)
        target_world_center = u.Vector((r[0] + r[2]) / 2, -(r[1] + r[3]) / 2, (r[4] + r[5]) / 2)
        desired = [r[2] - r[0], r[3] - r[1], r[5] - r[4]]
        ratio = [desired[i] / value for i, value in enumerate((2 * source_e.x, 2 * source_e.y, 2 * source_e.z))]
        q = source.get_actor_rotation()
        # All source return moldings are cardinal; local X/Y swap at90deg.
        if abs(abs(q.yaw) % 180 - 90) < .01:
            ratio[0], ratio[1] = ratio[1], ratio[0]
        new = act.duplicate_actor(source, world, u.Vector())
        assert new
        new.set_actor_label(label); new.tags = list(new.tags) + [u.Name(owner)]
        new.set_folder_path('Stage3/GateHallRevision20261125/CornerReturns')
        scale = source.get_actor_scale3d()
        new.set_actor_scale3d(u.Vector(scale.x * ratio[0], scale.y * ratio[1], scale.z * ratio[2]))
        c, e = new.get_actor_bounds(False, False)
        new.set_actor_location(new.get_actor_location() + target_world_center - c, False, True)
        comp = new.get_component_by_class(u.StaticMeshComponent)
        if not collision:
            comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        c, e = new.get_actor_bounds(False, False)
        assert max(abs(v - d) for v, d in zip((2 * e.x, 2 * e.y, 2 * e.z), desired)) < .1
        created.append({'label': label, 'source': source.get_actor_label(), 'canonical_bounds': r,
                        'collision': collision, 'path': new.get_path_name()})

    for i, row in enumerate(rows):
        if 'body_patch_canonical_bounds' in row:
            copy_fit(actors['S3_Wall_0018'], f'S3_Wall_CornerJoin_{i:02}', row['body_patch_canonical_bounds'], True)
        for j, patch in enumerate(row['trim_patches']):
            copy_fit(actors[patch['source_label']], f'S3_Gothic_WallCornerJoin_{i:02}_{j}', patch['canonical_bounds'], False)
    result = {'success': True, 'level_saved': False, 'created': created,
              'pending': ['Run occlusion.apply after all geometry changes', 'Rebuild SoundGrid',
                          'Root capsule/door/basket regression before final save']}
    (OUT / 'corner_applied_unsaved.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    result = audit()
    print('Body joins:', len(result['body_joins']), 'trim-only:', len(result['trim_only']))
