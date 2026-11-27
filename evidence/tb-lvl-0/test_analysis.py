# SPDX-License-Identifier: Apache-2.0
"""Invented unit fixtures only; no study corpus, native calls or measurements."""
import importlib.util
import tempfile
from fractions import Fraction
from pathlib import Path
import unittest

PATH = Path(__file__).with_name('analysis.py')
SPEC = importlib.util.spec_from_file_location('tb_lvl_analysis_tested', PATH)
a = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(a)


def row(name, size, C=10, D=10, codec='synthetic', level='0', api_level=None, original=100):
    return dict(id=name, codec=codec, level=level, api_level=api_level, input_bytes=original,
                compressed_bytes=size, C_MB_s=str(C), D_MB_s=str(D))


def full_rows():
    grid = a.canonical_grid(True)
    points = [row(c['id'], 80000000, 10, 10, c['codec'], c['level'], c['api_level'], a.INPUT_BYTES) for c in grid]
    for p in points:
        if p['codec'] == 'aceapex':
            p['compressed_bytes'] = 3 * a.INPUT_BYTES // 10
    return grid, points


class ExactAnalysisTests(unittest.TestCase):
    def selected_fixture(self, directory, bad_time=False, retaken=False):
        here = Path(directory) / 'evidence/tb-lvl-0'; here.mkdir(parents=True)
        data = a.SavedData(here)
        cfg = next(c for c in a.canonical_grid(True) if c['id'] == 'aceapex,1')
        prep = dict(identity={'invented_test_fixture': True}, binary={'path': '/owned/test-turbobench'},
                    input={'path': '/owned/input/silesia.ref.tar'})
        target = data.target(cfg, 1); identity = dict(**prep['identity'], config=cfg, round=1, kind='main')
        folder = here / 'raw/round-1' / cfg['id'] / 'attempt-1'; folder.mkdir(parents=True)
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else a.packed(value))
            return data.reference(path)
        command = ['taskset', '-c', '0', prep['binary']['path'], '-e' + cfg['id'], '-b1073741824B',
                   '-B' + str(a.INPUT_BYTES) + 'B', '-i0,0', '-C3', '-D', '-V0', '-v0', prep['input']['path']]
        req = write(folder / 'request.json', dict(schema='tb-lvl-0-request-v1', identity=identity, target=target, command=command,
                    folder=folder.as_posix(), cwd=folder.as_posix() + '/cwd'))
        stdout = write(folder / 'stdout', b'invented fixture only\n'); stderr = write(folder / 'stderr', b'')
        cells = ['silesia.ref.tar', str(a.INPUT_BYTES), '12345', '0.100000', '1.000000', 'aceapex', '1', '?', '0', '0', '0', '0', '1', '']
        raw = ('\t'.join(a.TBB_HEADER) + '\n' + '\t'.join(cells) + '\n').encode()
        native = write(folder / 'native.tbb', raw)
        receipt = write(folder / 'receipt.json', dict(schema='tb-lvl-0-receipt-v1', identity=identity, target=target, status='CLEAN',
            command_started=True, returncode=0, command=command, request_sha256=req['sha256'],
            stdout_sha256=stdout['sha256'], stderr_sha256=stderr['sha256'], tbb_sha256=native['sha256']))
        parsed = a.parse_tbb(raw, cfg)
        if bad_time:
            parsed['ctime_seconds'] = '2.000000'
        result = write(folder / 'result.json', dict(schema='tb-lvl-0-result-v1', identity=identity, config=cfg, round=1,
            **parsed, roundtrip=True, raw=native, receipt=receipt))
        attempts = [dict(attempt=1, status='CLEAN', receipt=receipt, result=result)]
        if retaken:
            (folder.parent / 'attempt-2').mkdir()
            attempts.append(dict(attempt=2, status='LOADED', receipt=receipt, result=None))
        unit = write(here / 'units/round-1' / (cfg['id'] + '.json'), dict(schema='tb-lvl-0-unit-v1', identity=identity,
            config=cfg, round=1, kind='main', status='CLEAN', attempts=attempts, selected=result))
        return data, prep, target, unit

    def test_selected_raw_coupling_and_first_clean(self):
        with tempfile.TemporaryDirectory(prefix='tb-analysis-test-') as directory:
            data, prep, target, unit = self.selected_fixture(directory)
            observed = data.selected_unit(prep, unit, target)
            self.assertEqual(observed['ctime_seconds'], '1.000000')
            self.assertEqual(observed['compressed_bytes'], 12345)
        for option in ('bad_time', 'retaken'):
            with tempfile.TemporaryDirectory(prefix='tb-analysis-test-') as directory:
                data, prep, target, unit = self.selected_fixture(directory, **{option: True})
                with self.assertRaises(ValueError):
                    data.selected_unit(prep, unit, target)

    def test_native_tbb_seconds_order_and_exact_selection(self):
        cfg = dict(id='aceapex_fast,1', codec='aceapex_fast', level='1', api_level=11)
        cells = ['silesia.ref.tar', str(a.INPUT_BYTES), '130490328', '0.123456', '1.000001', 'aceapex_fast', '1', '?', '0', '0', '0', '0', '1', '']
        def raw(values):
            return ('\t'.join(a.TBB_HEADER) + '\n' + '\t'.join(values) + '\n').encode()
        result = a.parse_tbb(raw(cells), cfg)
        self.assertEqual((result['ctime_seconds'], result['dtime_seconds']), ('1.000001', '0.123456'))
        self.assertEqual(result['compressed_bytes'], 130490328)
        for index, bad in ((0, 'other.tar'), (1, '123'), (2, '0'), (3, '0.000000'),
                           (4, '1.00000'), (5, 'aceapex'), (6, '13'), (7, ''), (13, 'ERROR')):
            changed = list(cells); changed[index] = bad
            with self.assertRaises(ValueError):
                a.parse_tbb(raw(changed), cfg)
        with self.assertRaises(ValueError):
            a.parse_tbb(raw(cells) + ('\t'.join(cells) + '\n').encode(), cfg)
        cells[5:8] = ['bsc', '0', 'e0']
        self.assertEqual(a.parse_tbb(raw(cells), dict(codec='bsc', level='0e0'))['compressed_bytes'], 130490328)

    def test_grid_and_fast_alias(self):
        self.assertEqual(len(a.canonical_grid(False)), 60)
        grid = a.canonical_grid(True)
        self.assertEqual(len(grid), 50)
        self.assertEqual([c['api_level'] for c in grid if c['codec'] == 'aceapex_fast'], list(range(11, 19)))
        self.assertIn('bsc,0e0', [c['id'] for c in grid])

    def test_source_resolution_is_not_owner_confirmation(self):
        result = a.analyze([], a.canonical_grid(True), mapping_resolved=True, owner_confirmed=False)
        self.assertTrue(result['mapping_resolved'])
        self.assertFalse(result['owner_confirmed'])
        self.assertFalse(a.math_projection(result)['owner_confirmed'])
        with self.assertRaises(ValueError):
            a.analyze([], mapping_resolved=False, owner_confirmed=True)
        with self.assertRaises(ValueError):
            a.analyze([], mapping_resolved='true')

    def test_math_projection_excludes_output_and_raw_reference_cycles(self):
        cfg = a.canonical_grid(True)[0]
        rounds = [dict(round=i, compressed_bytes=10, ctime_seconds='1.000000', dtime_seconds='2.000000', roundtrip=True, raw={'path':str(i)}) for i in (1, 2, 3)]
        summary = a.analyze([a.summarize_rounds(cfg, rounds)], a.canonical_grid(True), True)
        before = a.math_projection(summary)
        summary['integrity_status'] = 'PASS'; summary['source_bindings'] = [{'path':'irrelevant','sha256':'0'*64}]
        summary['rows'][0]['rounds'][0]['raw'] = {'path':'other-reference'}
        self.assertEqual(a.math_projection(summary), before)
        summary['rows'][0]['D_MB_s'] = '1'
        self.assertNotEqual(a.math_projection(summary), before)

    def test_round_order_is_predefined_not_speed_order(self):
        grid = [dict(id=x) for x in ('e', 'b', 'd', 'a', 'c')]
        self.assertEqual(a.execution_order(grid, 1), list('abcde'))
        self.assertEqual(a.execution_order(grid, 2), list('edcba'))
        self.assertEqual(a.execution_order(grid, 3), list('cdeab'))
        with self.assertRaises(ValueError):
            a.execution_order(grid, 0)

    def test_strict_both_not_historical_weak_front(self):
        points = [row('equal-size-faster', 20, D=30), row('target', 20, D=20),
                  row('smaller-equal-speed', 19, D=20), row('strict', 18, D=21)]
        d = a.frontier(points)
        self.assertEqual(d['target'], ['strict'])
        self.assertFalse(a.dominates(points[0], points[1]))
        self.assertFalse(a.dominates(points[2], points[1]))
        self.assertFalse(a.dominates(points[1], points[1]))

    def test_C_and_D_are_distinct_axes(self):
        target, other = row('target', 20, C=30, D=5), row('other', 19, C=20, D=6)
        self.assertTrue(a.dominates(other, target, 'D'))
        self.assertFalse(a.dominates(other, target, 'C'))

    def test_fixed_bands_edges_empty_and_overflow(self):
        points = [row('under', 499, original=10000), row('edge', 500, original=10000),
                  row('hundred', 10000, original=10000), row('expanded', 10001, original=10000)]
        self.assertEqual([a.density_band(p) for p in points], [0, 1, 19, 20])
        bands = a.density_bands(points)
        self.assertEqual(len(bands), 21)
        self.assertEqual(bands[2]['status'], 'EMPTY')
        self.assertEqual(bands[20]['configurations'], ['expanded'])

    def test_band_local_does_not_imply_global_front(self):
        points = [row('outside', 49, D=21, original=1000), row('inside', 50, D=20, original=1000)]
        band = a.density_bands(points)[1]
        self.assertEqual(band['local_front_D'], ['inside'])
        self.assertEqual(band['global_front_D_members'], [])

    def test_nearest_tie_speed_before_smaller_then_label(self):
        target = row('misa77,0', 50, D=10, codec='misa77')
        small = row('aceapex,1', 49, D=20, codec='aceapex')
        large = row('aceapex_fast,1', 51, D=21, codec='aceapex_fast')
        result = a.nearest_ace([target, small, large])[0]
        self.assertEqual(result['ACE'], large['id'])
        self.assertEqual(result['signed_byte_gap'], 1)
        self.assertEqual(result['signed_archive_gap_pp'], '1')
        self.assertEqual(result['signed_archive_gap_percent_of_misa'], '2')
        large['D_MB_s'] = '20'
        self.assertEqual(a.nearest_ace([target, small, large])[0]['ACE'], small['id'])
        same = dict(small, id='aceapex,0')
        self.assertEqual(a.nearest_ace([target, small, same])[0]['ACE'], same['id'])

    def test_nearest_size_distance_precedes_speed_and_can_be_reused(self):
        ace = row('aceapex,1', 50, D=1, codec='aceapex')
        far = row('aceapex,2', 48, D=1000, codec='aceapex')
        targets = [row('misa77,' + str(i), 50, D=2, codec='misa77', level=str(i)) for i in range(2)]
        self.assertEqual([r['ACE'] for r in a.nearest_ace(targets + [ace, far])], [ace['id'], ace['id']])

    def test_three_external_rounds_exact_medians_and_size_range(self):
        config = dict(id='synthetic,1', codec='synthetic', level='1', api_level=None)
        rounds = [dict(round=i, compressed_bytes=s, ctime_seconds=c, dtime_seconds=d, roundtrip=True)
                  for i, s, c, d in [(3, 30, '3.000000', '1.000000'), (1, 10, '1.000000', '3.000000'), (2, 20, '2.000000', '2.000000')]]
        result = a.summarize_rounds(config, rounds, 1000000)
        self.assertEqual((result['compressed_bytes'], result['size_min'], result['size_max']), (20, 10, 30))
        self.assertEqual(result['C_MB_s'], '1/2')
        self.assertEqual(result['D_MB_s'], '1/2')
        self.assertEqual([r['round'] for r in result['rounds']], [1, 2, 3])
        self.assertNotEqual(Fraction(result['C_MB_s']), (Fraction(1) + Fraction(1, 2) + Fraction(1, 3)) / 3)
        for bad in (0.123456, True, '0'):
            with self.assertRaises(ValueError):
                a.exact(bad)
        with self.assertRaises(ValueError):
            a.summarize_rounds(config, rounds[:2])

    def test_P1_named_subset_excludes_misa_and_other_ACE(self):
        grid, points = full_rows()
        misa = next(r for r in points if r['id'] == 'misa77,0')
        misa.update(compressed_bytes=1, D_MB_s='1000')
        result = a.analyze(points, grid, True)
        self.assertEqual(result['forecasts']['P1']['verdict'], 'HIT')
        self.assertEqual(len(result['forecasts']['P1']['reference_configs']), 11)
        self.assertNotIn('aceapex,1', result['global_front_D'])
        for r in points:
            if r['id'] == 'zstd,1':
                r.update(compressed_bytes=1, D_MB_s='1000')
        self.assertEqual(a.analyze(points, grid, True)['forecasts']['P1']['verdict'], 'MISS')

    def test_P1_inclusive_density_threshold_without_rounding(self):
        grid, points = full_rows()
        for r in points:
            if r['codec'] == 'aceapex':
                r['compressed_bytes'] = a.INPUT_BYTES // 10
        candidate = next(r for r in points if r['id'] == 'aceapex,1')
        candidate['compressed_bytes'] = (27 * a.INPUT_BYTES + 99) // 100
        self.assertEqual(a.analyze(points, grid, True)['forecasts']['P1']['verdict'], 'HIT')
        candidate['compressed_bytes'] -= 1
        self.assertEqual(a.analyze(points, grid, True)['forecasts']['P1']['verdict'], 'MISS')

    def test_P2_universal_six_C_witness_may_be_default_ACE(self):
        grid, points = full_rows()
        default = next(r for r in points if r['id'] == 'aceapex,1')
        default.update(compressed_bytes=1, C_MB_s='1000', D_MB_s='1')
        result = a.analyze(points, grid, True)
        self.assertEqual(result['forecasts']['P2']['verdict'], 'HIT')
        self.assertEqual(len(result['forecasts']['P2']['C_dominators_within_registered_grid']), 6)
        last = next(r for r in points if r.get('api_level') == 18)
        last.update(compressed_bytes=1, C_MB_s='1000')
        self.assertEqual(a.analyze(points, grid, True)['forecasts']['P2']['verdict'], 'MISS')

    def test_missing_grid_is_not_a_forecast_miss_and_pending_mapping(self):
        grid, points = full_rows()
        result = a.analyze(points[:-1], grid, True)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertTrue(all(v['verdict'] == 'NOT TESTED' and v['passed'] is None for v in result['forecasts'].values()))
        result = a.analyze([])
        self.assertEqual(result['status'], 'NEED MAPPING')
        self.assertIsNone(result['registered_configurations'])
        with self.assertRaises(ValueError):
            a.analyze(points)
        points[0]['api_level'] = 999
        with self.assertRaises(ValueError):
            a.analyze(points, grid, True)

    def test_pending_report_signature_empty_bands_and_no_complete_claim(self):
        text = a.render(a.analyze([]))
        self.assertEqual(text.splitlines()[0], a.SIG)
        self.assertIn('**NEED MAPPING.**', text)
        self.assertIn('PENDING INDEPENDENT AUDIT', text)
        self.assertEqual(text.count('| empty | none |'), 21)
        self.assertEqual(text.count('| NOT TESTED |'), 2)


if __name__ == '__main__':
    unittest.main()
