"""Rejection tests at the nine-axis publication gate; no codec execution."""
import copy
import json
from pathlib import Path
import unittest

import axes
from table_cells import unavailable, validate_tables
from throughput import render_throughput


class NineAxes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(s) for s in (Path(__file__).resolve().parents[1] / 'results.jsonl').read_text().splitlines()]

    def modified(self, codec, metric):
        rows = self.rows.copy()
        i = next(i for i, r in enumerate(rows) if r['codec'] == codec and r['metric'] == metric)
        rows[i] = copy.deepcopy(rows[i])
        return rows, rows[i]

    def test_complete_retained_evidence(self):
        result = axes.audit(self.rows)
        self.assertEqual((result['axes'], result['formats'], result['curve_positions']), (9, 3, 15))

    def test_missing_curve_is_pending_not_closed(self):
        rows = [r for r in self.rows if r.get('evidence_group') != 'cg-five-point-v1']
        with self.assertRaises(ValueError):
            axes.audit(rows)
        self.assertIn('Pending:', axes.render_coverage(rows))

    def test_missing_profile_cannot_be_hidden(self):
        rows = [r for r in self.rows if not (r['codec'] == 'bgzip+htslib' and r['metric'] == 'batch_throughput' and r['access_profile'] == 'hot-set')]
        with self.assertRaises(ValueError):
            axes.audit(rows)

    def test_unsupported_batch_requires_reason(self):
        rows, row = self.modified('bgzip+htslib', 'batch_throughput')
        row['native_batch_reason'] = ''
        with self.assertRaises(ValueError):
            axes.audit(rows)

    def test_no_baseline_borrowed_from_another_machine(self):
        rows, row = self.modified('bgzip+htslib', 'region_p50')
        row['hardware']['logical_cpus'] += 1
        with self.assertRaisesRegex(ValueError, 'scope'):
            axes.audit(rows)

    def test_false_relative_pass_is_rejected(self):
        rows, row = self.modified('aceapex-interactive', 'region_p50_relative_to_bgzip')
        row['value'], row['status'] = 0.1, 'pass'
        with self.assertRaisesRegex(ValueError, 'baseline comparison'):
            axes.audit(rows)

    def test_understated_sample_variation_is_rejected(self):
        rows, row = self.modified('bgzip+htslib', 'encode_throughput_curve')
        row['sample_cv'] = 0
        with self.assertRaisesRegex(ValueError, 'CV mismatch'):
            render_throughput(rows)

    def test_fabricated_plateau_headline_is_rejected(self):
        rows, row = self.modified('bgzip+htslib', 'encode_throughput_mb_s')
        row['value'] *= 2
        with self.assertRaisesRegex(ValueError, 'headline'):
            render_throughput(rows)

    def test_plateau_receipt_must_match_underlying_scales(self):
        rows, row = self.modified('bgzip+htslib', 'encode_throughput_mb_s')
        row['plateau_evidence'][0]['sample_cv'] = 0
        with self.assertRaisesRegex(ValueError, 'evidence'):
            render_throughput(rows)

    def test_generated_report_explains_all_missing_cells(self):
        text = axes.render(self.rows)
        validate_tables(text)
        self.assertIn('n/a — no native batch API in this adapter', text)


class TableCells(unittest.TestCase):
    def test_missing_placeholders_are_rejected(self):
        for value in ('', 'n/a', '—', '-', 'n/a —', 'n/a:'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_tables('| Name | Value |\n|---|---|\n| codec | ' + value + ' |')

    def test_reason_is_in_the_cell(self):
        validate_tables('| codec | ' + unavailable('no batch API') + ' |')
        for reason in ('', 'n/a', 'n/a:', 'n/a —'):
            with self.assertRaises(ValueError):
                unavailable(reason)

    def test_code_and_escaped_pipes_are_not_cells(self):
        validate_tables('```\n| n/a |\n```\n| codec | no A\\|B decoder |')


if __name__ == '__main__':
    unittest.main()
