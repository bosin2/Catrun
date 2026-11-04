"""Reject a completed intro that never animated its actual possessed cat.

This reads recorded evidence; it neither starts the game nor repairs bindings.
Rendered inspection remains necessary for animation quality and intersections.
"""
import argparse
import json
import re
from pathlib import Path


def sequence_frame(row):
    match = re.search(r'frame_number: \{value: (\d+)\}, sub_frame: ([\d.]+)', row.get('sequence_time', ''))
    return float(match[1]) + float(match[2]) if match else None


def pose_span(rows):
    if len(rows) < 2:
        return 0.0
    common = set.intersection(*(set(row.get('bone_components', {})) for row in rows))
    return max((max(row['bone_components'][bone][axis] for row in rows)
                - min(row['bone_components'][bone][axis] for row in rows)
                for bone in common for axis in range(7)), default=0.0)


def evaluate(data):
    rows = [row for row in data.get('samples', []) if 'tutorial_elapsed' in row]
    playing = [row for row in rows if row.get('intro_playing')]
    last = rows[-1] if rows else {}
    views = list(dict.fromkeys(row.get('view') for row in rows))
    expected_views = ['CineCameraActor_0', 'CineCameraActor_3', 'Cam_03_LookDemon_0',
                      'Cam_03B_CatFaceAfterDemon_0', 'Cam_04_LookMonster_0',
                      'Cam_05_MoveToEdge_0', 'Cam_06_Jump_0', 'Cam_07_Landing_0',
                      'BP_QuarterViewCamera_C_0']
    checks = {
        'observer_clean': data.get('error') is None and data.get('menu_seen') is True,
        'playback_observed': len(playing) >= 20,
        'canonical_tutorial': bool(rows) and all(re.fullmatch(r'(?:UEDPIE_\d+_)?Tutorial', row.get('world', '')) for row in rows),
        'original_sequence': bool(playing) and all(row.get('sequence_path') == '/Game/Cinematics/LS_Tutorial.LS_Tutorial' for row in playing),
        'actual_pawn_bound': bool(playing) and all(row.get('pawn_path') and row.get('bindings', {}).get('BP_Cat_Player') == [row['pawn_path']] for row in playing),
        'sequencer_animation': bool(playing) and all(row.get('animation_instance') == 'AnimSequencerInstance' for row in playing),
        'original_camera_order': views == expected_views,
        'animation_restored': last.get('animation_instance') == 'ABP_Cat_Final_C' and not last.get('intro_playing', True),
        'controls_restored': last.get('move_ignored') is False and 'WALKING' in last.get('movement_mode', ''),
        'original_hint': data.get('saw_hint') is True,
    }
    phases = {}
    # Interior moving intervals avoid intentional fixed-pose wake/idle holds.
    for name, start, end in [('wake', 93, 150), ('stand', 378, 426),
                             ('walk', 431, 467), ('jump', 534, 569), ('land', 571, 601)]:
        samples = [row for row in playing if (frame := sequence_frame(row)) is not None and start <= frame <= end]
        span = pose_span(samples)
        phases[name] = {'samples': len(samples), 'component_pose_span': span}
        checks[name + '_pose_changes'] = len(samples) >= 2 and span > .001
    return {'accepted': all(checks.values()), 'checks': checks, 'phases': phases,
            'scope': 'Binding, phase motion, camera order and restoration; rendered quality reviewed separately.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.observations.read_text(encoding='utf-8-sig')))
    args.observations.with_name('intro-acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['accepted'] else 1)
