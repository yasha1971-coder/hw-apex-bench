import copy
import unittest
from window_cg import E, calculate, read_rows


class WindowCurveTests(unittest.TestCase):
    def setUp(self):
        self.bases = read_rows(E/'baselines.jsonl')

    def test_complete_curve(self):
        derived, groups, paired = calculate(self.bases)
        self.assertEqual((len(derived),len(groups),len(paired)),(300,30,10))
        for r in derived:
            self.assertAlmostEqual(r['c_g'],1-r['baseline_bytes']/r['point_bytes'])

    def test_missing_baseline_rejected(self):
        with self.assertRaises(AssertionError):
            calculate(self.bases[:-1])

    def test_non_whole_baseline_rejected(self):
        self.bases[0]['granularity'] = 1048576
        with self.assertRaises(AssertionError):
            calculate(self.bases)

    def test_input_mismatch_rejected(self):
        self.bases[0]['input_sha256'] = '0'*64
        with self.assertRaises(AssertionError):
            calculate(self.bases)

    def test_literal_policy_mismatch_rejected(self):
        b = next(b for b in self.bases if b['codec']=='aceapex')
        b['geometry']['literal_chunk_bytes'] = 131072
        with self.assertRaises(AssertionError):
            calculate(self.bases)


if __name__ == '__main__':
    unittest.main()
