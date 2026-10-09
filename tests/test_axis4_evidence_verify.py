"""A6 adversarial evidence tests. All timings/readers here are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import jsonschema

from tools import axis4 as job
from tools import axis4_evidence_verify as verifier
from review.axis3.native_readers import RawFastaReader
from review.axis3.verdict_data import file_ref, load_json
from tools.silence_contract import judge


class TestAxis4Verify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.make_inputs()
        self.prepared = job.prepare(self.root, 'cohort.json', 'groups.json', 'prepared')
        self.plan = {
            'schema': 'axis4-plan-v1', 'prepared': self.prepared,
            'reader': {'family': 'synthetic-unit-fixture', 'variant': 'unit',
                       'library': file_ref(self.root, self.root / 'fixture.so'),
                       'build_receipt': file_ref(self.root, self.root / 'build.json'),
                       'archives': [{'assembly_id': a, 'archive': file_ref(self.root, self.root / (a + '.fa'))}
                                    for a in ('a', 'b')]}}
        self.write('plan.json', self.plan)

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data))

    def make_inputs(self):
        assemblies = []
        for a in ('a', 'b'):
            seq = ('acgtNRYC' if a == 'a' else 'TGCAANnn') * 30
            # Two contigs, CRLF, short final line and no terminal newline.
            content = ('>chr comment\r\n' + '\r\n'.join(seq[i:i+17] for i in range(0,len(seq),17))
                       + '\r\n>tail\r\nACGTNRYS').encode()
            p = self.root / (a + '.fa')
            p.write_bytes(content)
            assemblies.append({'assembly_id':a, 'source_url':'synthetic:unit-'+a,
                               'fasta':file_ref(self.root,p)})
        self.write('cohort.json', {'schema':'axis4-corpus-v1','evidence_kind':'synthetic','assemblies':assemblies})
        self.groups = [{a:{'assembly_id':a,'contig_id':'chr','start0':i*3,'end0':i*3+31}
                        for a in ('a','b')} for i in range(20)]
        self.groups[-1] = {a:{'assembly_id':a,'contig_id':'tail','start0':0,'end0':8} for a in ('a','b')}
        self.write('groups.json', self.groups)
        (self.root / 'fixture.so').write_bytes(b'unit fixture only, never dlopen')
        self.write('build.json', {'kind':'synthetic-unit-fixture'})

    def reader(self, *args):
        r = RawFastaReader({a:self.root/(a+'.fa') for a in ('a','b')})
        r.build = {'kind':'synthetic-unit-fixture'}
        r.close = lambda: None
        return r

    def run_fixture(self, **kwargs):
        with mock.patch.object(job, 'open_reader', side_effect=self.reader):
            data = job.run(self.root, 'plan.json', 'run', **kwargs)
        self.assertEqual(data['status'], 'PASS', data.get('error'))
        return data

    def check(self):
        return verifier.verify(self.root/'run/evidence.json', self.root, self.prepared['sha256'])

    def mutate(self, callback):
        path = self.root/'run/evidence.json'
        data = load_json(path)
        callback(data)
        path.write_text(json.dumps(data))

    def rejects(self):
        with self.assertRaises((ValueError, jsonschema.ValidationError)):
            self.check()

    def test_good_all_hashes_and_32_bytes(self):
        data = self.run_fixture()
        self.assertEqual(self.check()['verified'],40)
        self.assertEqual(self.check()['sample_bytes_verified'],32)
        self.assertEqual(len(list((self.root/'run/responses').glob('*.bin'))),32)
        self.assertFalse(data['performance_valid'])

    def test_sample_bytes_changed_even_with_updated_file_digest(self):
        data=self.run_fixture()
        row=data['rows'][data['sample_ids'][0]]
        p=self.root/'run'/row['response_file']['path']
        p.write_bytes(b'X'*row['length'])
        self.mutate(lambda d:d['rows'][row['id']].update(response_file=file_ref(self.root/'run',p)))
        self.rejects()

    def test_fasta_change_outside_queried_regions(self):
        self.run_fixture()
        p=self.root/'a.fa'
        p.write_bytes(p.read_bytes().replace(b'comment',b'COMMENT'))
        self.rejects()

    def test_forged_unsampled_sha(self):
        data=self.run_fixture()
        rid=next(i for i in range(40) if i not in data['sample_ids'])
        self.mutate(lambda d:d['rows'][rid].update(observed_sha256='0'*64))
        self.rejects()

    def test_duplicate_row_same_count(self):
        self.run_fixture()
        self.mutate(lambda d:d['rows'].__setitem__(1,copy.deepcopy(d['rows'][0])))
        self.rejects()

    def test_coordinate_shift(self):
        self.run_fixture()
        self.mutate(lambda d:d['rows'][0]['canonical'].update(start0=1,end0=32))
        self.rejects()

    def test_prepare_anchor_rejects_coordinated_rewrite(self):
        self.run_fixture()
        p=self.root/'run/prepared.json'
        data=load_json(p)
        data['groups'][0]['a'].update(start0=1,end0=32)
        p.write_text(json.dumps(data))
        self.mutate(lambda d:d.update(prepared=file_ref(self.root/'run',p)))
        self.rejects()

    def test_wrong_external_anchor(self):
        self.run_fixture()
        with self.assertRaisesRegex(ValueError,'external anchor'):
            verifier.verify(self.root/'run/evidence.json', self.root, '0'*64)

    def test_missing_row(self):
        self.run_fixture()
        self.mutate(lambda d:d['rows'].pop())
        self.rejects()

    def test_sample_selection_is_seed_bound(self):
        self.run_fixture()
        self.mutate(lambda d:d.update(sample_seed=d['sample_seed']+1))
        self.rejects()

    def test_missing_sample(self):
        data=self.run_fixture()
        self.mutate(lambda d:d['rows'][data['sample_ids'][0]].update(response_file=None))
        self.rejects()

    def test_schema_rejects_unknown_claim(self):
        self.run_fixture()
        self.mutate(lambda d:d.update(fake_performance_claim=42))
        self.rejects()

    def test_schema_rejects_synthetic_performance(self):
        self.run_fixture()
        self.mutate(lambda d:d.update(performance_valid=True))
        self.rejects()

    def test_independent_verifier_never_calls_prepare_truth_or_codec(self):
        self.run_fixture()
        with mock.patch.object(job.FastaTruth,'fetch',side_effect=AssertionError('shared oracle')), \
             mock.patch.object(job,'open_reader',side_effect=AssertionError('codec')):
            self.assertEqual(self.check()['status'],'PASS')

    def test_prepare_is_deterministic_and_never_loads_codec(self):
        with mock.patch.object(job,'open_reader',side_effect=AssertionError('codec')):
            other=job.prepare(self.root,'cohort.json','groups.json','prepared2')
        self.assertEqual(other['sha256'],self.prepared['sha256'])
        with self.assertRaises(FileExistsError):
            job.prepare(self.root,'cohort.json','groups.json','prepared')

    def test_prepare_requires_every_assembly(self):
        del self.groups[0]['b']
        self.write('groups.json',self.groups)
        with self.assertRaisesRegex(ValueError,'cover the cohort'):
            job.prepare(self.root,'cohort.json','groups.json','bad')

    def test_prepare_rejects_empty_or_out_of_bounds_query(self):
        for start,end in ((5,5),(-1,2),(0,10000),(True,5)):
            with self.subTest(start=start,end=end):
                self.groups[0]['a'].update(start0=start,end0=end)
                self.write('groups.json',self.groups)
                with self.assertRaises(ValueError):
                    job.prepare(self.root,'cohort.json','groups.json','bad')

    def test_source_change_before_run_prevents_codec_open(self):
        (self.root/'a.fa').write_bytes(b'>chr\nAAAA\n')
        with mock.patch.object(job,'open_reader') as reader:
            with self.assertRaises(ValueError):
                job.run(self.root,'plan.json','run')
            reader.assert_not_called()

    def official(self):
        p=self.root/'prepared/prepared.json'
        d=load_json(p);d['evidence_kind']='official';p.write_text(json.dumps(d))
        self.plan['prepared']=file_ref(self.root,p);self.write('plan.json',self.plan)

    def test_failed_silence_gate_prevents_open_and_preserves_failure(self):
        self.official()
        bad=judge({'host':'ace-core','load1':1,'disk_available_bytes':30_000_000_000,
                   'sampling_seconds':1.1,'processes':[]})
        with mock.patch.object(job,'capture_silence',return_value=bad),mock.patch.object(job,'open_reader') as reader:
            data=job.run(self.root,'plan.json','run')
        reader.assert_not_called()
        self.assertEqual(data['status'],'FAILED')
        self.assertIsNone(data['seconds'])
        self.assertTrue((self.root/'run/silence-before.json').exists())

    def test_official_cli_cannot_bypass_wrong_host(self):
        self.official()
        with mock.patch('review.axis3.verdict_data.socket.gethostname',return_value='unit-host'):
            data=job.run(self.root,'plan.json','run')
        self.assertEqual(data['status'],'FAILED')
        self.assertIn('ace-core',data['error'])

    def test_failed_final_silence_invalidates_timings(self):
        self.official()
        good=judge({'host':'ace-core','load1':0,'disk_available_bytes':30_000_000_000,
                    'sampling_seconds':1.1,'processes':[]})
        bad=copy.deepcopy(good);bad['status']='FAILED'
        with mock.patch.object(job,'capture_silence',side_effect=[good,bad]), \
             mock.patch.object(job,'open_reader',side_effect=self.reader):
            data=job.run(self.root,'plan.json','run')
        self.assertEqual(data['status'],'FAILED')
        self.assertIsNone(data['seconds'])
        self.assertFalse(data['performance_valid'])

    def test_bad_native_response_leaves_failed_evidence(self):
        reader=self.reader()
        reader.fetch=lambda *args:b'X'*31
        with mock.patch.object(job,'open_reader',return_value=reader):
            data=job.run(self.root,'plan.json','run')
        self.assertEqual(data['status'],'FAILED')
        self.assertEqual(data['rows'][0]['status'],'FAILED')
        self.assertIsNone(data['seconds'])

    def test_source_mutation_during_run_is_rejected(self):
        reader=self.reader()
        reader.close=lambda:(self.root/'a.fa').write_bytes(b'changed')
        with mock.patch.object(job,'open_reader',return_value=reader):
            data=job.run(self.root,'plan.json','run')
        self.assertEqual(data['status'],'FAILED')
        self.assertIsNone(data['seconds'])

    def test_no_overwrite_of_evidence(self):
        self.run_fixture()
        with self.assertRaises(FileExistsError):
            job.run(self.root,'plan.json','run')

    def test_group_time_sum_tamper(self):
        self.run_fixture()
        self.mutate(lambda d:d.update(seconds=d['seconds']+1))
        self.rejects()

    def test_small_dataset_saves_every_response(self):
        self.write('groups.json', self.groups[:2])
        self.prepared=job.prepare(self.root,'cohort.json','groups.json','small')
        self.plan['prepared']=self.prepared
        self.write('plan.json',self.plan)
        self.run_fixture()
        self.assertEqual(self.check()['sample_bytes_verified'],4)

    def test_duplicate_json_key_is_rejected(self):
        self.run_fixture()
        p=self.root/'run/evidence.json'
        p.write_text(p.read_text().replace('"axis": 4','"axis": 4, "axis": 4'))
        self.rejects()

    def test_translated_coordinate_shift(self):
        self.run_fixture()
        self.mutate(lambda d:d['rows'][0]['translated'].update(start0=1,end0=32))
        self.rejects()

    def test_missing_input_ledger_entry(self):
        self.run_fixture()
        self.mutate(lambda d:d['input_files'].pop())
        self.rejects()

    def test_storage_ledger_omission_with_recomputed_total(self):
        self.run_fixture()
        def change(d):
            d['storage_files'].pop()
            d['stored_bytes']=sum(r['bytes'] for r in d['storage_files'])
        self.mutate(change)
        self.rejects()

    def test_forged_reader_provenance(self):
        self.run_fixture()
        self.mutate(lambda d:d['reader_build'].update(compiler='forged'))
        self.rejects()

    def test_sample_path_escape(self):
        data=self.run_fixture()
        rid=data['sample_ids'][0]
        self.mutate(lambda d:d['rows'][rid]['response_file'].update(path='../a.fa'))
        self.rejects()

    def test_zero_clock_interval_leaves_no_performance(self):
        with mock.patch.object(job,'open_reader',side_effect=self.reader):
            data=job.run(self.root,'plan.json','run',clock=lambda:1)
        self.assertEqual(data['status'],'FAILED')
        self.assertIsNone(data['seconds'])

    def test_broken_native_library_never_falls_back_to_truth(self):
        spec=self.plan['reader'];spec['family']='zstd-seekable';spec['variant']='default'
        build={'source_commit':job.native.ZSTD_PIN,'codec_version':'1.5.7','compiler':'unit compiler',
               'flags':['-fPIC'],'dependencies':{'zstd':'1.5.7'},'decoder_threads':1,
               'library_sha256':spec['library']['sha256']}
        self.write('build.json',build)
        spec['build_receipt']=file_ref(self.root,self.root/'build.json')
        for a in spec['archives']:
            name=a['assembly_id']+'.map.json'
            self.write(name,{'canonical_bytes':248,'contigs':[
                {'assembly_id':a['assembly_id'],'contig_id':'chr','prefix':0,'length':240},
                {'assembly_id':a['assembly_id'],'contig_id':'tail','prefix':240,'length':8}]})
            a['contig_map']=file_ref(self.root,self.root/name)
        self.write('plan.json',self.plan)
        with mock.patch.object(job.FastaTruth,'fetch',side_effect=AssertionError('fallback')):
            data=job.run(self.root,'plan.json','run')
        self.assertEqual(data['status'],'FAILED')
        self.assertEqual(data['verified'],0)
        self.assertIsNone(data['seconds'])
        self.assertIn('OSError',data['error'])

    def test_sample_selection_reproducible(self):
        self.assertEqual(verifier.sample_ids(1000,20261003),verifier.sample_ids(1000,20261003))
        self.assertNotEqual(verifier.sample_ids(1000,20261003),verifier.sample_ids(1000,20261004))
        self.assertEqual(len(set(verifier.sample_ids(1000,20261003))),32)

    def test_agc_axis4_does_not_require_window_law_geometry(self):
        spec={'family':'agc','variant':'noref','archive':file_ref(self.root,self.root/'a.fa')}
        corpus={'assemblies':load_json(self.root/'prepared/prepared.json')['assemblies']}
        build={'mode':'noref','create_calls':1,'append_calls':0,'cohort_order':['a','b'],
               'archive_sha256':spec['archive']['sha256']}
        inner=mock.Mock()
        inner.contig_length.side_effect=lambda a,c:240 if c=='chr' else 8
        with mock.patch.object(job.native,'_check_receipt',return_value=(self.root/'fixture.so',build)), \
             mock.patch.object(job.native,'AgcReader',return_value=inner):
            reader=job.open_reader(self.root,spec,corpus)
            self.assertEqual(reader.decoder_threads,1)
            reader.close()
            inner.close.assert_called_once()

    def test_agc_creation_receipt_cannot_name_another_archive(self):
        spec={'family':'agc','variant':'noref','archive':file_ref(self.root,self.root/'a.fa')}
        corpus={'assemblies':load_json(self.root/'prepared/prepared.json')['assemblies']}
        build={'mode':'noref','create_calls':1,'append_calls':0,'cohort_order':['a','b'],'archive_sha256':'0'*64}
        with mock.patch.object(job.native,'_check_receipt',return_value=(self.root/'fixture.so',build)), \
             mock.patch.object(job.native,'AgcReader') as inner:
            with self.assertRaisesRegex(ValueError,'archive mismatch'):
                job.open_reader(self.root,spec,corpus)
            inner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
