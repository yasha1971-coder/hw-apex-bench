"""Decoder worker lifecycle and thread evidence regressions without native deps."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from review.axis3.verdict_data import file_ref, load_json
from tools import axis4, axis4_threads as mt, axis4_evidence_verify as judge


class DecoderThreads(unittest.TestCase):
    def pool(self, n=8, failure=0):
        events=[]
        lib=SimpleNamespace(_name='pinned')
        lib.hts_tpool_init=Mock(return_value=42)
        lib.hts_tpool_size=Mock(return_value=n)
        lib.hts_tpool_destroy=Mock(side_effect=lambda p: events.append('destroy'))
        lib.fai_thread_pool=Mock(return_value=failure)
        handles=[SimpleNamespace(lib=lib,handle=i) for i in (1,2)]
        reader=SimpleNamespace(singles={i:SimpleNamespace(reader=SimpleNamespace(inner=h)) for i,h in enumerate(handles)},
             close=Mock(side_effect=lambda: events.append('close')),scope='cpu-in-process')
        return reader,lib,events

    def test_shared_pool_not_one_pool_per_assembly(self):
        r,l,e=self.pool();p=mt.configure(r,'bgzf',8)
        self.assertEqual(p.decoder_threads,8);l.hts_tpool_init.assert_called_once_with(8)
        self.assertEqual(l.fai_thread_pool.call_args_list[0].args,(1,42,16))
        self.assertEqual(l.fai_thread_pool.call_args_list[1].args,(2,42,16))
        p.close();self.assertEqual(e,['close','destroy'])

    def test_close_is_idempotent(self):
        r,l,e=self.pool();p=mt.configure(r,'bgzf',8);p.close();p.close()
        self.assertEqual(e,['close','destroy'])

    def test_attach_failure_closes_handles_before_pool(self):
        r,l,e=self.pool(failure=-1)
        with self.assertRaises(ValueError):mt.configure(r,'bgzf',8)
        self.assertEqual(e,['close','destroy'])

    def test_wrong_native_count_refused(self):
        r,l,e=self.pool(n=2)
        with self.assertRaises(ValueError):mt.configure(r,'bgzf',8)
        self.assertEqual(e,['close','destroy'])

    def test_missing_native_export_is_unsupported_and_closes(self):
        r,l,e=self.pool();del l.fai_thread_pool
        with self.assertRaises(mt.NotSupported):mt.configure(r,'bgzf',8)
        self.assertEqual(e,['close'])

    def test_scalar_no_pool_or_emulation(self):
        r,l,e=self.pool();self.assertIs(mt.configure(r,'bgzf',1),r)
        l.hts_tpool_init.assert_not_called()

    def test_unsupported_families_explicit(self):
        for f in ('refrel3','zstd-seekable','fasta-faidx','agc','lz4-indexed','ozseg'):
            for n in (2,8,16):self.assertEqual(mt.capability(f,n)['status'],'NOT_SUPPORTED')

    def test_invalid_threads(self):
        for n in (True,False,0,-1,257,1.0,None):
            with self.assertRaises(ValueError):mt.capability('bgzf',n)

    def test_hardware_is_canonical(self):
        h=mt.hardware();self.assertEqual(h['cpu_models'],sorted(set(h['cpu_models'])))
        if h['affinity'] is not None:self.assertEqual(h['affinity'],sorted(set(h['affinity'])))

    def fixture(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        (root/'a.fa').write_bytes(b'>c\nACGTACGT\n')
        (root/'cohort.json').write_text(json.dumps({'schema':'axis4-corpus-v1','evidence_kind':'synthetic',
           'assemblies':[{'assembly_id':'a','source_url':'synthetic:threads','fasta':file_ref(root,root/'a.fa')}]}))
        (root/'groups.json').write_text(json.dumps([{'a':{'assembly_id':'a','contig_id':'c','start0':0,'end0':4}}]))
        prep=axis4.prepare(root,'cohort.json','groups.json','prepared')
        (root/'unit.so').write_bytes(b'unit');(root/'build.json').write_text('{"unit":true}')
        plan={'schema':'axis4-plan-v1','prepared':prep,'reader':{'family':'unit','variant':'unit',
          'library':file_ref(root,root/'unit.so'),'build_receipt':file_ref(root,root/'build.json'),
          'archives':[{'assembly_id':'a','archive':file_ref(root,root/'a.fa')}]}}
        (root/'plan.json').write_text(json.dumps(plan))
        reader=SimpleNamespace(scope='cpu-in-process',decoder_threads=1,build={'unit':True},close=lambda:None,
          fetch=lambda a,c,s,e:b'ACGTACGT'[s:e],translated=lambda w:{'assembly_id':'a','contig_id':'c',
          'start0':w.start0,'end0':w.end0,'convention':'0-based-half-open'})
        return root,prep,reader

    def test_scalar_v5_independent_verify(self):
        root,p,r=self.fixture()
        with patch.object(axis4,'open_reader',return_value=r):d=axis4.run(root,'plan.json','run',decoder_threads=1)
        self.assertEqual(d['schema'],'axis4-evidence-v5');self.assertEqual(d['status'],'PASS',d['error'])
        self.assertEqual(judge.verify(root/'run/evidence.json',root,p['sha256'])['verified'],1)

    def test_unsupported_evidence_never_opens_decoder(self):
        root,p,r=self.fixture()
        with patch.object(axis4,'open_reader') as op:d=axis4.run(root,'plan.json','run',decoder_threads=8)
        op.assert_not_called();self.assertEqual(d['status'],'NOT_SUPPORTED');self.assertEqual(d['rows'],[])
        self.assertIsNone(d['seconds']);self.assertFalse(d['performance_valid'])
        with self.assertRaises(ValueError):judge.verify(root/'run/evidence.json',root,p['sha256'])

    def test_thread_capability_forgery_refused(self):
        root,p,r=self.fixture()
        with patch.object(axis4,'open_reader',return_value=r):d=axis4.run(root,'plan.json','run',decoder_threads=1)
        d['decoder_threads']=8;(root/'run/evidence.json').write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'capability'):judge.verify(root/'run/evidence.json',root,p['sha256'])

    def test_response_forgery_refused(self):
        root,p,r=self.fixture()
        with patch.object(axis4,'open_reader',return_value=r):d=axis4.run(root,'plan.json','run',decoder_threads=1)
        d['rows'][0]['observed_sha256']='0'*64;(root/'run/evidence.json').write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'SHA'):judge.verify(root/'run/evidence.json',root,p['sha256'])

    def test_v5_leaderboard_separates_decoder_counts(self):
        from tools import build_leaderboard as lb
        root,p,r=self.fixture()
        plan=load_json(root/'plan.json');plan['reader']['family']='bgzf'
        (root/'plan.json').write_text(json.dumps(plan));records=[]
        for n in (1,2):
            def config(reader,family,threads):
                reader.decoder_threads=threads
                return reader
            with patch.object(axis4,'open_reader',return_value=r), patch.object(mt,'configure',side_effect=config):
                d=axis4.run(root,'plan.json',f'run-{n}',decoder_threads=n)
            self.assertEqual(d['status'],'PASS',d['error'])
            records.append({'evidence':file_ref(root,root/f'run-{n}'/'evidence.json'),
                            'input_root':'.','prepared_sha256':p['sha256']})
        (root/'leaderboard-input.json').write_text(json.dumps({'schema':'leaderboard-input-v1','records':records}))
        result=lb.collect([root])
        self.assertEqual(len(result[0]["tables"]),2)
        for rec in records:rec['table']='mixed-threads'
        (root/'leaderboard-input.json').write_text(json.dumps({'schema':'leaderboard-input-v1','records':records}))
        with self.assertRaisesRegex(ValueError,'mixed conditions'):lb.collect([root])

    def test_native_response_mismatch_is_failed(self):
        root,p,r=self.fixture();r.fetch=lambda *args:b'TTTT'
        with patch.object(axis4,'open_reader',return_value=r):d=axis4.run(root,'plan.json','run',decoder_threads=1)
        self.assertEqual(d['status'],'FAILED');self.assertFalse(d['performance_valid'])
        with self.assertRaises(ValueError):judge.verify(root/'run/evidence.json',root,p['sha256'])

    def test_v5_compressed_truth_independent_verify(self):
        import gzip
        root,p,r=self.fixture()
        (root/'a.fa.gz').write_bytes(gzip.compress((root/'a.fa').read_bytes(),mtime=0))
        manifest=load_json(root/'cohort.json');manifest['schema']='axis4-corpus-v1.1'
        manifest['assemblies'][0]['fasta']=file_ref(root,root/'a.fa.gz')
        (root/'cohort.json').write_text(json.dumps(manifest))
        p=axis4.prepare(root,'cohort.json','groups.json','compressed-prepared')
        plan=load_json(root/'plan.json');plan['prepared']=p
        (root/'plan.json').write_text(json.dumps(plan))
        with patch.object(axis4,'open_reader',return_value=r):d=axis4.run(root,'plan.json','run',decoder_threads=1)
        self.assertEqual(d['status'],'PASS',d['error']);self.assertEqual(d['truth_version'],'1.1')
        self.assertEqual(judge.verify(root/'run/evidence.json',root,p['sha256'])['verified'],1)
