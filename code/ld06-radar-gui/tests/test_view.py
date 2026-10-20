from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import Point
from scan import Sample
from view import contours, directional_distances, distance_text, fitted_radius


def sample(angle, distance=250):
    return Sample(Point(angle, distance, 200), 0)


class ViewTests(unittest.TestCase):
    def test_nearby_scene_fits_half_meter_despite_one_distant_outlier(self):
        points = [sample(angle, 320) for angle in range(100)] + [sample(200, 10000)]
        self.assertEqual(fitted_radius(points), 0.5)
        self.assertEqual(fitted_radius([]), 1)

    def test_contour_does_not_bridge_missing_angles_or_depth_jump(self):
        points = [sample(0), sample(1), sample(20), sample(21), sample(22, 800)]
        self.assertEqual([len(group) for group in contours(points)], [2, 2, 1])

    def test_contours_join_across_zero_without_joining_unknown_region(self):
        points = [sample(0), sample(1), sample(180), sample(359)]
        groups = contours(points)
        self.assertEqual([s.point.angle_deg for s in groups[0]], [359, 0, 1])
        self.assertEqual(len(groups[1]), 1)

    def test_direction_requires_supported_returns_and_honors_rotation(self):
        points = [sample(359), sample(0), sample(1), sample(90, 10)]
        distances = directional_distances(points)
        self.assertEqual(distances["前方"], 0.25)
        self.assertIsNone(distances["右侧"])
        rotated = directional_distances(points, 90)
        self.assertEqual(rotated["右侧"], 0.25)
        self.assertIsNone(rotated["前方"])

    def test_units_and_missing_data(self):
        self.assertEqual(distance_text(0.07), "7 cm")
        self.assertEqual(distance_text(1.25), "1.25 m")
        self.assertEqual(distance_text(None), "无回波")


if __name__ == "__main__":
    unittest.main()
