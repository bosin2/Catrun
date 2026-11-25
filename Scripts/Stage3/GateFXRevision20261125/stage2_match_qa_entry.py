"""Root isolated saved-material QA; no temporary material/rotation/timing edits."""
import importlib.util
import os
from pathlib import Path
import unreal as u


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


saved = load('s3_stage2_match_saved_base', 'd2_saved_orientation.py')
match = load('s3_stage2_match_definition', 'stage2_dust_match.py')


class Harness(saved.Harness):
    def __init__(self, pass_name):
        super().__init__(pass_name)
        self.s.update(scope=__doc__, material_writes=0,
                      capture_window='First native impact sample at age >= .15 and < .26; unchanged game speed/timing')
        self.s['hashes_before'][str(match.package_file(match.SOURCE))] = match.sha(match.package_file(match.SOURCE))
        self.check('Finished Stage2 source SHA retained', self.s['hashes_before'][str(match.package_file(match.SOURCE))] == match.SOURCE_SHA)

    def setup(self, world, cat):
        actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
        rows = []
        expected = match.TARGET + '.M_Stage3GateDust'
        for label in match.LABELS:
            for i in range(8):
                path = actors[label].get_editor_property('Dust%02d' % i).get_material(0).get_path_name()
                rows.append({'actor': label, 'card': i, 'material': path})
                self.check('%s Dust%02d loads saved Stage3 dust copy' % (label, i), path == expected, path)
        self.s['saved_material_readback'] = rows
        super().setup(world, cat)

    def step(self, world):
        # Only delay observer sampling. This does not change native effect age,
        # camera return, game time, material opacity or simulation speed.
        if self.s['phase'] == 'focused_impact' and not self.s['screenshots']:
            fx = self.effect(1)
            assert fx['active'] and fx['count'] == 1 and fx['age'] < .26, ('Native .15-.26 capture window missed', fx)
            if fx['age'] < .15:
                return
        super().step(world)

    def shoot(self, world, name):
        fx = self.effect(1)
        self.check('Cloud expansion captured within native .15-.26s impact window', .15 <= fx['age'] < .26, fx)
        super().shoot(world, name)


HARNESS = Harness(os.environ.get('CATRUN_GATE_FX_MATCH_PASS', 'Stage2DustMatchQA01')).start()
