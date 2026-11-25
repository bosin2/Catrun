"""Inert PIE-only D2 orientation candidate using native paused on/off comparison.

Only eight D2 card rotations change in PIE memory. Production remains untouched.
Each native StartDust MID StartTime is measured against the paused game clock.
"""
import importlib.util
from pathlib import Path
import unreal as u


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load('s3_orientation_compare', 'd2_visibility_compare.py')
rotation = load('s3_rotation_candidate', 'card_rotation_candidate.py')


class Harness(compare.Harness):
    def __init__(self, pass_name):
        super().__init__(pass_name)
        self.s.update(scope=__doc__, candidate='PIE D2 card rotation only: pitch35 yaw-135 roll0')

    def setup(self, world, cat):
        self.s['rotation_candidate'] = rotation.apply(world, ('S3_GateImpact_D2',))
        super().setup(world, cat)

    def fixed_state(self, world):
        row = super().fixed_state(world)
        actor = self.live['effects'][1]
        values = []
        for i in range(8):
            card = actor.get_editor_property('Dust%02d' % i)
            material = card.get_material(0)
            assert isinstance(material, u.MaterialInstanceDynamic), ('Native StartDust must supply an actual MID', i, material)
            start = material.get_scalar_parameter_value('StartTime')
            shader_age = row['game'] - start
            assert abs(shader_age-row['fx']['age']) < .035, ('Material/native age mismatch', i, start, shader_age, row['fx']['age'])
            values.append({'card': i, 'material': material.get_path_name(), 'start_time': start,
                           'game_time': row['game'], 'shader_age': shader_age,
                           'native_impact_age': row['fx']['age']})
        row['native_material_clocks'] = values
        return row

