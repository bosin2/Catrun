"""Pure acceptance rules for Task4d's recorded API/native PIE observations.

No Unreal import, mutation of observations, or runtime claims beyond recorded data.
Immediate interrupted resets may still be closing; lifecycle verifies settled0.
"""
from math import isfinite

SEATS = {'A': (1875, 2585, .1), 'B': (410, 1070, .1), 'C': (1195, 3430, .1)}
TOPS = {'A': -34, 'B': -34, 'C': -54}
ANCHORS = {'A': (1525, 1260, 0), 'B': (1900, 2260, 0), 'C': (1375, 3210, 0)}
RED = (1, .005, .002, 1)
ORIGINAL = (1, .4, .07, 1)
RECOVERY_CASES = [('A', 'normal'), ('A', 'repeat'), ('A', 'reset_togate'),
                  ('B', 'normal'), ('C', 'blocked'), ('C', 'takeover'), ('C', 'reset_opening')]


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def near(value, expected, tolerance=.01):
    return number(value) and abs(value - expected) <= tolerance


def vector(value, expected):
    return isinstance(value, (list, tuple)) and len(value) == len(expected) and all(
        near(a, b) for a, b in zip(value, expected))


def acceptance_errors(kind, observations, require_complete=True):
    """Return named failures, checking a completed-case prefix or the complete run."""
    if kind not in ('routes', 'recovery', 'visual'):
        raise ValueError('Unknown Task4d validator: ' + kind)
    errors = []

    def check(condition, label):
        if not condition:
            errors.append(label)

    rows = observations.get('results', [])
    expected = RECOVERY_CASES if kind == 'recovery' else list(SEATS)
    check(len(rows) == len(expected) if require_complete else 0 < len(rows) <= len(expected),
          f'{kind}.result_count: expected {len(expected)}' + ('' if require_complete else ' or completed prefix'))
    for index, row in enumerate(rows):
        key = row.get('puzzle')
        identity = (key, row.get('case')) if kind == 'recovery' else key
        label = f'{kind}[{index}:{identity}]'
        check(index < len(expected) and identity == expected[index], label + '.case_order')
        if key not in SEATS:
            continue
        if kind == 'routes':
            for field in ('complete', 'move_restored'):
                check(row.get(field) is True, label + '.' + field)
            check(near(row.get('gate_offset'), -280), label + '.gate_offset')
            check(near(row.get('gate_top'), TOPS[key]), label + '.gate_top')
            check(vector(row.get('seat'), SEATS[key]), label + '.seat')
            phases = [x for x in row.get('phases', []) if x != 'INACTIVE']
            check(phases == ['TO_GATE', 'OPENING', 'RETURNING'], label + '.phases')
        elif kind == 'recovery':
            case = row.get('case')
            for field in ('reset_original_eye', 'stale_session_ignored', 'bars_cleared',
                          'dust_cleared', 'view_preserved', 'other_rooms_unchanged'):
                check(row.get(field) is True, label + '.' + field)
            check(number(row.get('baseline_count')) and row['baseline_count'] > 0 and
                  row.get('actor_count') == row['baseline_count'], label + '.actor_count')
            check(number(row.get('elapsed_game')) and 0 < row['elapsed_game'] <= 8.25, label + '.bounded_time')
            check(row.get('move_ignored') is (case == 'takeover'), label + '.move_ignored')
            check(row.get('pressed') is (case not in ('reset_togate', 'reset_opening')), label + '.pressed')
            check(row.get('complete') is (case in ('normal', 'repeat')), label + '.complete')
            check(vector(row.get('eye'), ORIGINAL if case in ('reset_togate', 'reset_opening') else RED), label + '.eye')
            if case in ('normal', 'repeat'):
                check(near(row.get('offset'), -280), label + '.offset')
            elif case in ('blocked', 'reset_togate'):
                check(near(row.get('offset'), 0), label + '.offset')
            else:
                check(number(row.get('offset')) and -280 < row['offset'] <= 0, label + '.offset')
            if case == 'takeover':
                check(row.get('unrelated_input_lock_preserved') is True, label + '.unrelated_input_lock_preserved')
            if case == 'blocked':
                check(number(row.get('elapsed_game')) and row['elapsed_game'] >= 8, label + '.timeout_reached')
                after = row.get('after_unblock', {})
                for field in ('complete', 'no_effect_revival', 'control_restored'):
                    check(after.get(field) is True, label + '.after_unblock.' + field)
                check(near(after.get('offset'), -280), label + '.after_unblock.offset')
            # stale_revision_ignored is an honest static-only note, not a runtime boolean.
        else:
            below = row.get('below', {})
            check(number(below.get('ratio')) and 0 <= below['ratio'] < .8, label + '.below.ratio')
            check(below.get('pressed') is False, label + '.below.pressed')
            check(vector(below.get('eye'), ORIGINAL), label + '.below.eye')
            check(number(row.get('above_ratio_before_seat')) and .8 <= row['above_ratio_before_seat'] <= 1,
                  label + '.above_ratio_before_seat')
            for field in ('complete', 'return_view', 'input_restored', 'no_active_presentation',
                          'no_dust', 'gameplay_postprocess_unchanged'):
                check(row.get(field) is True, label + '.' + field)
            check(near(row.get('gate_offset'), -280), label + '.gate_offset')
            check(near(row.get('gate_top'), TOPS[key]), label + '.gate_top')
            check(vector(row.get('seat'), SEATS[key]), label + '.seat')
            check(number(row.get('baseline_count')) and row['baseline_count'] > 0 and
                  row.get('actor_count') == row['baseline_count'], label + '.actor_count')
            samples = [s for s in observations.get('samples', []) if s.get('puzzle') == key]
            check({'TO_GATE', 'OPENING', 'RETURNING', 'INACTIVE'} <= {s.get('phase') for s in samples}, label + '.sample_phases')
            for j, sample in enumerate(samples):
                item = label + f'.sample[{j}]'
                active = sample.get('phase') != 'INACTIVE'
                check(sample.get('active') is active, item + '.active')
                check(sample.get('dust') is (sample.get('phase') == 'OPENING'), item + '.dust')
                check(vector(sample.get('dust_anchor'), ANCHORS[key]), item + '.dust_anchor')
                check(vector(sample.get('eyes'), RED) and near(sample.get('strength'), 5), item + '.eyes')
                if active:
                    check(sample.get('session') == sample.get('presentation_session') and number(sample.get('session')), item + '.session')
                    check(sample.get('projection') == '<CameraProjectionMode.ORTHOGRAPHIC: 1>', item + '.projection')
                    check(sample.get('motion_blur') == {'override': True, 'amount': 0.0}, item + '.motion_blur')
                    check(number(sample.get('width')) and sample['width'] > 0, item + '.width')
                    if sample.get('phase') == 'OPENING':
                        check(near(sample.get('width'), 650), item + '.opening_width')
    return errors


def acceptance_error(kind, observations, require_complete=True):
    failures = acceptance_errors(kind, observations, require_complete)
    return 'Acceptance failed: ' + '; '.join(failures) if failures else None
