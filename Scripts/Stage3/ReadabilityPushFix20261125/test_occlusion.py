"""CPU geometric regression for the Stage3 cutaway contract (no Unreal import).

Run: python Scripts/Stage3/ReadabilityPushFix20261125/test_occlusion.py
GPU compilation and actual material bindings must be verified separately.
"""
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1),
           (2 ** -.5, 2 ** -.5), (-2 ** -.5, 2 ** -.5),
           (2 ** -.5, -2 ** -.5), (-2 ** -.5, -2 ** -.5))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def norm(v):
    length = math.sqrt(dot(v, v))
    return tuple(x / max(length, .0001) for x in v)


def slab(origin, direction, center, extent, low=2., high=math.inf):
    """Intersect three unpadded axis intervals with the permitted ray segment."""
    intervals = [(low, high)]
    for o, d, c, e in zip(origin, direction, center, extent):
        if abs(d) < .000001:
            if not c - e <= o <= c + e:
                return False
        else:
            intervals.append(tuple(sorted(((c - e - o) / d, (c + e - o) / d))))
    enter = max(x[0] for x in intervals)
    exit_ = min(x[1] for x in intervals)
    return exit_ > low and enter <= exit_


def hit_samples(cat, camera, forward, right, up, center, extent,
                radius=24., ortho=True, active=True):
    if not active:
        return 0
    hits = 0
    for u, v in SAMPLES:
        q = tuple(cat[i] + max(radius, 0.) * (right[i] * u + up[i] * v) for i in range(3))
        to_camera = sub(camera, q)
        direction = tuple(-x for x in norm(forward)) if ortho else norm(to_camera)
        maximum = math.inf if ortho else math.sqrt(dot(to_camera, to_camera))
        hits += slab(q, direction, center, extent, high=maximum)
    return hits


def old_cutaway(cat, camera, center, extent):
    """The removed CODE, retained here only to prove the observed regression."""
    v = sub((cat[0], cat[1], cat[2] + 35.), camera)
    depth = math.sqrt(dot(v, v))
    ray = norm(v)
    along = dot(sub(center, camera), ray)
    half_depth = dot(tuple(abs(x) for x in ray), extent)
    if (center[2] + extent[2] < cat[2] - 26. or
            along - half_depth >= depth - 20. or along + half_depth <= 0.):
        return False
    return slab(camera, ray, center, tuple(x + 90. for x in extent), low=0., high=depth + 65.)


class CutawayGeometryTests(unittest.TestCase):
    def simple(self, center, extent=(5., 5., 5.), **kwargs):
        return hit_samples((0., 0., 0.), kwargs.pop('camera', (0., -500., 0.)),
                           (0., 1., 0.), (1., 0., 0.), (0., 0., 1.),
                           center, extent, **kwargs)

    def test_true_foreground_is_cut(self):
        self.assertEqual(self.simple((0., -100., 0.), (30., 5., 30.)), 9)

    def test_entirely_behind_cat_stays_opaque(self):
        for distance in (3., 25., 65., 150.):
            with self.subTest(distance=distance):
                self.assertEqual(self.simple((0., distance, 0.), (30., 1., 30.)), 0)

    def test_lateral_90cm_neighborhood_does_not_disappear(self):
        self.assertEqual(self.simple((70., -100., 0.), (5., 5., 30.)), 0)

    def test_orthographic_ray_does_not_point_to_offset_camera_origin(self):
        self.assertGreater(self.simple((0., -100., 0.), camera=(500., -500., 0.)), 0)
        self.assertEqual(self.simple((100., -100., 0.), camera=(500., -500., 0.)), 0)

    def test_orthographic_foreground_beyond_camera_plane_not_clipped(self):
        # Actual Stage3 ortho near clip is -2000, so origin distance is no cap.
        self.assertGreater(self.simple((0., -100., 0.), camera=(0., -10., 0.)), 0)

    def test_perspective_uses_actual_converging_camera_rays(self):
        self.assertGreater(self.simple((100., -100., 0.), camera=(500., -500., 0.), ortho=False), 0)
        self.assertEqual(self.simple((0., -100., 0.), camera=(500., -500., 0.), ortho=False), 0)

    def test_perspective_does_not_cut_beyond_camera(self):
        self.assertEqual(self.simple((0., -600., 0.), ortho=False), 0)

    def test_parallel_axes_and_cat_plane_epsilon(self):
        self.assertEqual(self.simple((50., -100., 0.)), 0)
        self.assertEqual(self.simple((0., 0., 0.), (30., 1., 30.)), 0)
        self.assertGreater(self.simple((0., 0., 0.), (30., 10., 30.)), 0)

    def test_silhouette_edge_hit_without_central_ray_hit(self):
        self.assertEqual(self.simple((24., -100., 0.), (1., 5., 1.), radius=0.), 0)
        self.assertGreater(self.simple((24., -100., 0.), (1., 5., 1.)), 0)

    def test_inactive_cat_never_cuts(self):
        self.assertEqual(self.simple((0., -100., 0.), active=False), 0)

    @classmethod
    def setUpClass(cls):
        cls.snapshot_path = ROOT / 'Saved/Stage3OrientationFix20261125/QA/after/snapshot.json'
        cls.view_path = ROOT / 'Saved/Stage3CameraXReverse20261125/Visual/report.json'
        if cls.snapshot_path.exists() and cls.view_path.exists():
            snapshot = json.loads(cls.snapshot_path.read_text(encoding='utf-8'))
            cls.actors = {a['label']: a for a in snapshot['actors'].values()}
            cls.view = json.loads(cls.view_path.read_text(encoding='utf-8'))['views'][0]
        else:
            cls.actors = None

    def actual_hits(self, label):
        if self.actors is None:
            self.skipTest('Actual saved Stage3 snapshot/camera fixture not present')
        pitch, yaw = map(math.radians, self.view['rotation'][:2])
        forward = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
        right = (-math.sin(yaw), math.cos(yaw), 0.)
        up = (-math.sin(pitch) * math.cos(yaw), -math.sin(pitch) * math.sin(yaw), math.cos(pitch))
        b = self.actors[label]['all_component_bounds']
        return hit_samples(self.view['cat'], self.view['camera'], forward, right, up,
                           b['center'], b['extent'])

    def test_actual_entrance_rear_wall_old_false_positive_repaired(self):
        # Original grouped bounds include the sconce; raw wall is x=0..30.
        group_center = (32.47499678001458, -100.00001851343242, 150.)
        group_extent = (32.47499678001458, 100.00001954028934, 150.)
        hits = self.actual_hits('S3_Wall_0078')
        self.assertTrue(old_cutaway(self.view['cat'], self.view['camera'], group_center, group_extent))
        self.assertEqual(hits, 0)

    def test_actual_entrance_foreground_walls_still_cut(self):
        self.assertGreater(self.actual_hits('S3_Wall_0002'), 0)
        self.assertGreater(self.actual_hits('S3_Wall_0079'), 0)

    def test_actual_partial_cat_silhouette_is_not_misclassified_as_rear(self):
        self.assertGreater(self.actual_hits('S3_Wall_0001'), 0)

    def test_actual_camera_ray_differs_from_ortho_forward(self):
        self.actual_hits('S3_Wall_0078')
        pitch, yaw = map(math.radians, self.view['rotation'][:2])
        forward = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
        old_target = tuple(self.view['cat'][i] + (35. if i == 2 else 0.) for i in range(3))
        angle = math.degrees(math.acos(dot(norm(sub(old_target, self.view['camera'])), forward)))
        self.assertAlmostEqual(angle, 5.839293237, places=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
