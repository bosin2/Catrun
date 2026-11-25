"""Basket-only native F / WASD regression; inert until root calls main().

Reuses the established strict 16 basket cases, including cloth animation sync,
blocked F state preservation and safe fallback. Only unrelated Annex traversal
is skipped. One collision-checked initial staging per independent case; never
force basket state, change interaction settings, or save packages/maps.
"""
import importlib.util
import os
from pathlib import Path


def main():
    import unreal as u
    root = Path(u.Paths.project_dir()).resolve()
    path = root / 'Scripts/Stage3/PlacementRevision20261125/runtime_qa.py'
    spec = importlib.util.spec_from_file_location('stage3_height_existing_basket_qa', path)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    suffix = os.environ.get('CATRUN_STAGE3_BASKET_HEIGHT_QA_PASS', '01')
    assert suffix.replace('_', '').isalnum()
    out = root / 'Saved/Stage3BasketHeightRevision20261125' / ('RuntimeQA' + suffix + '.json')
    assert not out.exists(), 'Preserve prior evidence; choose a fresh pass'

    class BasketOnly(base.RuntimeQA):
        def __init__(self):
            # Base constructor checks an unused output path but does not write.
            previous = os.environ.get('CATRUN_STAGE3_PLACEMENT_QA_PASS')
            os.environ['CATRUN_STAGE3_PLACEMENT_QA_PASS'] = 'BasketHeight' + suffix
            try:
                super().__init__(u)
            finally:
                if previous is None:
                    os.environ.pop('CATRUN_STAGE3_PLACEMENT_QA_PASS', None)
                else:
                    os.environ['CATRUN_STAGE3_PLACEMENT_QA_PASS'] = previous
            self.out = out
            self.report['scope'] = __doc__
            self.report['source_harness'] = str(path)
            self.report['cat_route'] = {'executed': False, 'reason': 'Basket height scope only'}
            self.report['armor_route'] = {'executed': False, 'reason': 'Basket height scope only'}
            self.report['basket_geometry_transitions'] = []

        def basket_geometry(self):
            body = self.basket.get_editor_property('ExternalBody')
            cloth = self.cloth()
            rows = {}
            for role, actor in (('basket', self.basket), ('body', body), ('cloth', cloth.get_owner())):
                center, extent = actor.get_actor_bounds(False, False)
                rows[role] = {'world': self.v(actor.get_actor_location()),
                              'transform': actor.get_actor_transform().export_text(),
                              'bounds_min': self.v(center-extent), 'bounds_max': self.v(center+extent)}
            rows['hidden_point'] = self.v(self.basket.get_hidden_location())
            rows['cloth_component_world'] = cloth.get_world_transform().export_text()
            return rows

        def sample_animation(self):
            sample = super().sample_animation()
            sample['basket_geometry'] = self.basket_geometry()
            return sample

        def step(self):
            previous = self.report['phase']
            super().step()
            if self.report['phase'] != previous and getattr(self, 'basket', None):
                self.report['basket_geometry_transitions'].append({
                    'from_phase': previous, 'to_phase': self.report['phase'],
                    'basket': self.basket.get_actor_label(), 'native_phase': self.bp(),
                    'geometry': self.basket_geometry()})
                self.persist()

        def begin_cat(self):
            assert len(self.report['basket_cases']) == 16
            self.finish()

    global RUN
    RUN = BasketOnly()
    RUN.start()
    return RUN.report
