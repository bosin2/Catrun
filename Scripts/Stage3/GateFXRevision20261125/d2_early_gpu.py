"""Inert focused native D2 impact observer, with no critical-window disk writes.

Reuses three real device TryRelease/Commit interactions and native cat Tick push.
No D1 solve, reset/replay, presenter calls, camera/timing edits or package saves.
Screenshots are requests from the unchanged gameplay camera, not visual approval.
"""
import hashlib
import importlib.util
import time
import traceback
from pathlib import Path
import unreal as u

_spec = importlib.util.spec_from_file_location('s3_d2_base', Path(__file__).with_name('reset_replay.py'))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


class Harness(base.Harness):
    def __init__(self, pass_name):
        super().__init__(pass_name, capture=True)
        self.s.update(scope=__doc__, warmup={}, critical_disk_writes=0,
                      visual_acceptance='Pending inspection of one actual-camera early-dust PNG',
                      capture_policy='03: first-active memory only; one early dust capture; preserve 01/02 failures')
        self.defer_persist = False
        self.starting_devices = True

    def persist(self):
        if not getattr(self, 'defer_persist', False):
            super().persist()

    def begin_push(self, world, index, cycle):
        if self.starting_devices:
            self.starting_devices = False
            self.s.update(gate_index=1, cycle=0)
            self.stage_device(world, 0)
            return
        assert index == 1 and cycle == 0, 'Focused run solves D2 once only'
        super().begin_push(world, index, cycle)

    def camera_row(self, world):
        camera = u.GameplayStatics.get_player_camera_manager(world, 0)
        rotation = camera.get_camera_rotation()
        actor = self.live['effects'][1]
        result = {'location': base.vec(camera.get_camera_location()),
                  'rotation': [rotation.pitch, rotation.yaw, rotation.roll],
                  'effect_origin': base.vec(actor.get_actor_location()),
                  'native_phase': str(self.live['reveal'].get_editor_property('Phase'))}
        try:
            point = actor.get_actor_location() + u.Vector(0, 0, 14)
            screen = u.GameplayStatics.project_world_to_screen(u.GameplayStatics.get_player_controller(world, 0), point, False)
            viewport = u.WidgetLayoutLibrary.get_viewport_size(world)
            result.update(effect_screen=[screen.x, screen.y] if screen else None,
                          viewport=[viewport.x, viewport.y])
        except Exception as exc:
            result['projection_observation_error'] = str(exc)
        return result

    def shoot(self, world, name):
        assert not self.s['screenshots']
        super().shoot(world, name)
        self.s['screenshots'][-1]['view'] = self.camera_row(world)
        self.s['screenshots'][-1]['capture_note'] = 'Request-time state; inspect rendered PNG independently'

    @staticmethod
    def origin_in_view(view):
        screen, size = view.get('effect_screen'), view.get('viewport')
        return bool(screen and size and size[0] > 0 and size[1] > 0
                    and 0 <= screen[0] < size[0] and 0 <= screen[1] < size[1])

    def step_device(self, world, game):
        # The original sequential harness has already completed D1 here and
        # reads its last cycle unconditionally. This focused run deliberately
        # has no cycle until the real P2 push starts; do not fabricate one.
        phase = self.s['phase']
        elapsed = game - self.s['phase_start_game']
        assert elapsed < 20., ('Native device phase timeout', phase, elapsed)
        cat = self.live['cat']
        director = self.live['objectives']
        n = self.s['device_index']
        fx = self.effect(1)
        assert self.silent(fx) and fx['count'] == 0, ('D2 effect before native push', fx)
        assert base.read_reveal_tuning(self.live['reveal']) == self.s['native_reveal_tuning']
        if phase == 'device_ready':
            if elapsed < .25:
                return
            self.check('D2 prerequisite device%d native TryRelease starts' % (n + 1), director.try_release(n, cat))
            self.s['device_releases'].append({'index': n, 'started_game': game, 'commit_clip_s': None})
            self.phase('device_playing', world)
            return
        assert phase == 'device_playing'
        device = director.get_editor_property('Devices')[n]
        record = self.s['device_releases'][-1]
        if device.get_editor_property('bReleased') and record['commit_clip_s'] is None:
            mesh = cat.get_component_by_class(u.SkeletalMeshComponent)
            record['commit_clip_s'] = mesh.get_position() if isinstance(mesh.get_anim_instance(), u.AnimSingleNodeInstance) else -1.
            self.check('D2 prerequisite device%d physically commits after frame44' % (n + 1),
                       record['commit_clip_s'] >= 44. / 30., record)
        if director.get_editor_property('ActiveDevice') != -1:
            return
        self.check('D2 prerequisite device%d releases and restores player' % (n + 1),
                   device.get_editor_property('bReleased')
                   and not cat.get_component_by_class(u.CatrunBasketInteractionComponent).get_editor_property('Busy'))
        if n < 2:
            self.stage_device(world, n + 1)
        else:
            self.check('D2 native unlock comes from all three real releases', director.all_released())
            self.begin_push(world, 1, 0)

    def step(self, world):
        game = u.GameplayStatics.get_time_seconds(world)
        if self.s['phase'] == 'startup':
            cat = u.GameplayStatics.get_player_character(world, 0)
            if not cat or game < 3.:
                return
            warmup = self.s['warmup']
            if not warmup:
                u.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
                warmup.update(first_finish_all_returned=True, started_wall=time.monotonic(), ticks=0)
            warmup['ticks'] += 1
            if time.monotonic() - warmup['started_wall'] < 10. or warmup['ticks'] < 60:
                return
            u.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
            warmup.update(second_finish_all_returned=True, finished_game=game)
            self.setup(world, cat)
            return

        if self.s['phase'] in ('device_ready', 'device_playing'):
            self.step_device(world, game)
            return

        if self.s['phase'] not in ('opening', 'focused_impact'):
            super().step(world)
            return

        # Full report serialization is intentionally absent during actual gate
        # opening/impact. ResetReplay01 wrote thousands of rows three times at
        # completion, then observed a .283/.316s next-frame jump.
        self.defer_persist = True
        phase = self.s['phase']
        link = self.links()[1]
        fx = self.effect(1)
        row = {'game': game, 'wall': time.monotonic(), 'phase': phase,
               'native_phase': str(self.live['reveal'].get_editor_property('Phase')),
               'completed': link.get_editor_property('bCompleted'),
               'gate_z': link.get_editor_property('Gate').get_actor_location().z,
               'gate_offset': link.get_editor_property('GateOffset'), 'fx': fx,
               'view': self.camera_row(world)}
        self.s.setdefault('focused_samples', []).append(row)
        assert game - self.s['phase_start_game'] < 15., ('Focused phase timeout', row)
        assert base.read_reveal_tuning(self.live['reveal']) == self.s['native_reveal_tuning']
        assert fx['no_collision'] and fx['component_count'] == self.s['initial'][1]['fx']['component_count']
        if phase == 'opening':
            if not row['completed']:
                assert fx['count'] == 0 and not fx['active'], ('Premature effect', row)
                return
            self.check('D2 native completion reaches actual gate end',
                       abs(row['gate_offset'] + link.get_editor_property('RequiredGateTravel')) < .05
                       and abs(row['gate_z'] - self.live['effects'][1].get_editor_property('ExpectedOpenZ')) < .1, row)
            self.check('D2 first completion produces one pooled impact',
                       fx['count'] == 1 and fx['active'] and fx['shown_cards'] == 8, fx)
            self.s['first_active'] = row
            # Age zero has no dust opacity. A HighResShot here also hitches the
            # next frame (02 observed .4167s), destroying the early-dust window.
            # Retain this event in memory only; no screenshot or disk write.
            self.phase('focused_impact', world)
            return
        assert fx['count'] == 1, ('Unexpected repeat', row)
        if self.s['screenshots'] and 'post_capture_frame' not in self.s:
            shot = self.s['screenshots'][0]
            self.s['post_capture_frame'] = {'game_delta': game - shot['game'],
                                           'wall_delta': row['wall'] - self.s['capture_request_wall'],
                                           'state': row}
        if not self.s['screenshots'] and fx['active'] and fx['age'] >= .045:
            self.check('Only capture is within early dust and rumble envelope',
                       fx['age'] < .26 and fx['rumble'] > 0 and fx['shown_cards'] == 8
                       and self.origin_in_view(row['view']), row)
            self.s['capture_request_wall'] = time.monotonic()
            self.shoot(world, 'D2_EarlyDust')
        if game - self.s['phase_start_game'] < 1.2:
            return
        self.check('D2 settles silently through original camera return', self.silent(fx)
                   and 'INACTIVE' in row['native_phase'], row)
        self.check('D1 remains untriggered throughout focused D2 run', self.effect(0)['count'] == 0)
        self.check('First active observation occurs within rumble envelope',
                   self.s['first_active']['fx']['age'] < .26 and self.s['first_active']['fx']['rumble'] > 0,
                   self.s['first_active'])
        self.check('Single request retains visible-origin early native dust and rumble',
                   len(self.s['screenshots']) == 1
                   and .045 <= self.s['screenshots'][0]['fx']['age'] < .26
                   and self.s['screenshots'][0]['fx']['rumble'] > 0
                   and self.s['screenshots'][0]['fx']['shown_cards'] == 8
                   and self.origin_in_view(self.s['screenshots'][0]['view']), self.s['screenshots'])
        self.finish()

    def finish(self, error=None):
        if self.s['phase'] == 'shutdown':
            return
        self.defer_persist = False
        try:
            self.s['hashes_after'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                      for p in self.s['hashes_before']}
            self.check('Saved maps and presentation packages preserved',
                       self.s['hashes_after'] == self.s['hashes_before'])
            if not error:
                self.check('Four isolated clear stagings, three releases and one native push',
                           len(self.s['staging']) == 4 and len(self.s['device_releases']) == 3
                           and len(self.s['cycles']) == 1)
                for shot in self.s['screenshots']:
                    shot['written'] = Path(shot['path']).exists() and Path(shot['path']).stat().st_size > 1024
                self.check('One actual-camera early-dust GPU capture written', len(self.s['screenshots']) == 1
                           and all(shot['written'] for shot in self.s['screenshots']))
        except Exception:
            error = (error or '') + '\n' + traceback.format_exc()
        self.s.update(success=error is None, error=error, phase='shutdown', changed=time.monotonic())
        self.persist()
        if self.ed.get_game_world():
            self.le.editor_request_end_play()

