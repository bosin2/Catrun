"""Inert diagnostic fixture: pause one real D2 impact, compare cards on/off.

This is NOT an ordinary-play capture or a substitute for native regression.
It uses native device releases and P2 push, then explicitly pauses test PIE at
age >= .08 s. Only the eight dust cards' hidden flags differ between two PNGs.
The camera, materials, native timing parameters and presenter activation are
never changed. Flags are restored and PIE resumed for natural cleanup.
"""
import hashlib
import importlib.util
import time
import traceback
from pathlib import Path
import unreal as u

spec = importlib.util.spec_from_file_location('s3_d2_early_compare_base', Path(__file__).with_name('d2_early_gpu.py'))
focused = importlib.util.module_from_spec(spec)
spec.loader.exec_module(focused)


class Harness(focused.Harness):
    def __init__(self, pass_name):
        super().__init__(pass_name)
        self.s.update(scope=__doc__, capture_policy='Diagnostic paused same-game-time dust cards on/off',
                      visual_acceptance='Pending pixel difference and independent inspection',
                      test_pause_count=0, fixture_restored=False)
        self.paused_by_fixture = False
        self.cards = []
        self.original_hidden = []
        self.phase_ticks = 0

    def set_phase(self, name, world):
        self.phase_ticks = 0
        self.phase(name, world)

    def fixed_state(self, world):
        return {'game': u.GameplayStatics.get_time_seconds(world),
                'view': self.camera_row(world), 'fx': self.effect(1),
                'native_tuning': focused.base.read_reveal_tuning(self.live['reveal'])}

    def verify_fixed(self, world):
        now = self.fixed_state(world)
        original = self.s['paused_state']
        assert u.GameplayStatics.is_game_paused(world), 'Comparison must remain explicitly paused'
        assert abs(now['game'] - original['game']) < 1e-6, ('Game time changed', now)
        for field in ('location', 'rotation'):
            assert max(abs(a-b) for a,b in zip(now['view'][field], original['view'][field])) < 1e-4, ('Camera changed', now)
        for key in ('count', 'active', 'armed', 'age', 'rumble', 'component_count', 'no_collision'):
            assert now['fx'][key] == original['fx'][key], ('Native effect advanced while paused', key, now)
        assert now['native_tuning'] == self.s['native_reveal_tuning']
        return now

    def request_picture(self, world, name):
        assert len(self.s['screenshots']) < 2
        row = self.verify_fixed(world)
        path = self.out / (name + '.png')
        row.update(name=name, path=str(path), request_wall=time.monotonic(),
                   fixture='Game paused at native impact; only dust hidden flags differ')
        self.s['screenshots'].append(row)
        u.SystemLibrary.execute_console_command(world, 'HighResShot 1280x720 filename="' + str(path) + '"')

    def ready(self):
        self.phase_ticks += 1
        return self.phase_ticks >= 8 and time.monotonic() - self.s['changed'] >= .5

    def restore_fixture(self, world):
        for card, hidden in zip(self.cards, self.original_hidden):
            card.set_hidden_in_game(hidden, False)
        if self.paused_by_fixture:
            assert u.GameplayStatics.set_game_paused(world, False), 'Resume fixture failed'
            self.paused_by_fixture = False
        self.s['fixture_restored'] = all(card.get_editor_property('hidden_in_game') == hidden
                                       for card,hidden in zip(self.cards, self.original_hidden))

    def step(self, world):
        phase = self.s['phase']
        if phase not in ('focused_impact', 'compare_on_warm', 'compare_on_written',
                         'compare_off_warm', 'compare_off_written', 'compare_resume'):
            super().step(world)
            return
        self.defer_persist = True
        game = u.GameplayStatics.get_time_seconds(world)
        if phase == 'focused_impact':
            fx = self.effect(1)
            assert fx['active'] and fx['count'] == 1, ('Native impact lost before diagnostic pause', fx)
            if fx['age'] < .08:
                return
            self.check('Diagnostic pause begins in real early visible-origin impact',
                       fx['age'] < .26 and fx['rumble'] > 0 and fx['shown_cards'] == 8
                       and self.origin_in_view(self.camera_row(world)), fx)
            actor = self.live['effects'][1]
            self.cards = [actor.get_editor_property('Dust%02d' % i) for i in range(8)]
            self.original_hidden = [card.get_editor_property('hidden_in_game') for card in self.cards]
            assert u.GameplayStatics.set_game_paused(world, True), 'Diagnostic pause rejected'
            self.paused_by_fixture = True
            self.s['test_pause_count'] += 1
            self.s['paused_state'] = self.fixed_state(world)
            self.set_phase('compare_on_warm', world)
            return
        if phase == 'compare_resume':
            assert focused.base.read_reveal_tuning(self.live['reveal']) == self.s['native_reveal_tuning']
            if game - self.s['phase_start_game'] < 1.2:
                return
            self.check('Resume naturally clears native effect and camera session',
                       self.silent(self.effect(1)) and 'INACTIVE' in str(self.live['reveal'].get_editor_property('Phase')))
            self.check('D1 remains untriggered', self.effect(0)['count'] == 0)
            self.finish()
            return
        self.verify_fixed(world)
        assert time.monotonic() - self.s['changed'] < 20., ('Diagnostic GPU phase timeout', phase)
        if not self.ready():
            return
        if phase == 'compare_on_warm':
            self.check('Visible comparison has exactly eight cards', self.effect(1)['shown_cards'] == 8)
            self.request_picture(world, 'D2_DustVisible_Paused')
            self.set_phase('compare_on_written', world)
        elif phase == 'compare_on_written':
            path = Path(self.s['screenshots'][-1]['path'])
            if not path.exists() or path.stat().st_size <= 1024:
                return
            for card in self.cards:
                card.set_hidden_in_game(True, False)
            self.set_phase('compare_off_warm', world)
        elif phase == 'compare_off_warm':
            self.check('Hidden comparison changes only eight card visibility flags', self.effect(1)['shown_cards'] == 0)
            self.request_picture(world, 'D2_DustHidden_Paused')
            self.set_phase('compare_off_written', world)
        elif phase == 'compare_off_written':
            path = Path(self.s['screenshots'][-1]['path'])
            if not path.exists() or path.stat().st_size <= 1024:
                return
            self.s['comparison_end_state'] = self.verify_fixed(world)
            self.restore_fixture(world)
            self.check('Eight visibility flags restored before native resume', self.s['fixture_restored']
                       and self.effect(1)['shown_cards'] == 8)
            self.set_phase('compare_resume', world)

    def finish(self, error=None):
        if self.s['phase'] == 'shutdown':
            return
        self.defer_persist = False
        try:
            world = self.ed.get_game_world()
            if world and self.paused_by_fixture:
                self.restore_fixture(world)
            self.s['hashes_after'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                      for p in self.s['hashes_before']}
            self.check('Comparison preserves saved maps and presentation packages',
                       self.s['hashes_after'] == self.s['hashes_before'])
            if not error:
                self.check('Real three releases, one P2 push and four isolated stagings',
                           len(self.s['device_releases']) == 3 and len(self.s['cycles']) == 1
                           and len(self.s['staging']) == 4)
                self.check('Exactly one explicit diagnostic pause restored',
                           self.s['test_pause_count'] == 1 and self.s['fixture_restored'] and not self.paused_by_fixture)
                self.check('Two paused same-time diagnostic images written', len(self.s['screenshots']) == 2
                           and all(Path(s['path']).is_file() and Path(s['path']).stat().st_size > 1024 for s in self.s['screenshots']))
        except Exception:
            error = (error or '') + '\n' + traceback.format_exc()
        self.s.update(success=error is None, error=error, phase='shutdown', changed=time.monotonic())
        self.persist()
        if self.ed.get_game_world():
            self.le.editor_request_end_play()

