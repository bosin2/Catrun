"""Check observed gameplay camera frames against geometry measured from the map.

These checks target the cropped plate, foreground statue and unreadable reaction
seen in the baseline recording. They supplement, rather than replace, image review.
"""
import argparse
import itertools
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
parser.add_argument('geometry', type=Path)
args = parser.parse_args()
report = json.loads((args.run / 'report.json').read_text(encoding='utf-8'))
geometry = json.loads(args.geometry.read_text(encoding='utf-8'))['geometry']
rows = [r for r in report['viewport_frames'] if r.get('sequence') == 'arrival']


def closest(frame):
    return min(rows, key=lambda row: abs(row['frame'] - frame))


def project(row, point):
    pitch, yaw, roll = map(math.radians, row['view_rot'])
    assert abs(roll) < .001
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    forward, right, up = (cp * cy, cp * sy, sp), (-sy, cy, 0), (-sp * cy, -sp * sy, cp)
    delta = [b - a for a, b in zip(row['view_pos'], point)]
    dot = lambda v: sum(a * b for a, b in zip(v, delta))
    if row['projection'] == 'orthographic':
        half_width = row['projected_ortho_width'] / 2
    else:
        half_width = dot(forward) * math.tan(math.radians(row['projected_horizontal_fov']) / 2)
    return (.5 + .5 * dot(right) / half_width, .5 - .5 * dot(up) * (16 / 9) / half_width)


def box(row, label):
    item = geometry[label]
    points = [project(row, [a + s * b for a, b, s in zip(item['origin'], item['extent'], signs)])
              for signs in itertools.product((-1, 1), repeat=3)]
    return [min(v[0] for v in points), max(v[0] for v in points), min(v[1] for v in points), max(v[1] for v in points)]


plate = box(closest(205), 'S2_Prop_Plate_C_Frame')
reaction = closest(246)
statue = box(reaction, 'S2_Prop_Statue_C')
head = reaction['visual']['bones']['head']
front_angle = abs(math.degrees(math.atan2(reaction['view_pos'][0] - head[0], head[1] - reaction['view_pos'][1])))
held = [r for r in rows if 246 <= r['frame'] <= 266]
hold_distance = max(math.dist(r['view_pos'], reaction['view_pos']) for r in held)
hold_zoom = max(abs(r['projected_ortho_width'] - reaction['projected_ortho_width']) for r in held)
features = [project(r, point) for r in held for name, point in r['visual']['bones'].items()
            if name in ('head', 'ear_tip_L', 'ear_tip_R')]
checks = {
    'runtime_transition_and_control_return': report['success'],
    'whole_plate_inside_frame': all(.04 < value < .96 for value in plate),
    'statue_outside_reaction_frame': statue[1] < 0 or statue[0] > 1 or statue[3] < 0 or statue[2] > 1,
    'front_reaction_with_both_eyes': front_angle < 30,
    'reaction_hold_before_pullback': hold_distance < .1 and hold_zoom < .1,
    'head_and_ears_in_frame': all(.04 < value < .96 for point in features for value in point),
}
result = {'checks': checks, 'success': all(checks.values()), 'measurements': {
    'plate_screen_bounds': plate, 'statue_screen_bounds_at_reaction': statue,
    'front_angle_degrees': front_angle, 'hold_max_movement_cm': hold_distance,
    'hold_max_width_change_cm': hold_zoom,
}, 'scope': 'Actual PIE camera telemetry and separately measured saved-map bounds; image review remains required.'}
(args.run / 'framing_qa.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['success'] else 1)
