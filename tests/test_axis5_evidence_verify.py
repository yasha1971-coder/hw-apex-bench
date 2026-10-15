"""A7 bounded fixtures and independent adversarial judge tests, no benchmarks."""
import copy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest import mock

import jsonschema
from review.axis3.verdict_data import file_ref, load_json
from tools import axis5 as job
from tools import axis5_evidence_verify as judge


class Axis5Evidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rng = random.Random(17)
        self.truth = bytes(rng.choice(b'ACGT') for _ in range(768))
        for name, data in [('a.fa', b'>chr\n'+self.truth+b'\n'),
                           ('donor.arc', bytes(rng.randrange(256) for _ in range(780))),
                           ('a.fa.fai', b'chr\t768\t5\t768\t769\n'),
                           ('fixture.so', b'not a library'), ('build.json', b'{}')]:
            (self.root/name).write_bytes(data)
        fasta = file_ref(self.root, self.root/'a.fa')
        self.write('a4.json', {'assemblies': [{'assembly_id': 'a', 'fasta': fasta,
                                              'contigs': [{'contig_id': 'chr', 'length': 768}]}]})
        self.write('plan.json', {'schema': 'axis4-plan-v1',
            'prepared': file_ref(self.root, self.root/'a4.json'),
            'reader': {'family': 'fasta-faidx', 'variant': 'plain',
                       'library': file_ref(self.root, self.root/'fixture.so'),
                       'build_receipt': file_ref(self.root, self.root/'build.json'),
                       'archives': [{'assembly_id': 'a', 'archive': fasta,
                                     'fai': file_ref(self.root, self.root/'a.fa.fai')}]}})
        with mock.patch('tools.axis4.open_reader'):
            self.anchor = job.prepare(self.root, 'plan.json', 'donor.arc', 'prepared')
        job.corrupt(self.root, 'prepared/prepared.json', 'corrupt')
        def fake(argv, output, errors, truth_length, timeout):
            output.write_bytes(self.truth)
            errors.write_bytes(b'')
            return {'decoder_started': True, 'timed_out': False, 'returncode': 0,
                    'signal': None, 'validation': 'disabled'}
        with mock.patch.object(job, 'observe', side_effect=fake):
            job.run(self.root, 'corrupt/corrupt.json', 'run')

    def write(self, path, data):
        (self.root/path).write_text(json.dumps(data))

    def edit(self, change):
        data = load_json(self.root/'run/evidence.json')
        change(data)
        self.write('run/evidence.json', data)

    def verify(self, anchor=None):
        return judge.verify(self.root/'run/evidence.json', self.root, anchor or self.anchor['sha256'])

    def rejects(self):
        with self.assertRaises((ValueError, jsonschema.ValidationError)):
            self.verify()

    def test_complete_counts(self):
        result = self.verify()
        self.assertEqual(result['verified'], 200)
        self.assertEqual(result['counts']['on']['detected'], 100)
        self.assertEqual(result['counts']['off']['harmless'], 100)

    def test_independent_classification_and_truth(self):
        with mock.patch.object(job, 'classify', side_effect=AssertionError('runner oracle')), \
             mock.patch.object(job, 'truth_bytes', side_effect=AssertionError('runner truth')), \
             mock.patch('tools.axis4.open_reader', side_effect=AssertionError('codec')):
            self.assertEqual(self.verify()['status'], 'PASS')

    def test_forged_classification(self):
        self.edit(lambda d: d['rows'][1].update(classification='refusal'))
        self.rejects()

    def test_forged_count(self):
        self.edit(lambda d: d['counts']['off'].update(harmless=99))
        self.rejects()

    def test_forged_integrity_verdict(self):
        self.edit(lambda d: d['integrity'].update(off='FAIL'))
        self.rejects()

    def test_duplicate_case(self):
        self.edit(lambda d: d['rows'].__setitem__(3, copy.deepcopy(d['rows'][1])))
        self.rejects()

    def test_reordered_case(self):
        def change(d):
            d['rows'][0], d['rows'][1] = d['rows'][1], d['rows'][0]
        self.edit(change)
        self.rejects()

    def test_missing_case(self):
        self.edit(lambda d: d['rows'].pop())
        self.rejects()

    def test_wrong_hash_mode(self):
        self.edit(lambda d: d['rows'][1].update(hash_enabled=True))
        self.rejects()

    def test_fake_sha(self):
        self.edit(lambda d: d['rows'][1]['raw']['output'].update(sha256='0'*64))
        self.rejects()

    def test_output_byte_tamper(self):
        p = self.root/'run/000-off.output'
        p.write_bytes(b'X'*768)
        self.rejects()

    def test_output_rehashed_still_not_harmless(self):
        p = self.root/'run/000-off.output'
        p.write_bytes(b'X'*768)
        self.edit(lambda d: d['rows'][1]['raw'].update(output=file_ref(self.root, p)))
        self.rejects()

    def test_silent_output_independently_classified(self):
        p = self.root/'run/000-off.output'
        p.write_bytes(b'X'*768)
        def change(d):
            d['rows'][1]['raw']['output'] = file_ref(self.root, p)
            d['rows'][1]['classification'] = 'silent_error'
            d['counts']['off'].update(harmless=99, silent_error=1)
            d['integrity']['off'] = 'FAIL'
        self.edit(change)
        self.assertEqual(self.verify()['counts']['off']['silent_error'], 1)

    def test_fasta_tamper(self):
        p = self.root/'a.fa'
        p.write_bytes(p.read_bytes().replace(b'chr', b'CHR'))
        self.rejects()

    def test_donor_tamper(self):
        (self.root/'donor.arc').write_bytes(b'x'*780)
        self.rejects()

    def test_mutation_tamper(self):
        (self.root/'corrupt/000.archive').write_bytes(b'x'*774)
        self.rejects()

    def test_worker_archive_tamper(self):
        (self.root/'run/000-off.archive').write_bytes(b'x'*774)
        self.rejects()

    def test_worker_sidecar_tamper(self):
        (self.root/'run/000-off.archive.fai').write_bytes(b'fake index')
        self.rejects()

    def test_baseline_tamper(self):
        (self.root/'run/baseline.output').write_bytes(b'x')
        self.rejects()

    def test_prepare_external_anchor(self):
        with self.assertRaisesRegex(ValueError, 'external anchor'):
            self.verify('0'*64)

    def test_coordinate_shift_with_reanchoring_rejected(self):
        p = self.root/'prepared/prepared.json'
        data = load_json(p)
        data['queries'][0]['start0'] = 1
        p.write_text(json.dumps(data))
        self.edit(lambda d: d.update(prepared=file_ref(self.root, p)))
        with self.assertRaisesRegex(ValueError, 'coordinates'):
            self.verify(file_ref(self.root, p)['sha256'])

    def test_signal_contradiction(self):
        self.edit(lambda d: d['rows'][1]['raw'].update(signal=11))
        self.rejects()

    def test_validation_stage_contradiction(self):
        self.edit(lambda d: d['rows'][0]['raw'].update(decoder_started=True))
        self.rejects()

    def test_unknown_evidence_key(self):
        self.edit(lambda d: d.update(unfounded_claim=1))
        self.rejects()

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):
            job.corrupt(self.root, 'prepared/prepared.json', 'corrupt')

    def test_no_escape_output(self):
        with self.assertRaisesRegex(ValueError, 'root-relative'):
            job.corrupt(self.root, 'prepared/prepared.json', '../escape')


