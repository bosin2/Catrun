"""Inert observer extending the proven 53-check native reset/replay harness.

Measures both D1/D2 ToGate/Opening/Returning using native phase transitions and
camera positions. It does not alter timing/cameras/effects. Four real openings
include two normal full returns and two mid-impact resets. No GPU screenshots.
"""
import importlib.util
import time
import traceback
from pathlib import Path
import unreal as u

_p = Path(__file__).resolve().parents[1]/'GateFXRevision20261125/reset_replay.py'
_s = importlib.util.spec_from_file_location('s3_pacing_native_base', _p)
base = importlib.util.module_from_spec(_s)
_s.loader.exec_module(base)
TARGET = {'CameraTravelTime': 3., 'CameraReturnTime': 2.6, 'MaximumLockTime': 10.5}


class Harness(base.Harness):
    def __init__(self, pass_name):
        # Base creates only an empty output dir; reports themselves belong to
        # this run's CameraPacing folder. No earlier evidence is overwritten.
        super().__init__('CameraPacing_'+pass_name, capture=False)
        self.out = self.root/'Saved/Stage3CameraPacingRevision20261125'/pass_name
        assert not self.out.exists(), 'Fresh pass required'
        self.out.mkdir(parents=True)
        self.defer = False
        self.s.update(scope=__doc__, pacing_sessions={}, pacing_samples=[], timing_writes=0,
                      capture=False, native_timing_target=TARGET)

    def persist(self):
        if not getattr(self, 'defer', False):
            super().persist()

    def setup(self, world, cat):
        super().setup(world, cat)
        for key,value in TARGET.items():
            self.check('Saved '+key+' matches Stage2 pacing', abs(self.s['native_reveal_tuning'][key]-value)<1e-5)
        self.check('Stage3 original framing and offset retained',
                   self.s['native_reveal_tuning']['bPreserveGameplayFraming']
                   and self.s['native_reveal_tuning']['GateCameraOffset'] == [0.,400.,160.])
        settings = self.live['puzzle'].get_editor_property('Settings')
        self.s['native_gate_speed_cm_s'] = float(settings.get_editor_property('GateSpeed'))

    def observe(self, world):
        reveal = self.live['reveal']
        phase = str(reveal.get_editor_property('Phase')).split('.')[1].split(':')[0]
        sid = str(reveal.get_editor_property('SessionId'))
        game = u.GameplayStatics.get_time_seconds(world)
        rows = self.s['pacing_sessions']
        if phase == 'INACTIVE' and sid not in rows:
            return phase
        if phase == 'INACTIVE' and 'INACTIVE' in rows[sid]['phase_first']:
            # Later device interactions own their own input lock; inspect the
            # reveal's immediate cleanup once, not unrelated idle gameplay.
            return phase
        row = rows.setdefault(sid, {'gate': self.s['gate_index']+1, 'cycle': self.s['cycle']+1,
                                   'phase_first': {}, 'samples': 0, 'max_game_step': 0.})
        if 'last_game' in row:
            row['max_game_step'] = max(row['max_game_step'], game-row['last_game'])
        row['last_game'] = game
        row['samples'] += 1
        row['phase_first'].setdefault(phase, game)
        camera = reveal.get_reveal_camera()
        sample = {'game': game, 'session': sid, 'phase': phase, 'gate': row['gate'], 'cycle': row['cycle']}
        controller = u.GameplayStatics.get_player_controller(world, 0)
        ignored = [controller.is_move_input_ignored(), controller.is_look_input_ignored()]
        sample['input_ignored'] = ignored
        if phase != 'INACTIVE':
            assert ignored == [True, True], ('Native reveal input lock missing', sample)
        else:
            assert ignored == [False, False], ('Native reveal input lock not released', sample)
            row['cleanup_input_ignored'] = ignored
            row['cleanup_view_target'] = controller.get_view_target().get_path_name()
        if camera:
            c = camera.get_component_by_class(u.CameraComponent)
            assert c, 'Native reveal camera has no CameraComponent'
            rotation = camera.get_actor_rotation()
            framing = {k: str(c.get_editor_property(k)) for k in
                       ('projection_mode','ortho_width','field_of_view','aspect_ratio','ortho_near_clip_plane','ortho_far_clip_plane')}
            angles = [rotation.pitch,rotation.yaw,rotation.roll]
            sample.update(camera=base.vec(camera.get_actor_location()), rotation=angles)
            row.setdefault('camera_framing', framing)
            row.setdefault('camera_rotation', angles)
            assert framing == row['camera_framing'], ('Native framing changed during pacing', sample)
            assert max(abs(a-b) for a,b in zip(angles,row['camera_rotation'])) < .001, ('Camera turned during pan', sample)
            if phase == 'TO_GATE':
                row.setdefault('pan_start', sample['camera'])
            if phase == 'OPENING':
                row.setdefault('pan_end', sample['camera'])
        self.s['pacing_samples'].append(sample)
        return phase

    def step(self, world):
        phase = None
        if 'reveal' in self.live:
            phase = self.observe(world)
            self.defer = phase != 'INACTIVE'
        # Original harness checks replay after 1.1s; now native return lasts
        # 2.6s. Wait for its actual Inactive rather than forcing early cleanup.
        if self.s['phase'] == 'replay_settle' and phase != 'INACTIVE':
            elapsed = u.GameplayStatics.get_time_seconds(world)-self.s['phase_start_game']
            assert elapsed < 5., 'Native slow return did not release its session'
            fx = self.effect(self.s['gate_index'])
            assert fx['count'] == 2, ('Replay effect repeated during extended return', fx)
            if fx['active']:
                assert fx['age'] < .78, ('Dust exceeds original lifetime', fx)
                if fx['age'] >= .26:
                    assert abs(fx['rumble']) < 1e-8, ('Rumble exceeds original lifetime', fx)
            if elapsed >= .85:
                assert self.silent(fx), ('Dust must finish before long camera return ends', fx)
            return
        super().step(world)

    def finish(self, error=None):
        if self.s['phase'] == 'shutdown':
            return
        self.defer = False
        if not error:
            try:
                rows = list(self.s['pacing_sessions'].values())
                self.check('Four native reveal sessions observed', len(rows)==4)
                for row in rows:
                    first = row['phase_first']
                    prefix = 'D%d cycle%d ' % (row['gate'],row['cycle'])
                    outbound = first['OPENING']-first['TO_GATE']
                    opening = first['RETURNING']-first['OPENING']
                    row.update(measured_outbound_s=outbound, measured_opening_s=opening)
                    self.check(prefix+'actual camera travel takes 3 seconds', abs(outbound-3.)<.2, row)
                    link = self.links()[row['gate']-1]
                    expected_open = link.get_editor_property('RequiredGateTravel')/max(1.,self.s['native_gate_speed_cm_s'])
                    self.check(prefix+'gate descent speed remains unchanged', abs(opening-expected_open)<.2, row)
                    distance = (u.Vector(*row['pan_end'])-u.Vector(*row['pan_start'])).length()
                    row['actual_pan_distance_cm'] = distance
                    self.check(prefix+'actual camera pans toward its own gate', distance>100., distance)
                    if row['cycle']==2:
                        returning = first['INACTIVE']-first['RETURNING']
                        total = first['INACTIVE']-first['TO_GATE']
                        row.update(measured_return_s=returning, measured_session_s=total)
                        self.check(prefix+'natural return takes 2.6 seconds', abs(returning-2.6)<.2, row)
                        self.check(prefix+'normal cleanup precedes watchdog without abort', total<10. and abs(total-(3.+expected_open+2.6))<.35, row)
                        self.check(prefix+'normal return releases move/look input', row.get('cleanup_input_ignored') == [False,False], row)
            except Exception:
                error = traceback.format_exc()
        super().finish(error)

