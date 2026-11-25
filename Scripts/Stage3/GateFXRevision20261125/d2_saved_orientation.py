"""Inert saved-presentation observer: never applies candidate rotations.

Reads every D1/D2 dust card's saved rotation and actual world normal, then uses
the unchanged native three-device/P2-push early-one-PNG harness. No pause,
temporary visibility change or orientation fixture is used by this observer.
"""
import importlib.util
from pathlib import Path
import unreal as u

spec = importlib.util.spec_from_file_location('s3_saved_orientation_base', Path(__file__).with_name('d2_early_gpu.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class Harness(base.Harness):
    def __init__(self, pass_name):
        super().__init__(pass_name)
        self.s.update(scope=__doc__, orientation_writes=0, test_pause_count=0,
                      visibility_writes=0, candidate_fixture_applied=False)

    def setup(self, world, cat):
        actors = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
        rows = []
        inverse_camera = (.4055797876726389, .40557978767263886, .8191520442889918)
        for label in ('S3_GateImpact_D1', 'S3_GateImpact_D2'):
            actor = actors[label]
            for i in range(8):
                card = actor.get_editor_property('Dust%02d' % i)
                rotation = card.get_editor_property('relative_rotation')
                normal = card.get_up_vector()
                xyz = [normal.x, normal.y, normal.z]
                row = {'actor': label, 'card': i,
                       'rotation': [rotation.pitch, rotation.yaw, rotation.roll],
                       'world_normal': xyz,
                       'facing_dot': sum(a*b for a,b in zip(xyz, inverse_camera)),
                       'relative_location': base.base.vec(card.get_editor_property('relative_location')),
                       'relative_scale': base.base.vec(card.get_editor_property('relative_scale3d')),
                       'material': card.get_material(0).get_path_name()}
                rows.append(row)
                self.check('%s Dust%02d loads saved camera-facing orientation' % (label, i),
                           max(abs(a-b) for a,b in zip(row['rotation'], (35., -135., 0.))) < .001
                           and row['facing_dot'] > .99999, row)
        self.s['saved_orientation_readback'] = rows
        self.check('All sixteen saved cards inspected without orientation writes', len(rows) == 16
                   and self.s['orientation_writes'] == 0)
        super().setup(world, cat)

    def shoot(self, world, name):
        actor = self.live['effects'][1]
        game = u.GameplayStatics.get_time_seconds(world)
        age = self.effect(1)['age']
        clocks = []
        for i in range(8):
            material = actor.get_editor_property('Dust%02d' % i).get_material(0)
            assert isinstance(material, u.MaterialInstanceDynamic), ('Native StartDust MID missing', i)
            start = material.get_scalar_parameter_value('StartTime')
            clocks.append({'card': i, 'material': material.get_path_name(), 'start_time': start,
                           'game_time': game, 'shader_age': game-start, 'native_impact_age': age})
            assert abs(game-start-age) < .035, ('Native/material clock mismatch', clocks[-1])
        self.s['capture_material_clocks'] = clocks
        super().shoot(world, name)

