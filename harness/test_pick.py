import unittest
from pick import select, table


class PickTests(unittest.TestCase):
    def rows(self):
        return [dict(codec='xz',g=g,status='measured',ratio=r,p50_ms=t,
                     amplification=1.23456,break_even_N=1234)
                for g,r,t in [(4096,2.,1.),(16384,3.,2.),(65536,2.,3.)]]

    def test_pareto(self):
        rows=self.rows(); select(rows)
        self.assertEqual([r['selected'] for r in rows],[True,True,False])

    def test_max_p50(self):
        rows=self.rows(); select(rows,max_p50=1.5)
        self.assertEqual([r['g'] for r in rows if r['selected']],[4096])

    def test_min_ratio(self):
        rows=self.rows(); select(rows,min_ratio=2.5)
        self.assertEqual([r['g'] for r in rows if r['selected']],[16384])

    def test_no_matching_row(self):
        for kwargs in ({'max_p50':.5},{'min_ratio':4.}):
            with self.assertRaisesRegex(ValueError,'no qualified row'):
                select(self.rows(),**kwargs)

    def test_render_preserves_raw_values(self):
        rows=self.rows(); select(rows)
        result=table(rows)
        self.assertIn('1.23 | 1.23e+03',result)
        self.assertEqual(rows[0]['amplification'],1.23456)


if __name__ == '__main__':
    unittest.main()
