"""A8 acceptance uses exact A6/A7 native evidence and adversarial unit records."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import jsonschema
from review.axis3.verdict_data import file_ref, load_json
from tools import build_leaderboard as job

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/fixtures/leaderboard'
FILES = ('LEADERBOARD.md', 'leaderboard.csv', 'leaderboard.json')


class Leaderboard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root/'input'
        shutil.copytree(FIXTURE/'input', self.inputs)

    def write(self, path, data):
        path.write_text(json.dumps(data, sort_keys=True, indent=2)+'\n')

    def catalog(self, callback):
        path = self.inputs/'leaderboard-input.json'
        data = load_json(path)
        callback(data)
        self.write(path, data)

    def edit_evidence(self, index, callback):
        catalog = load_json(self.inputs/'leaderboard-input.json')
        record = catalog['records'][index]
        path = self.inputs/record['evidence']['path']
        data = load_json(path)
        callback(data)
        self.write(path, data)
        record['evidence'] = file_ref(self.inputs, path)
        self.write(self.inputs/'leaderboard-input.json', catalog)

    def build(self, name='out'):
        return job.build([self.inputs], self.root/name)

    def rejects(self, message=None):
        with self.assertRaises((ValueError, jsonschema.ValidationError)) as ctx:
            self.build()
        if message:
            self.assertIn(message, str(ctx.exception))
        self.assertFalse((self.root/'out').exists())

    def axis3(self, name, *, machine='synthetic-unit', requests=b'same requests', scope='cpu-in-process'):
        root = self.inputs/name
        root.mkdir()
        (root/'fixture.txt').write_bytes(b'synthetic unit protocol/corpus')
        (root/'requests.json').write_bytes(requests)
        raw = [{'request_id': i, 'status': 'PASS', 'expected_sha256': 'a'*64,
                'observed_sha256': 'a'*64, 'returned_bytes': 1024, 'elapsed_ns': 1000}
               for i in range(10000)]
        (root/'raw.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in raw))
        ref = file_ref(root, root/'fixture.txt')
        data = {'schema': 'axis3-evidence-v1', 'axis': 3, 'kind': 'synthetic',
            'run_id': 'unit-only', 'status': 'PASS', 'format': name, 'variant': 'unit',
            'scope': scope, 'threads': 1, 'n_assemblies': 4, 'window_bytes': 1024,
            'samples': 10000, 'verified': 10000, 'codec_commit': 'a'*40,
            'protocol': ref, 'runbook': ref, 'corpus_manifest': ref,
            'requests': file_ref(root, root/'requests.json'),
            'raw_logs': [file_ref(root, root/'raw.jsonl')],
            'metrics': {'stored_bytes': 400, 'bytes_per_assembly': 100,
                        'build_seconds': 1, 'peak_rss_bytes': 1000,
                        'p50_us': 1, 'p95_us': 1, 'p99_us': 1,
                        'windows_per_second': 1000000, 'Q_actual_bytes': 4096},
            'error': None, 'hardware': {'machine_id': machine, 'cpu_model': 'unit',
                                       'frequency_policy': 'unit'},
            'build': {'compiler': 'unit', 'flags': [], 'binary_sha256': 'b'*64,
                      'dependencies': {'unit': '1'}}, 'silence_gate': None}
        self.write(root/'evidence.json', data)
        record = {'evidence': file_ref(self.inputs, root/'evidence.json'), 'input_root': name}
        self.catalog(lambda c: c['records'].append(record))
        return root

    def test_exact_golden_outputs(self):
        receipt = self.build()
        self.assertEqual((receipt['tables'], receipt['rows']), (4, 4))
        for name in FILES:
            self.assertEqual((self.root/'out'/name).read_bytes(), (FIXTURE/'expected'/name).read_bytes())

    def test_repeated_build_is_byte_identical(self):
        self.build('first')
        self.build('second')
        for name in FILES:
            self.assertEqual((self.root/'first'/name).read_bytes(), (self.root/'second'/name).read_bytes())

    def test_catalog_order_does_not_change_bytes(self):
        self.build('first')
        self.catalog(lambda d: d['records'].reverse())
        self.build('second')
        for name in FILES:
            self.assertEqual((self.root/'first'/name).read_bytes(), (self.root/'second'/name).read_bytes())

    def test_relocation_does_not_change_bytes(self):
        self.build('first')
        copied = self.root/'other'/'inputs'
        shutil.copytree(self.inputs, copied)
        job.build([copied], self.root/'second')
        for name in FILES:
            self.assertEqual((self.root/'first'/name).read_bytes(), (self.root/'second'/name).read_bytes())

    def test_directory_order_does_not_change_bytes(self):
        catalog = load_json(self.inputs/'leaderboard-input.json')
        roots = []
        for i, record in enumerate(catalog['records']):
            root = self.root/('split'+str(i))
            shutil.copytree(self.inputs, root)
            self.write(root/'leaderboard-input.json', {'schema': 'leaderboard-input-v1', 'records': [record]})
            roots.append(root)
        job.build(roots, self.root/'first')
        job.build(list(reversed(roots)), self.root/'second')
        for name in FILES:
            self.assertEqual((self.root/'first'/name).read_bytes(), (self.root/'second'/name).read_bytes())

    def test_no_clock_native_decoder_or_current_paths(self):
        with mock.patch('time.time', side_effect=AssertionError('clock')), \
             mock.patch('tools.axis4.open_reader', side_effect=AssertionError('native')):
            self.build()
        for name in FILES:
            text = (self.root/'out'/name).read_text()
            self.assertNotIn(str(self.root), text)
            self.assertNotIn('/workspace/', text)
            self.assertNotIn('command', text)

    def test_every_row_has_exact_copied_evidence_sha(self):
        self.build()
        data = load_json(self.root/'out/leaderboard.json')
        for table in data['tables']:
            for row in table['rows']:
                copied = self.root/'out'/row['evidence']
                self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), row['evidence_sha256'])
        rows = list(csv.DictReader(io.StringIO((self.root/'out/leaderboard.csv').read_text())))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['evidence'] and len(r['evidence_sha256']) == 64 for r in rows))

    def test_all_values_copied_from_axis5_counts(self):
        self.build()
        rows = [r for t in load_json(self.root/'out/leaderboard.json')['tables'] for r in t['rows'] if r['axis'] == 5]
        source = load_json(self.inputs/'data/a7-run/evidence.json')
        for row in rows:
            self.assertEqual(row['status'], source['integrity'][row['hash_mode']])
            for key, value in source['counts'][row['hash_mode']].items():
                self.assertEqual(row[key], value)

    def test_synthetic_timings_not_promoted(self):
        self.build()
        rows = [r for t in load_json(self.root/'out/leaderboard.json')['tables'] for r in t['rows']]
        self.assertTrue(all('seconds' not in r and 'p50_us' not in r for r in rows))

    def test_unknown_machine_stays_singleton(self):
        self.build()
        for table in load_json(self.root/'out/leaderboard.json')['tables']:
            self.assertIsNone(table['conditions']['machine'])
            self.assertEqual(len(table['rows']), 1)

    def test_explicit_unknown_machine_comparison_refused(self):
        def change(c):
            c['records'][0]['table'] = c['records'][2]['table'] = 'forced'
        self.catalog(change)
        self.rejects('machine unrecorded')

    def test_schema_mismatch_refused(self):
        self.edit_evidence(0, lambda d: d.update(schema='axis4-evidence-v2'))
        self.rejects('schema')

    def test_axis_schema_disagreement_refused(self):
        self.edit_evidence(0, lambda d: d.update(axis=3))
        self.rejects()

    def test_axis4_verify_failure_refused(self):
        self.edit_evidence(0, lambda d: d['rows'][0].update(observed_sha256='0'*64))
        self.rejects('FASTA')

    def test_axis5_forged_classification_refused(self):
        self.edit_evidence(1, lambda d: d['rows'][1].update(classification='harmless'))
        self.rejects('classification')

    def test_fasta_mutation_refused(self):
        (self.inputs/'data/asm1.fa').write_bytes(b'>chr\nWRONG\n')
        self.rejects()

    def test_duplicate_format_variant_refused(self):
        self.catalog(lambda d: d['records'].append(copy.deepcopy(d['records'][0])))
        self.rejects('duplicate format/variant')

    def test_different_machines_refused(self):
        self.axis3('one', machine='machine-a')
        self.axis3('two', machine='machine-b')
        self.rejects('mixed conditions')

    def test_different_request_sets_refused(self):
        self.axis3('one', requests=b'set-a')
        self.axis3('two', requests=b'set-b')
        self.rejects('mixed conditions')

    def test_different_scopes_refused(self):
        self.axis3('one')
        self.axis3('two', scope='cli')
        self.rejects('mixed conditions')

    def test_comparable_axis3_records_share_table(self):
        self.axis3('one')
        self.axis3('two')
        self.build()
        table = next(t for t in load_json(self.root/'out/leaderboard.json')['tables'] if t['id'] == 'axis3')
        self.assertEqual([r['format'] for r in table['rows']], ['one', 'two'])
        self.assertTrue(all('p50_us' not in r for r in table['rows']))

    def test_axis3_raw_quantile_failure_refused(self):
        self.axis3('one')
        self.edit_evidence(3, lambda d: d['metrics'].update(p50_us=0.5))
        self.rejects('quantile')

    def test_axis3_unverified_pass_refused(self):
        self.axis3('one')
        self.edit_evidence(3, lambda d: d.update(verified=1))
        self.rejects()

    def test_wrong_evidence_anchor_refused(self):
        self.catalog(lambda d: d['records'][0]['evidence'].update(sha256='0'*64))
        self.rejects()

    def test_wrong_prepare_anchor_refused(self):
        self.catalog(lambda d: d['records'][0].update(prepared_sha256='0'*64))
        self.rejects('anchor')

    def test_missing_prepare_anchor_refused(self):
        self.catalog(lambda d: d['records'][0].pop('prepared_sha256'))
        self.rejects('external prepare')

    def test_unknown_catalog_schema_refused(self):
        self.catalog(lambda d: d.update(schema='anything'))
        self.rejects('catalog schema')

    def test_catalog_path_escape_refused(self):
        self.catalog(lambda d: d['records'][0].update(input_root='../outside'))
        self.rejects('root-relative')

    def test_symlink_escape_refused(self):
        (self.root/'foreign').mkdir()
        (self.inputs/'escape').symlink_to(self.root/'foreign', target_is_directory=True)
        self.catalog(lambda d: d['records'][0].update(input_root='escape'))
        self.rejects('symlink')

    def test_empty_input_refused(self):
        self.catalog(lambda d: d.update(records=[]))
        self.rejects('empty')

    def test_unknown_catalog_key_refused(self):
        self.catalog(lambda d: d['records'][0].update(machine_override='fake'))
        self.rejects('catalog record')

    def test_overwrite_refused(self):
        self.build()
        with self.assertRaises(FileExistsError):
            self.build()

    def test_cli(self):
        got = subprocess.run([sys.executable, '-m', 'tools.build_leaderboard', str(self.inputs),
                              '--out', str(self.root/'cli')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(json.loads(got.stdout)['rows'], 4)

    def test_number_format_preserves_small_values(self):
        self.assertEqual(job.number(0.000000000123), '0.000000000123')
        self.assertEqual(job.number(1000000000000000000), '1000000000000000000')
        self.assertEqual(job.number(-0.0), '0')

    def test_evidence_link_hash_is_full_length(self):
        self.build()
        for t in load_json(self.root/'out/leaderboard.json')['tables']:
            for row in t['rows']:
                self.assertEqual(row['evidence'], 'evidence/'+row['evidence_sha256']+'/evidence.json')

    def test_window_law_native_verifier_adapter(self):
        # Artificial-clock Axis 3 report from the existing B-job acceptance fixture.
        sys.path.insert(0, str(ROOT/'tests'))
        from test_verdict_job import complete_report
        root = self.inputs/'window'
        root.mkdir()
        complete_report(root)
        record = {'evidence': file_ref(self.inputs, root/'results.json'), 'input_root': 'window'}
        self.catalog(lambda d: d['records'].append(record))
        self.build()
        rows = [r for t in load_json(self.root/'out/leaderboard.json')['tables'] for r in t['rows'] if r['axis'] == 3]
        self.assertEqual(len(rows), 60)
        self.assertTrue(all('p50_us' not in r for r in rows))

    def test_window_law_forged_summary_refused(self):
        sys.path.insert(0, str(ROOT/'tests'))
        from test_verdict_job import complete_report
        root = self.inputs/'window'
        root.mkdir()
        complete_report(root)
        record = {'evidence': file_ref(self.inputs, root/'results.json'), 'input_root': 'window'}
        self.catalog(lambda d: d['records'].append(record))
        self.edit_evidence(3, lambda d: d['entries'][0]['observations'][0].update(measured_p50_us=12345))
        self.rejects('p50')
