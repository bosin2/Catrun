"""Offline regression proof: saved successful runs and in-memory failing copies.

The real harness finish functions are extracted with ast and executed with tiny
cleanup stubs; no Unreal import/editor call or fixture/binary write is performed.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from task4d_acceptance import acceptance_error, acceptance_errors

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'Saved/Prototype20261104/Task4d'
FIXTURES = {
    'stage_routes': ('routes', 'Routes-Stage2-181609'),
    'soundtest_routes': ('routes', 'Routes-SoundTest_Stage2-182253'),
    'recovery': ('recovery', 'Recovery-181954'),
    'visual': ('visual', 'VisualFinal-184204'),
}
HARNESSES = {'routes': 'verify_task4d_routes.py', 'recovery': 'verify_task4d_recovery.py',
             'visual': 'task4d_validate_visual.py'}


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {}
        cls.hashes = {}
        cls.mutations = 0
        for name, (kind, folder) in FIXTURES.items():
            path = EVIDENCE / folder / 'observations.json'
            cls.fixtures[name] = (kind, json.loads(path.read_text()))
            cls.hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()

    def reject(self, kind, original, path, value):
        data = deepcopy(original)
        target = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with self.subTest(kind=kind, path=path, value=value):
            self.assertIsNotNone(acceptance_error(kind, data))
        type(self).mutations += 1

    def test_saved_runs_and_completed_prefixes_pass_without_mutation(self):
        for kind, data in self.fixtures.values():
            before = deepcopy(data)
            self.assertEqual(acceptance_errors(kind, data), [])
            for count in range(1, len(data['results']) + 1):
                prefix = deepcopy(data)
                prefix['results'] = prefix['results'][:count]
                self.assertIsNone(acceptance_error(kind, prefix, require_complete=False))
            self.assertEqual(data, before)

    def test_route_failure_predicates(self):
        for name in ('stage_routes', 'soundtest_routes'):
            kind, data = self.fixtures[name]
            for index in range(3):
                for field, value in [('complete', False), ('move_restored', False),
                                     ('gate_offset', 0), ('gate_top', 5),
                                     ('seat', [0, 0, 0]), ('phases', ['TO_GATE']),
                                     ('gate_offset', float('nan')), ('gate_top', None)]:
                    self.reject(kind, data, ['results', index, field], value)

    def test_recovery_case_specific_predicates(self):
        kind, data = self.fixtures['recovery']
        common = ('reset_original_eye', 'stale_session_ignored', 'bars_cleared',
                  'dust_cleared', 'view_preserved', 'other_rooms_unchanged')
        for index, row in enumerate(data['results']):
            for field in common:
                self.reject(kind, data, ['results', index, field], False)
            for field, value in [('actor_count', 999), ('elapsed_game', 20),
                                 ('move_ignored', not row['move_ignored']),
                                 ('pressed', not row['pressed']), ('complete', not row['complete']),
                                 ('eye', [0, 0, 0, 1]), ('offset', 25)]:
                self.reject(kind, data, ['results', index, field], value)
        self.reject(kind, data, ['results', 5, 'unrelated_input_lock_preserved'], False)
        self.reject(kind, data, ['results', 4, 'elapsed_game'], 3)
        self.reject(kind, data, ['results', 4, 'after_unblock'], {})
        for field, value in [('complete', False), ('no_effect_revival', False),
                             ('control_restored', False), ('offset', 0)]:
            self.reject(kind, data, ['results', 4, 'after_unblock', field], value)

    def test_visual_endpoint_and_threshold_predicates(self):
        kind, data = self.fixtures['visual']
        for index in range(3):
            for field in ('complete', 'return_view', 'input_restored', 'no_active_presentation',
                          'no_dust', 'gameplay_postprocess_unchanged'):
                self.reject(kind, data, ['results', index, field], False)
            for field, value in [('gate_offset', 0), ('gate_top', 10), ('seat', [0, 0, 0]),
                                 ('actor_count', 999), ('above_ratio_before_seat', .79)]:
                self.reject(kind, data, ['results', index, field], value)
            for field, value in [('ratio', .81), ('pressed', True), ('eye', [1, 0, 0, 1])]:
                self.reject(kind, data, ['results', index, 'below', field], value)

    def test_visual_sample_predicates(self):
        kind, data = self.fixtures['visual']
        index = next(i for i, s in enumerate(data['samples']) if s['phase'] == 'OPENING')
        for field, value in [('active', False), ('dust', False), ('dust_anchor', [1, 2, 3]),
                             ('eyes', [1, .4, .07, 1]), ('strength', 0),
                             ('presentation_session', -1), ('projection', 'PERSPECTIVE'),
                             ('motion_blur', {'override': False, 'amount': .5}), ('width', 1170)]:
            self.reject(kind, data, ['samples', index, field], value)
        self.reject(kind, data, ['samples'], [])

    def test_completeness_and_order(self):
        for kind, data in self.fixtures.values():
            for rows in ([], data['results'][:-1], data['results'] + data['results'][:1],
                         data['results'][:1] * len(data['results'])):
                self.reject(kind, data, ['results'], rows)
            missing = deepcopy(data)
            del missing['results']
            self.assertIsNotNone(acceptance_error(kind, missing))

    def test_real_finish_functions_propagate_errors_and_preserve_raw_data(self):
        for name in ('stage_routes', 'recovery', 'visual'):
            kind, original = self.fixtures[name]
            tree = ast.parse((ROOT / 'Scripts/Prototype' / HARNESSES[kind]).read_text())
            finish = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'finish')
            code = compile(ast.Module(body=[finish], type_ignores=[]), HARNESSES[kind], 'exec')
            for scenario in ('pass', 'false_acceptance', 'missing_result', 'runtime_error'):
                with self.subTest(kind=kind, scenario=scenario), tempfile.TemporaryDirectory() as directory:
                    data = deepcopy(original)
                    if scenario == 'false_acceptance':
                        data['results'][0]['complete'] = False
                    if scenario == 'missing_result':
                        data['results'].pop()
                    raw = deepcopy(data)
                    data['handle'] = 123
                    cleanup = []
                    scope = {'s': data, 'OUT': Path(directory), 'json': json,
                             'acceptance_error': acceptance_error, 'acceptance_errors': acceptance_errors,
                             'unreal': SimpleNamespace(unregister_slate_post_tick_callback=lambda h: cleanup.append(h)),
                             'lv': SimpleNamespace(editor_request_end_play=lambda: cleanup.append('end'))}
                    exec(code, scope)
                    scope['finish']('sentinel runtime failure' if scenario == 'runtime_error' else None)
                    output = json.loads((Path(directory) / 'observations.json').read_text())
                    self.assertEqual(output['results'], raw['results'])
                    self.assertEqual(output.get('samples'), raw.get('samples'))
                    self.assertEqual(cleanup, [123, 'end'])
                    if scenario == 'pass':
                        self.assertIsNone(output['error'])
                    else:
                        self.assertIsNotNone(output['error'])
                    if scenario == 'runtime_error':
                        self.assertEqual(output['error'], 'sentinel runtime failure')
                    if scenario in ('false_acceptance', 'missing_result'):
                        self.assertTrue(output['acceptance_errors'])

    @classmethod
    def tearDownClass(cls):
        for path, before in cls.hashes.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != before:
                raise AssertionError('Saved evidence changed: ' + str(path))
        print(f'In-memory failing mutations rejected: {cls.mutations}; saved evidence hashes unchanged.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
