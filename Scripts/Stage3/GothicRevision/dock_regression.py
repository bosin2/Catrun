"""PIE-only transient dock fixtures; root executes, no editor/map writes.

Use DockRegression(world, check_callback).step() once per Slate callback after
both native puzzles completed and E1/E2/E3 released. Returns True when finished.
Fixtures teleport each weight near its plate, then use native TryPushStatue and
ResetStatue. No writes to bPressed/bCompleted or manual presentation tick calls.
Already-completed restoration means a newly spawned presenter attaches to an
already solved live puzzle. Current native code does not restore solved puzzles
from disk checkpoints; this test must not be described as proving that behavior.
"""
import importlib.util
import json
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GothicRevision20261125/Regression/dock_report.json'


class DockRegression:
    def __init__(self, world, check_callback=None, report_path=None):
        import unreal as u
        self.u, self.world, self.external_check = u, world, check_callback
        self.out = Path(report_path) if report_path else OUT
        if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() != world:
            raise RuntimeError('DockRegression requires the active PIE world')
        self.gs = u.GameplayStatics
        self.lookup = {a.get_actor_label(): a for a in self.gs.get_all_actors_of_class(world, u.Actor)}
        puzzles = [a for a in self.lookup.values() if isinstance(a, u.CatrunStatuePuzzle)]
        if len(puzzles) != 1: raise RuntimeError('Expected one live puzzle director')
        self.puzzle = puzzles[0]
        self.cat = self.gs.get_player_character(world, 0)
        self.cat_position = self.cat.get_actor_location()
        self.presentation = json.loads((ROOT / 'Saved/Stage3GothicRevision20261125/presentation_report.json').read_text(encoding='utf8'))
        self.reveal = self.puzzle.get_editor_property('Reveal')
        self.reveal_enabled = self.reveal.get_editor_property('bEnabled')
        self.reveal.cancel_reveal()
        self.reveal.set_editor_property('bEnabled', False)
        self.fresh = None
        self.disabled_presenter = None
        self.done = False
        self.n, self.cycle = 1, 0
        self.last_game = None
        self.started = time.monotonic()
        self.report = {'success': False, 'checks': [], 'samples': [], 'scope': __doc__,
                       'native_methods': ['TryPushStatue', 'ResetStatue', 'IsPuzzleSeated'],
                       'fixture_changes': ['NPCs were disabled by enclosing native suite',
                           'Near-plate weight teleport, then native pushes', 'Reveal disabled transiently',
                           'Fresh cosmetic presenter spawned in PIE for restored-state query'],
                       'disk_checkpoint_restore_tested': False, 'map_saved': False}
        self.baseline = {}
        for n in (1, 2):
            row = self._row(n)
            self.check('Dock%d initially native completed' % n, row.get_editor_property('bCompleted'))
            self.baseline[n] = {'fixed': {label: self.lookup[label].get_actor_transform().export_text() for label in (
                'S3_GothicVisual_Dock%d_DockArch' % n, 'S3_GothicVisual_FloorFrame%d' % n,
                'S3_GothicVisual_Dock%d_DockSheave' % n)},
                'extents': {part: self.xyz(row.get_editor_property(part).get_actor_bounds(False)[1])
                            for part in ('Statue', 'Plate', 'Gate')}}
        self._reset('initial_open')

    @staticmethod
    def xyz(v): return [v.x, v.y, v.z]

    def persist(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(json.dumps(self.report, indent=2), encoding='utf8')

    def check(self, name, passed, detail=None):
        self.report['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        self.persist()
        if self.external_check: self.external_check(name, passed, detail)
        if not passed: raise AssertionError((name, detail))

    def _row(self, n=None):
        ident = 'S3_P%d' % (n or self.n)
        return next(row for row in self.puzzle.get_editor_property('Links') if str(row.get_editor_property('PuzzleId')) == ident)

    def _presenter(self):
        return self.lookup[self.presentation['instances'][self.n - 1]['actor']]

    def _phase(self, name):
        self.phase, self.phase_started = name, self.gs.get_time_seconds(self.world)
        self.report['phase'], self.report['dock'] = name, self.n
        self.persist()

    def _move_cat(self, x, y):
        u = self.u
        movement = self.cat.get_component_by_class(u.CharacterMovementComponent)
        movement.stop_movement_immediately()
        z = self.cat.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height() + .25
        self.cat.set_actor_location(u.Vector(x, y, z), False, True)
        movement.set_movement_mode(u.MovementMode.MOVE_WALKING)

    def _reset(self, next_phase):
        self._move_cat(0, 100)
        before = self._row().get_editor_property('Revision')
        ok = self.puzzle.reset_statue(self.u.Name('S3_P%d' % self.n))
        self.check('Dock%d native reset %s' % (self.n, next_phase), ok)
        self.check('Dock%d reset clears authoritative seat' % self.n,
                   not self.puzzle.is_puzzle_seated(self.u.Name('S3_P%d' % self.n)))
        self.check('Dock%d reset advances native revision' % self.n, self._row().get_editor_property('Revision') > before)
        self._phase(next_phase)

    def _prepare_push(self, next_phase):
        row = self._row(); statue, plate = [row.get_editor_property(k) for k in ('Statue', 'Plate')]
        p = plate.get_actor_location(); z = statue.get_actor_location().z
        statue.set_actor_location(self.u.Vector(p.x, p.y - 32, z), False, True)
        self._move_cat(p.x, p.y - 117)
        self.check('Dock%d near-plate fixture remains unseated' % self.n,
                   not self.puzzle.is_puzzle_seated(self.u.Name('S3_P%d' % self.n)))
        self._phase(next_phase)

    def _push(self):
        row = self._row()
        if self.puzzle.is_puzzle_seated(self.u.Name('S3_P%d' % self.n)): return
        statue = row.get_editor_property('Statue'); p = statue.get_actor_location()
        self._move_cat(p.x, p.y - 85)
        links = self.puzzle.get_editor_property('Links')
        index = next(i for i, link in enumerate(links) if str(link.get_editor_property('PuzzleId')) == 'S3_P%d' % self.n)
        dt = min(.05, max(.001, self.gs.get_world_delta_seconds(self.world)))
        self.puzzle.try_push_statue(index, self.cat, self.u.Vector(0, 1, 0), dt)

    def _endpoint(self, closed, tag, presenter=None):
        u = self.u; expected = self.presentation['instances'][self.n - 1]
        presenter = presenter or self._presenter()
        state = 'Closed' if closed else 'Open'
        alpha = presenter.get_editor_property('Alpha')
        self.check('Dock%d %s alpha endpoint' % (self.n, tag), abs(alpha - int(closed)) < .001, alpha)
        self.check('Dock%d %s native seat matches' % (self.n, tag),
                   self.puzzle.is_puzzle_seated(u.Name('S3_P%d' % self.n)) == closed)
        sample = {'dock': self.n, 'phase': tag, 'alpha': alpha, 'positions': {}, 'chain': None}
        for part in ('Fork', 'Pin', 'ChainTerminal'):
            actor = self.lookup[expected['references'][part]]
            actual = actor.get_actor_location(); target = u.Vector(*expected['poses'][part + state])
            error = (actual - target).length()
            self.check('Dock%d %s %s endpoint' % (self.n, tag, part), error < .05, {'error_cm': error})
            self.check('Dock%d %s %s NoCollision' % (self.n, tag, part),
                       actor.static_mesh_component.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION)
            sample['positions'][part] = self.xyz(actual)
        chain = self.lookup[expected['references']['OpenChain']].static_mesh_component
        mesh = 'SM_S3_DockShortChain' if closed else 'SM_S3_DockShortChain_OpenPose'
        self.check('Dock%d %s exact chain state' % (self.n, tag), chain.static_mesh.get_name() == mesh)
        self.check('Dock%d %s chain remains visible' % (self.n, tag), chain.is_visible() and not chain.get_editor_property('hidden_in_game'))
        visible_chains = [a.get_actor_label() for label, a in self.lookup.items()
            if label.startswith('S3_GothicVisual_Dock%d_DockShortChain' % self.n)
            and a.static_mesh_component.is_visible() and not a.static_mesh_component.get_editor_property('hidden_in_game')]
        self.check('Dock%d %s exactly one visible chain pose' % (self.n, tag), len(visible_chains) == 1, visible_chains)
        sample['chain'] = chain.static_mesh.get_path_name()
        for label, transform in self.baseline[self.n]['fixed'].items():
            self.check('Dock%d %s fixed %s' % (self.n, tag, label), self.lookup[label].get_actor_transform().export_text() == transform)
        row = self._row()
        for part, extent in self.baseline[self.n]['extents'].items():
            now = self.xyz(row.get_editor_property(part).get_actor_bounds(False)[1])
            self.check('Dock%d %s native %s bounds preserved' % (self.n, tag, part),
                       max(abs(a - b) for a, b in zip(now, extent)) < .01)
        frame_z = self.lookup['S3_Plate%d_Frame' % self.n].get_actor_location().z
        travel = self.puzzle.get_editor_property('Settings').get_editor_property('PlateTravel')
        actual_z = row.get_editor_property('Plate').get_actor_location().z
        self.check('Dock%d %s plate native travel exactly once' % (self.n, tag),
                   abs(actual_z - (frame_z - travel * int(closed))) < .01, actual_z)
        self.report['samples'].append(sample); self.persist()

    def _spawn_restored_presenter(self):
        u = self.u
        # Both spawn helpers are BlueprintInternalUseOnly and consequently have
        # no normal Python wrapper in this UE5.8 build. Invoke their reflected
        # UFunctions on the GameplayStatics CDO with every native argument.
        spawning = u.load_object(None, '/Script/Engine.Default__GameplayStatics')
        if not spawning: raise RuntimeError('GameplayStatics CDO unavailable')
        scale_method = u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        old = self._presenter(); old.set_actor_tick_enabled(False)
        self.disabled_presenter = old
        expected = self.presentation['instances'][self.n - 1]
        for part in ('Fork', 'Pin', 'ChainTerminal'):
            self.lookup[expected['references'][part]].set_actor_location(u.Vector(*expected['poses'][part + 'Open']), False, True)
        old.get_editor_property('ChainComponent').set_static_mesh(old.get_editor_property('OpenMesh'))
        transform = u.Transform(location=u.Vector(0, 0, 0))
        fresh = spawning.call_method('BeginDeferredActorSpawnFromClass', args=(
            self.world, old.get_class(), transform,
            u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale_method))
        if not fresh: raise RuntimeError('Cannot spawn PIE restoration presenter')
        self.fresh = fresh
        fields = ['Director', 'PuzzleId', 'Fork', 'Pin', 'ChainTerminal', 'OpenChain', 'ChainComponent',
                  'OpenMesh', 'ClosedMesh', 'MoveSpeed', 'ForkOpen', 'ForkClosed', 'PinOpen', 'PinLowered',
                  'PinClosed', 'ChainTerminalOpen', 'ChainTerminalClosed']
        for name in fields: fresh.set_editor_property(name, old.get_editor_property(name))
        finished = spawning.call_method('FinishSpawningActor', args=(fresh, transform, scale_method))
        if finished != fresh: raise RuntimeError('Deferred presenter finish returned a different actor')
        self.check('Dock%d restoration fixture native solve unchanged' % self.n,
                   self._row().get_editor_property('bCompleted') and self.puzzle.is_puzzle_seated(u.Name('S3_P%d' % self.n)))
        self._phase('restore_first_tick')

    def cleanup(self):
        if self.fresh:
            self.fresh.destroy_actor(); self.fresh = None
        if self.disabled_presenter:
            self.disabled_presenter.set_actor_tick_enabled(True); self.disabled_presenter = None
        self.reveal.set_editor_property('bEnabled', self.reveal_enabled)
        self.cat.set_actor_location(self.cat_position, False, True)

    def step(self):
        if self.done: return True
        try:
            game = self.gs.get_time_seconds(self.world)
            if game == self.last_game: return False
            self.last_game = game
            if time.monotonic() - self.started > 180: raise RuntimeError('Dock regression total timeout')
            if game - self.phase_started > 25: raise RuntimeError('Dock regression phase timeout: ' + self.phase)
            alpha = self._presenter().get_editor_property('Alpha')
            seated = self.puzzle.is_puzzle_seated(self.u.Name('S3_P%d' % self.n))
            if self.phase in ('initial_open', 'mid_reset_open', 'cycle_reset_open'):
                if game - self.phase_started < .8 or abs(alpha) > .001: return False
                self._endpoint(False, self.phase)
                self._prepare_push('seek_mid' if self.phase == 'initial_open' else 'seek_closed')
            elif self.phase == 'seek_mid':
                self._push()
                if seated and .12 <= alpha <= .85:
                    self.report['samples'].append({'dock': self.n, 'phase': 'mid_transition_before_reset', 'alpha': alpha})
                    self.check('Dock%d reset samples an actual partial transition' % self.n, 0 < alpha < 1, alpha)
                    self._reset('mid_reset_open')
                elif seated and alpha > .85:
                    raise RuntimeError('Missed partial transition; cannot claim midpoint reset was tested')
            elif self.phase == 'seek_closed':
                self._push()
                if seated and alpha > .999 and self._row().get_editor_property('bCompleted'):
                    self.cycle += 1
                    self._endpoint(True, 'reseat_cycle%d' % self.cycle)
                    if self.cycle < 2: self._reset('cycle_reset_open')
                    else: self._spawn_restored_presenter()
            elif self.phase == 'restore_first_tick':
                # This callback runs after the new actor's real runtime tick, not
                # by calling its cosmetic function manually from Python.
                if not self.fresh.get_editor_property('Initialized'): return False
                self._endpoint(True, 'fresh_presenter_already_completed', self.fresh)
                self.fresh.destroy_actor(); self.fresh = None
                self.disabled_presenter.set_actor_tick_enabled(True); self.disabled_presenter = None
                if self.n == 1:
                    self.n, self.cycle = 2, 0
                    self._reset('initial_open')
                else:
                    self.done = True; self.report['success'] = True
                    self.report['phase'] = 'complete'; self.report['completed_docks'] = [1, 2]
                    self.cleanup(); self.persist(); return True
            return False
        except Exception:
            self.report['error'] = traceback.format_exc(); self.report['success'] = False
            self.cleanup(); self.persist(); raise


def run_with_native_suite(output_dir=None):
    """Explicit separate-run entry point; starts PIE using the unchanged suite.

    Requires an isolated editor command line with -SaveToUserDir, as the existing
    suite already requires. Do not invoke while another PIE/test is running.
    Loads regression.py unchanged, adds dock fixtures before final-gate traversal,
    then resumes the existing final-exit and editor-shutdown checks. It never
    saves a map. Set output_dir to a new directory to preserve previous reports.
    """
    import unreal as u
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if editor.get_game_world(): raise RuntimeError('Finish existing PIE before starting the extended suite')
    if '-SaveToUserDir' not in u.SystemLibrary.get_command_line():
        raise RuntimeError('Run in isolated -SaveToUserDir editor; native suite intentionally exits that editor')
    run_dir = Path(output_dir) if output_dir else ROOT / 'Saved/Stage3GothicRevision20261125/RegressionDock' / time.strftime('%Y%m%d-%H%M%S')
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError('Refusing to overwrite a prior test run: ' + str(run_dir))
    run_dir.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('gothic_regression_for_dock', ROOT / 'Scripts/Stage3/GothicRevision/regression.py')
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    test = suite.test
    test.OUT = run_dir
    test.S['dock_extension'] = {'scope': __doc__, 'report': str(run_dir / 'dock_report.json'),
                                'disk_checkpoint_restore_tested': False}
    test.persist()
    previous_step, previous_finish = test.step, test.finish
    state = {'runner': None, 'done': False}

    def extended_step(world):
        if test.S['phase'] == 'final_gate' and not state['done']:
            # Both native puzzles and all release devices have completed here.
            # Extend the suite in memory only; never rewrite regression.py.
            if state['runner'] is None:
                state['runner'] = DockRegression(world, test.check, run_dir / 'dock_report.json')
            state['done'] = state['runner'].step()
            test.S['changed'] = time.monotonic()
            if state['done']:
                test.S['dock_extension']['passed'] = True
                test.persist()
            return
        previous_step(world)

    def extended_finish(error=None):
        runner = state['runner']
        if runner and not runner.done:
            runner.report['success'] = False
            runner.report.setdefault('error', error or 'Enclosing suite ended before dock fixtures completed')
            runner.cleanup(); runner.persist()
        if not error and not state['done']:
            error = 'Extended dock tests never reached completion'
        previous_finish(error)

    test.step, test.finish = extended_step, extended_finish
    # Keep the imported module/callback state alive until native editor shutdown.
    globals()['_active_extended_suite'] = {'suite': suite, 'state': state}
    return {'started': True, 'output_dir': str(run_dir), 'editor_will_exit_on_completion': True,
            'map_saved': False, 'tests_completed': False}


if __name__ == '__main__':
    print(json.dumps(run_with_native_suite(), indent=2))
