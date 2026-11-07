import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from native_execution import digest
from pick import verify_regions
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


class GlobalFrontTests(unittest.TestCase):
    def row(self, codec, ratio, latency):
        return dict(codec=codec, g=4096, status='measured', ratio=ratio, p50_ms=latency)

    def test_cross_codec_domination(self):
        rows=[self.row('a',2,1),self.row('b',3,1)]
        select(rows)
        self.assertEqual([r['on_front'] for r in rows],[False,True])
        self.assertEqual(rows[0]['dominated_by'],[1])
        self.assertEqual(rows[1]['dominated_by'],[])

    def test_equal_rows_both_on_front(self):
        rows=[self.row('a',2,1),self.row('b',2,1)]
        select(rows)
        self.assertTrue(all(r['on_front'] and r['selected'] for r in rows))

    def test_na_excluded(self):
        rows=[dict(codec='a',g=4096,status='n/a'),self.row('b',2,1)]
        select(rows)
        self.assertFalse(rows[0]['on_front'])
        self.assertEqual(rows[0]['dominated_by'],[])
        self.assertIsNone(rows[0]['p99_ms'])
        self.assertTrue(rows[1]['on_front'])

    def test_single_row_and_p99(self):
        rows=[self.row('a',2,1)]
        rows[0]['evidence']={'region':{'region_p99_ms':1.5}}
        select(rows)
        self.assertTrue(rows[0]['on_front'])
        self.assertEqual(rows[0]['p99_ms'],1.5)

    def test_constraint_selection_still_per_codec(self):
        rows=[self.row('a',2,1),self.row('b',3,1)]
        for kwargs in ({'max_p50':2},{'min_ratio':1}):
            select(rows,**kwargs)
            self.assertTrue(all(r['selected'] for r in rows))
            self.assertFalse(rows[0]['on_front'])

    def test_pr78_fixed_fronts(self):
        import json
        common={('bgzip',65280),('zstd_seekable',4096),
                ('zstd_seekable',16384),('zstd_seekable',65536),('xz',65536)}
        expected={'enwik8':common,'silesia.tar':common|{('xz',16384)},
                  't2t_chr1.fa':common|{('xz',16384)}}
        root=Path(__file__).resolve().parents[1]/'evidence/hwab-pick-2-20261105'
        for corpus, wanted in expected.items():
            with self.subTest(corpus=corpus):
                rows=json.loads((root/corpus/'pick.json').read_text())['rows']
                select(rows)
                actual={(r['codec'],r['g']) for r in rows if r['selected']}
                self.assertEqual(actual,wanted)
                print('FIXED_FRONT',corpus,sorted(actual))


class IntegrityTests(unittest.TestCase):
    def test_mutation_and_removal_refused_before_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'archive'; p.write_bytes(b'abcdef')
            state = {'archive': p, 'artifacts': {str(p): {'bytes': 6, 'sha256': digest(p)}}}
            with patch('pick.Context') as decoder:
                p.write_bytes(b'abcdeg')
                with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                    verify_regions(state, p, [])
                p.unlink()
                with self.assertRaises(OSError):
                    verify_regions(state, p, [])
                decoder.assert_not_called()

    def test_wrong_answer_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'input'; p.write_bytes(b'abcdef')
            state = dict(archive=p, library='unused', sidecar='',
                         artifacts={str(p): {'bytes': 6, 'sha256': digest(p)}})
            with patch('pick.Context') as decoder:
                decoder.return_value.size = 6
                decoder.return_value.region.return_value = (3, b'bad')
                with self.assertRaisesRegex(ValueError, 'region SHA mismatch'):
                    verify_regions(state, p, [{'byte_offset': 0, 'requested_bytes': 3}])
                decoder.return_value.close.assert_called_once()


