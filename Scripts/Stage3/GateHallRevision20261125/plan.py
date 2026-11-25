"""Offline, preservation-oriented gate hall extension plan; never opens Unreal."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GateHallRevision20261125'
SNAPSHOT = ROOT / 'Saved/Stage3ApprovalAudit20261125/QA/before/snapshot.json'


def make_plan(snapshot_path=SNAPSHOT):
    snapshot = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    actors = snapshot['actors']
    by_label = {}
    for path, actor in actors.items():
        by_label.setdefault(actor['label'], []).append((path, actor))

    def one(label):
        rows = by_label.get(label, [])
        assert len(rows) == 1, (label, len(rows))
        return rows[0]

    copies, moves = [], {}

    def move(path, delta, reason):
        if path in moves:
            assert moves[path]['delta_world_cm'] == delta, path
            return
        moves[path] = {'path': path, 'label': actors[path]['label'],
                       'delta_world_cm': delta, 'reason': reason,
                       'before_transform': actors[path]['transform']}

    def copy(label, source, delta, reason):
        path, actor = one(source)
        copies.append({'label': label, 'source_path': path, 'source_label': source,
                       'delta_world_cm': delta, 'reason': reason,
                       'source_transform': actor['transform']})

    # Move only the terminal gate, landing, goal and endpoint masonry.
    for path, actor in actors.items():
        label = actor['label']
        if label.startswith(('S3_FinalGate_', 'S3_ExitLanding')) or label == 'S3_FinalExit':
            move(path, [0, -600, 0], 'terminal gate/goal +600 canonical Y')
    cutaway = json.loads((ROOT / 'Saved/Stage3GothicRevision20261125/occlusion_report.json').read_text())
    for wall in ('S3_Wall_0036', 'S3_Wall_0037', 'S3_Wall_0038', 'S3_Wall_0039'):
        for label in cutaway['groups'][wall]['members']:
            path, actor = one(label)
            move(path, [0, -600, 0], 'north boundary and its existing architectural trim')
    for label in ('S3_Gothic_GateHall_Sconce28', 'S3_Gothic_GateHall_SconceLight28',
                  'S3_Gothic_GateHall_Sconce29', 'S3_Gothic_GateHall_SconceLight29',
                  'S3_Gothic_GateHall_Candelabrum1', 'S3_Gothic_GateHall_CandelabrumLight1',
                  'S3_Gothic_GateHall_Candelabrum2', 'S3_Gothic_GateHall_CandelabrumLight2',
                  'S3_Gothic_GateThreshold', 'S3_Banner0', 'S3_Banner1'):
        if label in by_label:
            move(one(label)[0], [0, -600, 0], 'gate-end presentation follows terminal gate')
    # Object-reference route resolution avoids duplicate GateLeft_Route labels.
    for label in ('S3_Armor_GateLeft', 'S3_Armor_GateRight'):
        path, actor = one(label)
        move(path, [0, -600, 0], 'armor guard line follows terminal gate')
        for waypoint in actor['route']['PatrolPoints']:
            move(waypoint, [0, -600, 0], 'referenced armor waypoint follows guard')

    # New stone floor: exact existing module sizes, no new mesh or scaled UVs.
    for row in range(3):
        for column in range(8):
            x0 = -1000 + column * 200
            width = min(200, 500 - x0)
            source = 'S3_Floor_0111' if width == 200 else 'S3_Floor_0117'
            _, actor = one(source)
            c, e = actor['all_component_bounds']['center'], actor['all_component_bounds']['extent']
            assert abs(e[0] * 2 - width) < .05 and abs(e[1] * 2 - 200) < .05
            target_center = [x0 + width / 2, -(4100 + row * 200), c[2]]
            copy(f'S3_Floor_GateExt_{row}_{column}', source,
                 [target_center[i] - c[i] for i in range(3)], '600cm gate floor extension')
    # Side walls meet the moved north boundary with 30cm overlapping corners.
    for side, source in [('L', 'S3_Wall_0050'), ('R', 'S3_Wall_0084')]:
        for row in range(3):
            delta = [0, -(300 + row * 200), 0]  # source canonical3700..3900
            copy(f'S3_Wall_GateExt_{side}_{row}', source, delta, 'continuous side boundary')
            for member in cutaway['groups'][source]['members']:
                if member.startswith('S3_Gothic_Wall'):
                    copy(f'S3_Gothic_WallGateExt_{side}_{row}_{member}', member, delta,
                         'existing matching wall trim')
    for side, stem in [('L', 'S3_GrandPillar_-670_2'), ('R', 'S3_GrandPillar_270_2')]:
        for row, delta_y in [(3, -300), (4, -600)]:
            for part in ('Base', 'ShaftLower', 'ShaftUpper', 'Capital'):
                copy(f'S3_GrandPillar_GateExt{side}{row}_{part}', stem + '_' + part,
                     [0, delta_y, 0], '5 pillars per side; original rows retained')
    # Reuse local warm lights without changing exposure or global lighting.
    for row, canonical_y in [(3, 4025), (4, 4325)]:
        for number in (26, 27):
            for kind in ('Sconce', 'SconceLight'):
                copy(f'S3_Gothic_GateHall_{kind}Ext{number}_{row}',
                     f'S3_Gothic_GateHall_{kind}{number}', [0, -(canonical_y - 3620), 0],
                     'matching warm lighting for the additional two bays')
    for number in (5, 6):
        for kind in ('Banner', 'BannerHanger'):
            copy(f'S3_Gothic_GateHall_{kind}Ext{number}',
                 f'S3_Gothic_GateHall_{kind}{number}', [0, -700, 0],
                 'matching guard banner in extended hall')

    candles = []
    for side, xs in [('Left', [-870, -570]), ('Right', [70, 370])]:
        path, actor = one('S3_Candle_Gate' + side)
        points = actor['route']['PatrolPoints']
        assert len(points) == 4
        canonical = [[xs[0], 3300], [xs[1], 3300], [xs[1], 3600], [xs[0], 3600]]
        candles.append({'actor_path': path, 'actor_label': actor['label'], 'waypoint_paths': points,
                        'canonical_route_cm': canonical,
                        'reason': 'existing diamond waypoint lies inside a pillar base; rectangle clears it'})
    return {'status': 'PREPARED_NOT_EXECUTED', 'snapshot': str(snapshot_path),
            'coordinate_system': 'worldY=-canonicalY',
            'interpretation': 'Five pillars per side is an implementation interpretation, not an exact user dimension.',
            'gate_hall_outer_before_cm': [-1000, 2900, 500, 4000],
            'gate_hall_outer_after_cm': [-1000, 2900, 500, 4600],
            'pillar_rows_before_cm': [3150, 3450, 3725],
            'pillar_rows_after_cm': [3150, 3450, 3725, 4025, 4325],
            'pillar_x_cm': [-720, 220], 'pillar_top_before_cm': 900,
            'terminal_gate_canonical_y': 4550, 'final_exit_canonical_y': 4690,
            'landing_canonical_y_range': [4600, 4800],
            'moves': list(moves.values()), 'copies': copies, 'candles': candles,
            'rug': {'label': 'S3_GothicRug_GrandGate', 'canonical_rect_cm': [-400, 2950, -100, 4450],
                    'new_center_world_cm': [-250, -3700, .2], 'local_y_scale_multiplier': 1500 / 900,
                    'limitation': 'Actor stretch preserves source mesh/UV/material but elongates ornament proportions; actual-camera art check required.'},
            'preserved': ['All altar/E3/B1 pending geometry', 'D2 and its three locks',
                          'Main room sizes outside gate hall', 'Shared meshes/material assets',
                          'Enemy counts and native object references', 'Shared camera Blueprint'],
            'post_apply_required': ['Root chooses/tests pillar-top height using actual orthographic camera;900cm already exposes caps.',
                                    'Refresh cutaway CPD groups so new pillars share existing occlusion.',
                                    'Rebuild and export SoundGrid; nav/goal/native interaction regression.',
                                    'Regenerate minimap image/projection from measured saved actors, not stale layout.py.',
                                    'Check carpet proportions, light pools, corner seams and pillar tops in actual cat camera.']}


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    result = make_plan()
    (OUT / 'plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Gate hall plan:', len(result['moves']), 'moves;', len(result['copies']), 'copies; no Unreal calls')