class Axis5Watchdog(unittest.TestCase):
    def test_raw_refusal(self):
        self.check('raise SystemExit(7)', 'refusal')

    def test_raw_crash(self):
        self.check('import os,signal;os.kill(os.getpid(),signal.SIGTERM)', 'crash')

    def test_raw_timeout(self):
        self.check('import time;time.sleep(60)', 'hang', timeout=0.1)

    def test_raw_silent(self):
        self.check('print("wrong")', 'silent_error')

    def test_raw_harmless(self):
        self.check('import sys;sys.stdout.buffer.write(b"ok")', 'harmless')

    def check(self, code, outcome, timeout=2):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = job.observe([sys.executable, '-c', code], root/'out', root/'err', 2, timeout)
            raw.update(output=file_ref(root, root/'out'), stderr=file_ref(root, root/'err'))
            self.assertEqual(judge.judge_raw(root, raw, b'ok', enabled=False,
                                           archive_sha='changed', original_sha='original'), outcome)

    def test_every_kind_is_deterministic_and_changed(self):
        clean = bytes(random.Random(42).randbytes(1024))
        donor = bytes(reversed(range(256)))*4
        for kind in job.KINDS:
            for i in range(job.PER_KIND):
                a = job.mutation(clean, donor, kind, i)
                self.assertEqual(a, job.mutation(clean, donor, kind, i))
                self.assertNotEqual(a[0], clean)

    def test_identical_blocks_refused(self):
        with self.assertRaisesRegex(ValueError, 'nonidentical'):
            job.mutation(b'A'*512, b'A'*512, 'swap', 0)
