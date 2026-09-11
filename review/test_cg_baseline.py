import copy
import json
import os
from pathlib import Path
import unittest
from audit_cg_baseline import audit


class BaselineReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('CABENCH_CG_RESULTS', 'results.jsonl'))
        cls.rows = [json.loads(l) for l in path.read_text().splitlines() if 'cg-five-point-v1' in l]
        if len(cls.rows) != 15:
            raise ValueError('Set CABENCH_CG_RESULTS to the retained 435-row PR #16 results.jsonl')

    def changed_point_command(self, codec, before, after):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r['codec'] == codec)
        cmd = row['point']['commands'][0]
        self.assertIn(before, cmd)
        row['point']['commands'][0] = cmd.replace(before, after)
        with self.assertRaises(ValueError):
            audit(rows)

    def test_retained_data_pass(self):
        result = audit(self.rows)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual([r['baseline_physical_units'] for r in result['codecs']], [1, 2])

    def test_zstd_level_change(self):
        self.changed_point_command('zstd-seekable-cg', '4096 3', '4096 4')

    def test_ace_thread_change(self):
        self.changed_point_command('aceapex-cg-default', '--threads 8', '--threads 1')

    def test_hidden_entropy_override(self):
        self.changed_point_command('aceapex-cg-default', 'ACEAPEX_BS=4096 ', 'FSE_CHUNK=4096 ACEAPEX_BS=4096 ')

    def test_wrong_input(self):
        self.changed_point_command('zstd-seekable-cg', '/chr1.fa ', '/other.fa ')

    def test_wrong_executable(self):
        self.changed_point_command('aceapex-cg-default', '/aceapex c ', '/other c ')

    def test_wrong_granularity(self):
        self.changed_point_command('aceapex-cg-default', 'ACEAPEX_BS=4096 ', 'ACEAPEX_BS=8192 ')

    def test_one_frame_with_partial_input(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            if r['codec'] == 'zstd-seekable-cg':
                r['baseline']['geometry']['block_size_histogram'] = {'0': 1, '253935556': 1}
        with self.assertRaisesRegex(ValueError, 'complete corpus'):
            audit(rows)

    def test_two_payload_blocks(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            if r['codec'] == 'aceapex-cg-default':
                r['baseline']['geometry']['num_blocks'] = 2
        with self.assertRaisesRegex(ValueError, 'block geometry'):
            audit(rows)

    def test_seek_table_policy_change(self):
        rows = copy.deepcopy(self.rows)
        next(r for r in rows if r['codec'] == 'zstd-seekable-cg')['point']['geometry']['seek_table_checksums'] = False
        with self.assertRaisesRegex(ValueError, 'seek table policy'):
            audit(rows)

    def test_bgzf_fabricated_baseline(self):
        rows = copy.deepcopy(self.rows)
        next(r for r in rows if r['codec'] == 'bgzip-cg')['baseline'] = {}
        with self.assertRaisesRegex(ValueError, 'invented BGZF'):
            audit(rows)


if __name__ == '__main__':
    unittest.main()