class GridTests(unittest.TestCase):
    def test_parse_units_and_order(self):
        from pick import parse_g
        self.assertEqual(parse_g('64K,256K,1M,2M,4M,8M,16M'),
                         [65536,262144,1048576,2097152,4194304,8388608,16777216])
        self.assertEqual(parse_g('17,1M,64K'), [17,1048576,65536])

    def test_invalid_grid_before_any_work(self):
        import contextlib, io
        from pick import main
        for value in ('', '0', '-1', '0K', '1k', '1KiB', '1.5M', '1K,',
                      '1,,2', '1K,1024', '1M,1024K', '1025M', '1073741825'):
            with self.subTest(value=value), patch('sys.argv', ['pick', 'unused', '--g='+value]), \
                 patch('pick.execute') as execute, patch('pick.digest') as digest_source, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as exc:
                    main()
                self.assertNotEqual(exc.exception.code, 0)
                self.assertIn('--g', err.getvalue())
                execute.assert_not_called(); digest_source.assert_not_called()

    def test_default_and_bgzf_once(self):
        from pick import DEFAULT_G, codec_grid, parse_g
        self.assertEqual(DEFAULT_G, (4096,16384,65536))
        for grid in (DEFAULT_G, parse_g('64K,1M,16M'), parse_g('65280,1')):
            pairs=[(c,g) for c in ('bgzip','zstd_seekable','xz') for g in codec_grid(c,grid)]
            self.assertEqual([x for x in pairs if x[0]=='bgzip'], [('bgzip',65280)])
            self.assertEqual(len(pairs), 1+2*len(grid))

    def test_adapter_limit_boundary(self):
        from pick import parse_g, MAX_G
        self.assertEqual(parse_g(str(MAX_G)), [MAX_G])
        self.assertEqual(parse_g('1'), [1])

    def test_labels_do_not_round_bytes_or_mislabel_non_bgzf(self):
        rows=[dict(codec=c,g=g,status='n/a') for c,g in [('bgzip',65280),('xz',65280),('xz',17)]]
        rendered=table(rows)
        self.assertEqual(rendered.count('fixed, not matched to g'),1)
        self.assertIn('| xz | 65280 B |',rendered)
        self.assertIn('| xz | 17 B |',rendered)

    def test_historical_fields_and_fronts_preserved(self):
        import copy, json
        from pick import DEFAULT_G, codec_grid
        root=Path(__file__).resolve().parents[1]/'evidence'
        paths=[root/'hwab-pick-2-20261105'/c/'pick.json' for c in ('enwik8','silesia.tar','t2t_chr1.fa')]
        paths += [root/'hwab-pick-3-20261106'/p/'t2t_chrX.fa/pick.json' for p in ('','attempt1-invalid')]
        common={('bgzip',65280),('zstd_seekable',4096),('zstd_seekable',16384),('zstd_seekable',65536),('xz',65536)}
        for path in paths:
            with self.subTest(path=path):
                original=json.loads(path.read_text())['rows']
                select(original)
                by_pair={(r['codec'],r['g']):r for r in original if r['status']=='measured'}
                rows=[copy.deepcopy(by_pair[c,g]) for c in ('bgzip','zstd_seekable','xz') for g in codec_grid(c,DEFAULT_G)]
                before=json.dumps([{k:v for k,v in r.items() if k not in ('selected','on_front','dominated_by')} for r in rows],sort_keys=True)
                select(rows)
                after=json.dumps([{k:v for k,v in r.items() if k not in ('selected','on_front','dominated_by')} for r in rows],sort_keys=True)
                self.assertEqual(before,after)
                self.assertEqual(len(rows),7)
                expected=common if path.parent.name=='enwik8' else common|{('xz',16384)}
                self.assertEqual({(r['codec'],r['g']) for r in rows if r['on_front']},expected)
                for row in rows:
                    for i in row['dominated_by']:
                        self.assertGreaterEqual(rows[i]['ratio'],row['ratio'])
                        self.assertLessEqual(rows[i]['p50_ms'],row['p50_ms'])


if __name__ == '__main__':
    unittest.main()
