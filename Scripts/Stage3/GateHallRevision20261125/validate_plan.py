"""Offline geometry/identity checks; no engine calls and no production writes."""
import json
import math
from pathlib import Path
from plan import make_plan, ROOT, OUT


def main():
    plan = make_plan()
    snap = json.loads(Path(plan['snapshot']).read_text(encoding='utf-8'))
    actors = snap['actors']
    checks = []

    def check(name, result, detail):
        checks.append({'name': name, 'passed': bool(result), 'detail': detail})

    labels = [op['label'] for op in plan['copies']]
    check('new_actor_labels_unique', len(labels) == len(set(labels)), len(labels))
    check('all_original_object_paths_resolve', all(op['path'] in actors for op in plan['moves'])
          and all(op['source_path'] in actors for op in plan['copies']), 'Object paths avoid duplicate route labels')
    excluded = ('S3_D2', 'S3_Lock', 'S3_Release', 'S3_Statue', 'S3_Plate', 'S3_Control', 'S3_Armor_Control')
    check('altar_E3_D2_not_moved', not any(op['label'].startswith(excluded) for op in plan['moves']),
          [op['label'] for op in plan['moves'] if op['label'].startswith(excluded)])
    cells = set()
    for op in plan['copies']:
        if not op['label'].startswith('S3_Floor_GateExt_'):
            continue
        b = actors[op['source_path']]['all_component_bounds']
        c = [x + d for x, d in zip(b['center'], op['delta_world_cm'])]
        e = b['extent']
        bounds = [round(c[0] - e[0]), round(-c[1] - e[1]),
                  round(c[0] + e[0]), round(-c[1] + e[1])]
        x0, y0, x1, y1 = bounds
        new = {(x, y) for x in range(x0, x1, 50) for y in range(y0, y1, 50)}
        assert not (cells & new), op['label']
        cells.update(new)
        mesh = next(iter(actors[op['source_path']]['components'].values()))['mesh']
        assert 'GatePlain' in mesh, mesh
    expected = {(x, y) for x in range(-1000, 500, 50) for y in range(4000, 4600, 50)}
    check('extension_floor_exact_15m_by_6m', cells == expected,
          {'cells_50cm': len(cells), 'area_m2': len(cells) * .25})
    check('five_rows_per_side_preserve_original_three',
          plan['pillar_rows_after_cm'] == [3150, 3450, 3725, 4025, 4325],
          {'row_spacing_cm': [300, 275, 300, 300], 'new_pillar_actor_parts': sum('GrandPillar' in s for s in labels)})
    boundaries = {}
    for op in plan['copies']:
        if not op['label'].startswith('S3_Wall_GateExt_'):
            continue
        b = actors[op['source_path']]['all_component_bounds']
        c = [v + d for v, d in zip(b['center'], op['delta_world_cm'])]
        e = b['extent']; side = op['label'].split('_')[-2]
        boundaries.setdefault(side, []).append((round(-c[1] - e[1]), round(-c[1] + e[1])))
    check('side_walls_continuous_to_new_north_corners',
          all(sorted(v) == [(4000, 4200), (4200, 4400), (4400, 4600)] for v in boundaries.values())
          and len(boundaries) == 2,
          {'side_intervals': boundaries, 'north_wall_y': [4570, 4600], 'corner_overlap_cm': 30})

    def segment_rect_distance(p, q, rect):
        x0, y0, x1, y1 = rect
        if p[1] == q[1]:
            dx = max(x0 - max(p[0], q[0]), min(p[0], q[0]) - x1, 0)
            dy = max(y0 - p[1], p[1] - y1, 0)
        else:
            dx = max(x0 - p[0], p[0] - x1, 0)
            dy = max(y0 - max(p[1], q[1]), min(p[1], q[1]) - y1, 0)
        return math.hypot(dx, dy)

    rectangles = [[x - 75, y - 75, x + 75, y + 75]
                  for x in plan['pillar_x_cm'] for y in plan['pillar_rows_after_cm']]
    margins = []
    for candle in plan['candles']:
        points = candle['canonical_route_cm']
        for i, p in enumerate(points):
            margins.append(min(segment_rect_distance(p, points[(i + 1) % 4], r)
                               for r in rectangles) - 22)
    check('candle_rectangle_clears_all_ten_pillar_bases', min(margins) >= 28 - .01,
          {'minimum_surface_clearance_cm': min(margins), 'assumed_capsule_radius_cm': 22,
           'limit': 'Static pillar bounds only, not native AI or all-scene sweep'})
    check('gate_exit_landing_move_together', all(op['delta_world_cm'] == [0, -600, 0]
          for op in plan['moves'] if op['label'].startswith(('S3_FinalGate_', 'S3_ExitLanding', 'S3_FinalExit'))),
          {'gate_canonical_y': 4550, 'exit_canonical_y': 4690, 'landing': [4600, 4800]})
    report = {'success': all(c['passed'] for c in checks), 'checks': checks,
              'engine_executed': False, 'production_written': False,
              'pillar_caps_verified': False, 'rug_art_quality_verified': False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'plan_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    assert main()['success']
