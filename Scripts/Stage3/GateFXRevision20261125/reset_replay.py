"""Inert D1/D2 native reset/replay harness; root alone calls Harness.start().

Each gate is solved by continuous cat movement -> native statue Tick -> real
gate displacement. ResetStatue is called during visible completion dust, then
the same puzzle is pushed and opened again. No FX calls/counter writes, statue
teleports, fake delegates, direct sound emission or package saves. D2 unlocks
through three actual TryRelease/animation/Commit interactions. Seven independent
clear cat staging fixtures and disabled NPCs isolate cosmetics from difficulty.
"""
import hashlib
import json
import time
import traceback
from pathlib import Path
import unreal as u


def vec(p):
    return [p.x, p.y, p.z]


def read_reveal_tuning(reveal):
    result = {key: reveal.get_editor_property(key) for key in
              ('CameraTravelTime', 'CameraReturnTime', 'MaximumLockTime', 'bPreserveGameplayFraming')}
    result['GateCameraOffset'] = vec(reveal.get_editor_property('GateCameraOffset'))
    return result


class Harness:
    def __init__(self, pass_name, capture=True):
        assert pass_name.replace('_', '').isalnum()
        self.root = Path(u.Paths.project_dir()).resolve()
        self.out = self.root / 'Saved/Stage3GateFXRevision20261125' / pass_name
        assert not self.out.exists(), 'Preserve earlier failure/success evidence'
        self.out.mkdir(parents=True)
        self.ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
        self.le = u.get_editor_subsystem(u.LevelEditorSubsystem)
        self.capture = capture
        self.s = {'scope': __doc__, 'phase': 'startup', 'checks': [], 'samples': [],
                  'cycles': [], 'device_releases': [], 'staging': [], 'screenshots': [],
                  'started': time.monotonic(), 'changed': time.monotonic(),
                  'direct_fx_calls': 0, 'fx_counter_writes': 0, 'direct_sound_calls': 0,
                  'direct_try_push_calls': 0, 'statue_teleports': 0, 'packages_saved': False,
                  'camera_writes': 0, 'command_line': u.SystemLibrary.get_command_line()}
        self.live = {}
        paths = [self.root / 'Content/Maps' / (name + '.umap') for name in ('Stage1', 'Stage2', 'Stage3')]
        paths += list((self.root / 'Content/Environment/Stage3/GateFX_20261125').rglob('*.uasset'))
        paths += list((self.root / 'Content/Systems/Interaction/Puzzles/Presentation').glob('*.uasset'))
        self.s['hashes_before'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}

    def persist(self):
        (self.out / 'report.json').write_text(json.dumps(self.s, indent=2), encoding='utf8')

    def check(self, name, value, detail=None):
        self.s['checks'].append({'name': name, 'passed': bool(value), 'detail': detail})
        self.persist()
        assert value, (name, detail)

    def phase(self, name, world):
        self.s['phase'] = name
        self.s['phase_start_game'] = u.GameplayStatics.get_time_seconds(world)
        self.s['changed'] = time.monotonic()
        self.persist()

    def links(self):
        return self.live['puzzle'].get_editor_property('Links')

    def effect(self, index):
        actor = self.live['effects'][index]
        mid = actor.get_editor_property('RumbleMID')
        cards = [actor.get_editor_property('Dust%02d' % i) for i in range(8)]
        return {'count': actor.get_editor_property('ImpactCount'),
                'active': actor.get_editor_property('DustActive'),
                'armed': actor.get_editor_property('Armed'),
                'session': actor.get_editor_property('OriginSessionId'),
                'age': actor.get_editor_property('ImpactAge'),
                'rumble': mid.get_scalar_parameter_value('Rumble') if mid else None,
                'shown_cards': sum(not c.get_editor_property('hidden_in_game') for c in cards),
                'no_collision': all(c.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION for c in cards),
                'component_count': len(actor.get_components_by_class(u.ActorComponent))}

    @staticmethod
    def silent(row):
        return not row['active'] and not row['armed'] and row['shown_cards'] == 0 and row['rumble'] == 0

    def stop(self):
        cat = self.live['cat']
        cat.consume_movement_input_vector()
        cat.get_component_by_class(u.CharacterMovementComponent).stop_movement_immediately()

    def stage(self, world, point, reason):
        cat = self.live['cat']
        capsule = cat.get_component_by_class(u.CapsuleComponent)
        point.z = capsule.get_scaled_capsule_half_height() + 2.2
        hit = u.SystemLibrary.capsule_trace_single_by_profile(world, point, point + u.Vector(0, 0, .1),
                capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height(),
                'Pawn', False, [cat], u.DrawDebugTrace.NONE, False)
        self.check(reason + ' staging capsule clear', not hit,
                   {k: str(v) for k, v in hit.to_dict().items()} if hit else vec(point))
        self.stop()
        cat.set_actor_location(point, False, True)
        self.s['staging'].append({'reason': reason, 'position': vec(point)})

    def setup(self, world, cat):
        actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
        self.live.update(cat=cat, puzzle=actors['S3_StatuePuzzles'], objectives=actors['S3_Objectives'],
                         effects=[actors['S3_GateImpact_D1'], actors['S3_GateImpact_D2']])
        self.live['reveal'] = self.live['puzzle'].get_editor_property('Reveal')
        self.s['native_reveal_tuning'] = read_reveal_tuning(self.live['reveal'])
        self.s['native_puzzle_tick_enabled'] = self.live['puzzle'].is_actor_tick_enabled()
        self.check('Native puzzle Tick enabled and movement input owns push', self.s['native_puzzle_tick_enabled']
                   and not self.live['puzzle'].get_editor_property('Settings').get_editor_property('bRequireInteractKey'))
        self.s['initial'] = []
        for index, link in enumerate(self.links()):
            row = {'id': str(link.get_editor_property('PuzzleId')),
                   'statue': vec(link.get_editor_property('Statue').get_actor_location()),
                   'plate': vec(link.get_editor_property('Plate').get_actor_location()),
                   'gate': vec(link.get_editor_property('Gate').get_actor_location()), 'fx': self.effect(index)}
            self.s['initial'].append(row)
            self.check('D%d BeginPlay silent' % (index + 1), self.silent(row['fx']) and row['fx']['count'] == 0)
            self.check('D%d begins unsolved and closed' % (index + 1), not link.get_editor_property('bCompleted')
                       and abs(link.get_editor_property('GateOffset')) < .05)
        disabled = []
        for cls in (u.CatrunArmor, u.CatrunCandle):
            for actor in u.GameplayStatics.get_all_actors_of_class(world, cls):
                actor.set_actor_tick_enabled(False)
                actor.set_actor_enable_collision(False)
                disabled.append(actor.get_actor_label())
        self.s['npc_fixture_disabled'] = disabled
        u.CatrunUserSettings.set_no_armor_capture_enabled(True)
        self.begin_push(world, 0, 0)

    def begin_push(self, world, index, cycle):
        link = self.links()[index]
        statue = link.get_editor_property('Statue')
        center, extent = statue.get_actor_bounds(False, False)
        plate_center, _ = link.get_editor_property('Plate').get_actor_bounds(False, False)
        raw = plate_center - center
        direction = u.Vector(1 if raw.x > 0 else -1, 0, 0) if abs(raw.x) >= abs(raw.y) else u.Vector(0, 1 if raw.y > 0 else -1, 0)
        capsule = self.live['cat'].get_component_by_class(u.CapsuleComponent)
        support = abs(direction.x) * extent.x + abs(direction.y) * extent.y
        point = center - direction * (support + capsule.get_scaled_capsule_radius() + 5.)
        self.s.update(gate_index=index, cycle=cycle)
        self.live['push_direction'] = direction
        row = {'gate': index + 1, 'cycle': cycle + 1, 'statue_start': vec(statue.get_actor_location()),
               'gate_start': vec(link.get_editor_property('Gate').get_actor_location()),
               'revision_start': link.get_editor_property('Revision'), 'push_direction': vec(direction),
               'count_before': self.effect(index)['count']}
        self.s['cycles'].append(row)
        self.stage(world, point, 'D%d cycle%d push' % (index + 1, cycle + 1))
        self.phase('push', world)

    def shoot(self, world, name):
        if not self.capture:
            return
        assert len(self.s['screenshots']) < 4
        path = self.out / (name + '.png')
        camera = u.GameplayStatics.get_player_camera_manager(world, 0)
        u.SystemLibrary.execute_console_command(world, 'HighResShot 1280x720 filename="' + str(path) + '"')
        self.s['screenshots'].append({'name': name, 'path': str(path),
            'game': u.GameplayStatics.get_time_seconds(world), 'camera': vec(camera.get_camera_location()),
            'rotation': str(camera.get_camera_rotation()), 'fx': self.effect(self.s['gate_index'])})

    def stage_device(self, world, index):
        self.s['device_index'] = index
        d = self.live['objectives'].get_editor_property('Devices')[index]
        housing = d.get_editor_property('Housing')
        point = housing.get_actor_location() + housing.get_actor_forward_vector() * 10 + housing.get_actor_right_vector() * 70
        self.stage(world, point, 'Native device%d' % (index + 1))
        self.phase('device_ready', world)

    def step(self, world):
        game = u.GameplayStatics.get_time_seconds(world)
        cat = u.GameplayStatics.get_player_character(world, 0)
        if not cat:
            return
        if self.s['phase'] == 'startup':
            if game >= 1.:
                self.setup(world, cat)
            return
        index, cycle = self.s['gate_index'], self.s['cycle']
        link = self.links()[index]
        fx = self.effect(index)
        phase = self.s['phase']
        elapsed = game - self.s['phase_start_game']
        reveal_phase = str(self.live['reveal'].get_editor_property('Phase'))
        state = {'game': game, 'phase': phase, 'gate': index + 1, 'cycle': cycle + 1,
                 'native_phase': reveal_phase, 'native_session': self.live['reveal'].get_editor_property('SessionId'),
                 'revision': link.get_editor_property('Revision'), 'completed': link.get_editor_property('bCompleted'),
                 'gate_offset': link.get_editor_property('GateOffset'),
                 'gate_z': link.get_editor_property('Gate').get_actor_location().z,
                 'statue': vec(link.get_editor_property('Statue').get_actor_location()),
                 'cat': vec(cat.get_actor_location()), 'last_input': vec(cat.get_last_movement_input_vector()), 'fx': fx}
        self.s['samples'].append(state)
        assert elapsed < (30. if phase == 'push' else 20.), ('Phase timeout', state)
        assert fx['no_collision'] and fx['component_count'] == self.s['initial'][index]['fx']['component_count'], ('FX pool/collision changed', state)
        assert fx['count'] <= 2, ('Repeated effect loop', state)
        current_tuning = read_reveal_tuning(self.live['reveal'])
        assert current_tuning == self.s['native_reveal_tuning'], 'Native reveal tuning changed'
        row = self.s['cycles'][-1]
        if phase == 'push':
            assert fx['count'] == cycle and not fx['active'], ('Effect before completion', state)
            if link.get_editor_property('bPressed'):
                self.stop()
                displacement = (link.get_editor_property('Statue').get_actor_location() - u.Vector(*row['statue_start'])).length()
                self.check('D%d cycle%d native Tick physically seats statue' % (index + 1, cycle + 1), displacement > 50., displacement)
                row['seated_game'] = game
                self.phase('opening', world)
            else:
                cat.add_movement_input(self.live['push_direction'], 1., False)
            return
        if phase == 'opening':
            if not link.get_editor_property('bCompleted'):
                assert fx['count'] == cycle and not fx['active'], ('Dust during opening', state)
                return
            self.check('D%d cycle%d native completion reaches actual recessed gate' % (index + 1, cycle + 1),
                       abs(link.get_editor_property('GateOffset') + link.get_editor_property('RequiredGateTravel')) < .05
                       and abs(state['gate_z'] - self.live['effects'][index].get_editor_property('ExpectedOpenZ')) < .1, state)
            self.check('D%d cycle%d native completion triggers exactly one visible impact' % (index + 1, cycle + 1),
                       fx['count'] == cycle + 1 and fx['active'] and fx['shown_cards'] == 8 and fx['rumble'] is not None, fx)
            row['completion_game'], row['completion_session'] = game, state['native_session']
            self.phase('impact', world)
            return
        if phase == 'impact':
            assert fx['active'], ('Impact vanished before screenshot/reset observation', state)
            if fx['age'] < .05:
                return
            self.shoot(world, 'D%d_%s' % (index + 1, 'BeforeReset' if cycle == 0 else 'Replay'))
            self.phase('reset_pending' if cycle == 0 else 'replay_settle', world)
            return
        if phase == 'reset_pending':
            # Let one active GPU frame render before native Reset cancels it.
            if elapsed < .08:
                return
            self.check('D%d reset occurs during active dust' % (index + 1), fx['active'] and fx['shown_cards'] == 8, fx)
            previous_revision = link.get_editor_property('Revision')
            self.check('D%d native ResetStatue succeeds' % (index + 1),
                       self.live['puzzle'].reset_statue(link.get_editor_property('PuzzleId')))
            after, reset_link = self.effect(index), self.links()[index]
            self.check('D%d Reset clears dust and rumble synchronously' % (index + 1), self.silent(after) and after['count'] == 1, after)
            self.check('D%d Reset increments revision and clears completed' % (index + 1),
                       reset_link.get_editor_property('Revision') == previous_revision + 1
                       and not reset_link.get_editor_property('bCompleted') and not reset_link.get_editor_property('bPressed'))
            self.check('D%d Reset restores original statue and plate positions' % (index + 1),
                       (reset_link.get_editor_property('Statue').get_actor_location() - u.Vector(*self.s['initial'][index]['statue'])).length() < .05
                       and (reset_link.get_editor_property('Plate').get_actor_location() - u.Vector(*self.s['initial'][index]['plate'])).length() < .05)
            row['reset_game'], row['reset_effect'] = game, after
            self.phase('reset_closing', world)
            return
        if phase == 'reset_closing':
            assert self.silent(fx) and fx['count'] == 1, ('Reset effect revived', state)
            if abs(link.get_editor_property('GateOffset')) < .05:
                self.check('D%d native reset closes gate to original position' % (index + 1),
                           (link.get_editor_property('Gate').get_actor_location() - u.Vector(*self.s['initial'][index]['gate'])).length() < .05)
                self.begin_push(world, index, 1)
            return
        if phase == 'replay_settle':
            assert fx['count'] == 2, ('Replay did not remain exactly once', state)
            if fx['active']:
                assert fx['age'] < .78, ('Dust outlived envelope', state)
                if fx['age'] >= .26:
                    assert abs(fx['rumble']) < 1e-8, ('Rumble outlived envelope', state)
            if elapsed < 1.1:
                return
            self.check('D%d replay settles to silent Inactive without extra effects' % (index + 1),
                       self.silent(fx) and 'INACTIVE' in reveal_phase and fx['count'] == 2, fx)
            self.check('D%d replay uses a new native reveal session' % (index + 1),
                       row['completion_session'] > self.s['cycles'][-2]['completion_session'])
            if index == 0:
                self.stage_device(world, 0)
            else:
                self.finish()
            return
        if phase == 'device_ready':
            if elapsed < .25:
                return
            n = self.s['device_index']
            director = self.live['objectives']
            self.check('D2 prerequisite device%d native TryRelease starts' % (n + 1), director.try_release(n, cat))
            self.s['device_releases'].append({'index': n, 'started_game': game, 'commit_clip_s': None})
            self.phase('device_playing', world)
            return
        if phase == 'device_playing':
            n = self.s['device_index']
            director = self.live['objectives']
            d = director.get_editor_property('Devices')[n]
            record = self.s['device_releases'][-1]
            if d.get_editor_property('bReleased') and record['commit_clip_s'] is None:
                mesh = cat.get_component_by_class(u.SkeletalMeshComponent)
                record['commit_clip_s'] = mesh.get_position() if isinstance(mesh.get_anim_instance(), u.AnimSingleNodeInstance) else -1.
                self.check('D2 prerequisite device%d physically commits after frame44' % (n + 1), record['commit_clip_s'] >= 44. / 30., record)
            if director.get_editor_property('ActiveDevice') != -1:
                return
            self.check('D2 prerequisite device%d releases and restores player' % (n + 1),
                       d.get_editor_property('bReleased') and not cat.get_component_by_class(u.CatrunBasketInteractionComponent).get_editor_property('Busy'))
            if n < 2:
                self.stage_device(world, n + 1)
            else:
                self.check('D2 native unlock comes from all three real releases', director.all_released())
                self.begin_push(world, 1, 0)

    def finish(self, error=None):
        if self.s['phase'] == 'shutdown':
            return
        try:
            after = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in self.s['hashes_before']}
            self.s['hashes_after'] = after
            self.check('Native reset/replay preserves saved maps and presentation assets', after == self.s['hashes_before'])
            if not error:
                self.check('Exactly four native completion impacts across two gates',
                           [self.effect(i)['count'] for i in range(2)] == [2, 2])
                self.check('Seven isolated clear cat staging fixtures, no per-frame relocations', len(self.s['staging']) == 7)
                if self.capture:
                    for shot in self.s['screenshots']:
                        shot['written'] = Path(shot['path']).exists() and Path(shot['path']).stat().st_size > 1024
                    self.check('At most four actual-camera GPU frames written', len(self.s['screenshots']) == 4
                               and all(s['written'] for s in self.s['screenshots']))
        except Exception:
            error = (error or '') + '\n' + traceback.format_exc()
        self.s.update(success=error is None, error=error, phase='shutdown', changed=time.monotonic())
        self.persist()
        if self.ed.get_game_world():
            self.le.editor_request_end_play()

    def tick(self, _dt):
        try:
            if self.s['phase'] == 'shutdown':
                if not self.ed.get_game_world() and time.monotonic() - self.s['changed'] > .5:
                    u.unregister_slate_post_tick_callback(self.handle)
                    u.SystemLibrary.execute_console_command(self.ed.get_editor_world(), 'QUIT_EDITOR')
                return
            assert time.monotonic() - self.s['started'] < 360., 'Reset/replay total timeout'
            world = self.ed.get_game_world()
            if world:
                self.step(world)
        except Exception:
            self.finish(traceback.format_exc())

    def start(self):
        assert '-SaveToUserDir' in self.s['command_line'], 'Use isolated root-owned launcher'
        assert not self.ed.get_game_world(), 'Do not attach to another PIE run'
        if self.capture:
            assert '-nullrhi' not in self.s['command_line'].lower(), 'GPU captures need a real renderer'
        self.handle = u.register_slate_post_tick_callback(self.tick)
        try:
            assert self.le.load_level('/Game/Maps/Stage3')
            self.le.editor_request_begin_play()
        except Exception:
            self.finish(traceback.format_exc())
        return self
