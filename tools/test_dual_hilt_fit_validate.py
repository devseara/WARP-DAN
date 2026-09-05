"""Regression for fitting the same signed landmark transform that is validated."""
import math
import sys
import unittest

sys.dont_write_bytecode = True
import dual_hilt_fit_validate as model


class HiltFitSignTest(unittest.TestCase):
    def test_known_landmark_predicts_unseen_rotations_and_mirrors(self):
        # Construct exact translations independently of the implementation:
        # mirror X, rotate CCW in numeric XY, place the hilt at origin.
        # All 128 cells, including held-out rotations, must reconstruct exactly.
        cells, rows = {}, {}
        for hand, (hx, hy) in enumerate(((7.0, -19.0), (-11.0, 3.0))):
            for direction in range(8):
                for frame in range(8):
                    mirror = (direction + frame) % 2
                    angle = 19 * direction + 11 * frame
                    a = math.radians(angle)
                    mx = -hx if mirror else hx
                    rx = math.cos(a) * mx - math.sin(a) * hy
                    ry = math.sin(a) * mx + math.cos(a) * hy
                    key = direction, frame, hand
                    cells[key] = {'mirror': mirror, 'rotation_raw': angle}
                    rows[key] = {'x': -rx, 'y': -ry}
            fitted = model.fit_hand(hand, cells, rows)
            self.assertLess(fitted['calib_sse'], 1e-20)
            for direction in range(8):
                for frame in range(8):
                    key = direction, frame, hand
                    cell = cells[key]
                    rx, ry = model.transform(*fitted['hilt'], cell['mirror'],
                                             cell['rotation_raw'], fitted['conv'])
                    self.assertAlmostEqual(-rx, rows[key]['x'], places=10)
                    self.assertAlmostEqual(-ry, rows[key]['y'], places=10)


if __name__ == '__main__':
    unittest.main()
