"""Conservative four-corner cap projection for the fixed actual cat camera."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GateHallRevision20261125'


def calculate():
    source = ROOT / 'Saved/Stage3IntegrationRevision20261125/GateBefore/report.json'
    view = next(v for v in json.loads(source.read_text())['views'] if v['name'] == 'GateMiddle')
    pitch, yaw = map(math.radians, view['rotation'][:2])
    up = [-math.sin(pitch) * math.cos(yaw), -math.sin(pitch) * math.sin(yaw), math.cos(pitch)]
    right = [-math.sin(yaw), math.cos(yaw), 0]
    offset = [view['camera'][i] - view['cat'][i] for i in range(3)]
    width, aspect = 900., 16 / 9
    half_height = width / aspect / 2
    regions = {'hall_inner_wall_faces': [-970, -4570, 470, -2930],
               'exit_approach_through_goal4690': [-530, -4690, 30, -4550]}
    poses = []
    for region, (x0, y0, x1, y1) in regions.items():
        for x in (x0, x1):
            for y in (y0, y1):
                poses.append({'region': region, 'cat': [x, y, view['cat'][2]]})
    samples = []
    for x in (-720, 220):
        for y in (3150, 3450, 3725, 4025, 4325):
            for px in (x - 75, x + 75):
                for py in (-y - 75, -y + 75):
                    for pose in poses:
                        cx, cy, cz = pose['cat']
                        dx, dy = px - cx - offset[0], py - cy - offset[1]
                        required = cz + offset[2] + (half_height - up[0] * dx - up[1] * dy) / up[2]
                        screen_x = right[0] * dx + right[1] * dy
                        samples.append({'pillar_center_world_xy': [x, -y], 'cap_corner_world_xy': [px, py],
                                        'cat_pose': pose['cat'], 'minimum_top_z_cm': required,
                                        'screen_x_cm': screen_x})
    worst = max(samples, key=lambda s: s['minimum_top_z_cm'])
    selected = math.ceil((worst['minimum_top_z_cm'] + 50) / 50) * 50
    report = {'success': True, 'method': 'Require all four horizontal cap corners above the viewport top at every region extremum; affine orthographic projection covers region interiors.',
              'source_camera_capture': str(source), 'width_cm': width, 'aspect_ratio': aspect,
              'rotation': view['rotation'], 'camera_minus_cat_cm': offset,
              'view_up': up, 'half_view_height_cm': half_height, 'cat_z_cm': view['cat'][2],
              'regions_world_xy': regions, 'extreme_cat_poses': poses, 'tested_cap_corner_pose_pairs': len(samples),
              'worst_case': worst, 'minimum_uniform_top_cm': worst['minimum_top_z_cm'],
              'minimum_plus50_cm': worst['minimum_top_z_cm'] + 50, 'selected_top_cm': selected,
              'worst_case_margin_above_viewport_cm': (selected - worst['minimum_top_z_cm']) * up[2],
              'assembly': {'preserve_existing_z_range': [0, 840], 'full_new_modules_cm': [540, 540, 540, 540],
                           'last_new_module_cm': 390, 'capital_z_range': [3390, 3450],
                           'new_modules_and_capital_collision': 'NoCollision', 'new_modules_and_capital_cast_shadow': False,
                           'source_meshes_or_materials_modified': False},
              'limitations': ['Fixed measured camera and player ground height only; jumps, zooms, changed pitch or camera offsets require a new bound.',
                              'Cap projection is proven numerically; actual GPU visibility, lighting and pillar occlusion still require root captures.']}
    assert selected == 3450 and abs(worst['screen_x_cm']) < width / 2
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'projection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(calculate(), indent=2))
