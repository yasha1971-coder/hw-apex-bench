"""A11 compressed truth and legacy independent verification regressions."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

import jsonschema
from review.axis3.verdict_data import file_ref, load_json
from tools import axis4 as job, axis4_evidence_verify as judge, axis4_stream as stream


def bgzf(data):
    compressor = zlib.compressobj(wbits=-15)
    payload = compressor.compress(data)+compressor.flush()
    size = 18+len(payload)+8
    if size > 65536:
        raise ValueError('test block too large')
    header = b'\x1f\x8b\x08\x04'+b'\0'*4+b'\0\xff'+struct.pack('<H', 6)+b'BC'+struct.pack('<HH', 2, size-1)
    return header+payload+struct.pack('<II', zlib.crc32(data), len(data))


class StreamingTruth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sequence = (b'acgTNryS'*10000)
        self.raw = b'>c description\r\n'+self.sequence+b'\r\n>tail\nACGTN'
        self.groups = [{'a': {'assembly_id':'a','contig_id':'c','start0':i*100,'end0':i*100+37}}
                       for i in range(40)]
        self.groups[-1] = {'a': {'assembly_id':'a','contig_id':'tail','start0':0,'end0':5}}
        (self.root/'groups.json').write_text(json.dumps(self.groups))

    def source(self, name='a.fa.gz', content=None, version='axis4-corpus-v1.1'):
        p = self.root/name
        p.write_bytes(gzip.compress(self.raw, mtime=0) if content is None else content)
        manifest = {'schema':version,'evidence_kind':'synthetic','assemblies':[
            {'assembly_id':'a','source_url':'synthetic:A11','fasta':file_ref(self.root,p)}]}
        (self.root/'cohort.json').write_text(json.dumps(manifest))
        return p

    def prepare(self, out='prepared'):
        ref = job.prepare(self.root,'cohort.json','groups.json',out)
        return ref, load_json(self.root/ref['path'])

    def execute(self):
        prepared, data = self.prepare()
        (self.root/'fixture.so').write_bytes(b'unit only')
        (self.root/'build.json').write_text('{"unit":true}')
        plan = {'schema':'axis4-plan-v1','prepared':prepared,'reader':{
            'family':'unit','variant':'unit','library':file_ref(self.root,self.root/'fixture.so'),
            'build_receipt':file_ref(self.root,self.root/'build.json'),
            'archives':[{'assembly_id':'a','archive':data['assemblies'][0]['fasta']}]}}
        (self.root/'plan.json').write_text(json.dumps(plan))
        sequence = self.sequence
        class Reader:
            scope='cpu-in-process'
            decoder_threads=1
            build={'unit':True}
            def fetch(self, aid, contig, start, end):
                return (sequence if contig=='c' else b'ACGTN')[start:end]
            def translated(self,w):
                return {'assembly_id':w.assembly,'contig_id':w.contig,'start0':w.start0,
                        'end0':w.end0,'convention':'0-based-half-open'}
            def close(self):
                pass
        with mock.patch.object(job,'open_reader',return_value=Reader()):
            result=job.run(self.root,'plan.json','run')
        self.assertEqual(result['status'],'PASS',result.get('error'))
        self.assertEqual(judge.verify(self.root/'run/evidence.json',self.root,prepared['sha256'])['verified'],40)
        return prepared, result

    def test_plain_and_gzip_identical_queries_and_canonical_sha(self):
        self.source('a.fa',self.raw)
        _, plain=self.prepare('plain')
        self.source()
        _, packed=self.prepare('packed')
        self.assertEqual(plain['groups'],packed['groups'])
        for key in ('contigs','canonical_bytes','canonical_sha256'):
            self.assertEqual(plain['assemblies'][0][key],packed['assemblies'][0][key])
        self.assertEqual(packed['assemblies'][0]['truth']['uncompressed_sha256'],hashlib.sha256(self.raw).hexdigest())

    def test_plain_and_gzip_sample_response_bytes_identical(self):
        self.source('a.fa',self.raw)
        _, plain = self.execute()
        expected={p.name:p.read_bytes() for p in (self.root/'run/responses').iterdir()}
        import shutil
        shutil.rmtree(self.root/'run')
        shutil.rmtree(self.root/'prepared')
        (self.root/'a.fa').unlink()
        self.source()
        _, packed=self.execute()
        self.assertEqual([r['observed_sha256'] for r in plain['rows']], [r['observed_sha256'] for r in packed['rows']])
        self.assertEqual(expected,{p.name:p.read_bytes() for p in (self.root/'run/responses').iterdir()})

    def test_gzip_run_verify_no_plain_fasta(self):
        self.source()
        _, result=self.execute()
        self.assertEqual(result['schema'],'axis4-evidence-v4')
        self.assertEqual(result['truth_version'],'1.1')
        self.assertFalse(list(self.root.rglob('*.fa')))
        self.assertEqual(result['truth_sources'][0]['uncompressed_sha256'],hashlib.sha256(self.raw).hexdigest())

    def test_compressed_replacement_refused_before_prepare(self):
        p=self.source()
        p.write_bytes(gzip.compress(self.raw.replace(b'description',b'DESCRIPTION'),mtime=0))
        with self.assertRaisesRegex(ValueError,'frozen file changed'):
            self.prepare()
        self.assertFalse((self.root/'prepared').exists())

    def test_compressed_replacement_refused_by_verify(self):
        p=self.source()
        prepared,_=self.execute()
        p.write_bytes(gzip.compress(self.raw+b'A',mtime=0))
        with self.assertRaises(ValueError):
            judge.verify(self.root/'run/evidence.json',self.root,prepared['sha256'])

    def test_truncated_gzip_refused_even_with_matching_manifest(self):
        self.source(content=gzip.compress(self.raw,mtime=0)[:-4])
        with self.assertRaisesRegex(ValueError,'truncated'):
            self.prepare()
        self.assertFalse((self.root/'prepared').exists())

    def test_bad_gzip_crc_refused(self):
        payload=bytearray(gzip.compress(self.raw,mtime=0)); payload[-8]^=1
        self.source(content=bytes(payload))
        with self.assertRaisesRegex(ValueError,'stream'):
            self.prepare()

    def test_concatenated_gzip_members(self):
        self.source(content=b''.join(gzip.compress(self.raw[i:i+10007],mtime=0) for i in range(0,len(self.raw),10007)))
        _, p=self.prepare()
        self.assertEqual(p['assemblies'][0]['truth']['uncompressed_sha256'],hashlib.sha256(self.raw).hexdigest())
        self.execute_after_prepare(p)

    def execute_after_prepare(self, unused):
        import shutil
        shutil.rmtree(self.root/'prepared')
        self.execute()

    def test_later_member_truncation_refused(self):
        data=gzip.compress(self.raw[:1000],mtime=0)+gzip.compress(self.raw[1000:],mtime=0)[:-1]
        self.source(content=data)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_bgzf_input_with_eof_block(self):
        self.source('a.fa.bgz',b''.join(bgzf(self.raw[i:i+30000]) for i in range(0,len(self.raw),30000))+bgzf(b''))
        self.execute()

    def test_bgzf_truncated_block(self):
        self.source('a.fa.gz',bgzf(self.raw[:30000])[:-3])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_compression_suffix_triggers_new_version_on_old_manifest(self):
        self.source(version='axis4-corpus-v1')
        _,p=self.prepare()
        self.assertEqual(p['schema'],'axis4-prepared-v2')

    def test_false_gzip_suffix_refused(self):
        self.source(content=self.raw)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_forged_uncompressed_evidence_sha_refused(self):
        self.source();prepared,_=self.execute()
        p=self.root/'run/evidence.json';d=load_json(p)
        d['truth_sources'][0]['uncompressed_sha256']='0'*64
        p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'ledger'):
            judge.verify(p,self.root,prepared['sha256'])

    def test_independent_scan_refuses_forged_raw_sha(self):
        p=self.source();_,data=self.prepare()
        a=copy.deepcopy(data['assemblies'][0]);a['truth']['uncompressed_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):
            judge.independent_truth(p,[(0,self.groups[0]['a'])],{0},a)

    def test_verify_never_calls_prepare_extractor(self):
        self.source();prepared,_=self.execute()
        with mock.patch.object(stream,'prepare_truth',side_effect=AssertionError('not independent')):
            judge.verify(self.root/'run/evidence.json',self.root,prepared['sha256'])

    def test_huge_sequence_line_reads_are_bounded(self):
        class Bounded(io.BytesIO):
            def readline(self,size=-1):
                if size<0 or size>stream.CHUNK:
                    raise AssertionError('unbounded FASTA read')
                return super().readline(size)
        count=[0];digest=hashlib.sha256()
        pieces=list(stream.segments(Bounded(self.raw),digest,count))
        self.assertTrue(all(len(v)<=stream.CHUNK for k,v in pieces if k=='sequence'))
        self.assertEqual(count[0],len(self.raw))

    def test_crlf_split_exactly_at_chunk_boundary(self):
        raw=b'>c\n'+b'A'*(stream.CHUNK-1)+b'\r\n'
        p=self.source(content=gzip.compress(raw,mtime=0))
        identity,_=stream.prepare_truth(p,[(0,{'contig_id':'c','start0':stream.CHUNK-3,'end0':stream.CHUNK-1})])
        self.assertEqual(identity['canonical_bytes'],stream.CHUNK-1)

    def test_oversized_header_refused(self):
        p=self.source(content=gzip.compress(b'>'+b'h'*5000+b'\nACGT',mtime=0))
        with self.assertRaisesRegex(ValueError,'header exceeds'):
            stream.prepare_truth(p,[])

    def test_duplicate_contig_refused(self):
        self.source(content=gzip.compress(b'>c\nACGT\n>c\nACGT',mtime=0))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.prepare()

    def test_query_out_of_bounds_refused(self):
        self.groups[0]['a']['end0']=len(self.sequence)+1
        (self.root/'groups.json').write_text(json.dumps(self.groups))
        self.source()
        with self.assertRaisesRegex(ValueError,'outside'):
            self.prepare()

    def test_legacy_retained_v1_protocol_evidence_passes(self):
        root=job.REPO/'tests/fixtures/leaderboard/input/data'
        prepared=load_json(root/'plan.json')['prepared']
        self.assertEqual(judge.verify(root/'evidence/evidence.json',root,prepared['sha256'])['status'],'PASS')

    def test_new_schema_does_not_accept_legacy_as_new(self):
        self.source();_,p=self.prepare()
        p['schema']='axis4-prepared-v1'
        with self.assertRaises(jsonschema.ValidationError):
            judge.validate_schema(p)

    def test_explicit_new_plain_mode_on_legacy_manifest(self):
        self.source('a.fa',self.raw,version='axis4-corpus-v1')
        p=job.prepare(self.root,'cohort.json','groups.json','prepared',truth_version='1.1')
        self.assertEqual(load_json(self.root/p['path'])['schema'],'axis4-prepared-v2')

    def test_stream_prepare_never_uses_fasta_index(self):
        self.source()
        with mock.patch.object(job,'FastaTruth',side_effect=AssertionError('legacy index called')):
            self.prepare()

    def test_forged_canonical_identity_refused(self):
        p=self.source();_,data=self.prepare()
        a=copy.deepcopy(data['assemblies'][0]);a['canonical_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):
            judge.independent_truth(p,[(0,self.groups[0]['a'])],{0},a)

    def test_evidence_cannot_downgrade_new_prepare(self):
        self.source();prepared,result=self.execute()
        result['schema']='axis4-evidence-v3'
        result.pop('truth_version');result.pop('truth_sources')
        (self.root/'run/evidence.json').write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'version mismatch'):
            judge.verify(self.root/'run/evidence.json',self.root,prepared['sha256'])

    def test_v4_leaderboard_is_verified(self):
        from tools import build_leaderboard
        self.source();prepared,_=self.execute()
        (self.root/'leaderboard-input.json').write_text(json.dumps({'schema':'leaderboard-input-v1',
            'records':[{'evidence':file_ref(self.root,self.root/'run/evidence.json'),
                        'input_root':'.','prepared_sha256':prepared['sha256']}]}))
        result=build_leaderboard.build([self.root],self.root/'leaderboard')
        self.assertEqual(result['rows'],1)

    def test_synthetic_entrypoint_gzip_only(self):
        from tools.axis4_stream_synthetic import run_case
        result=run_case(self.root/'synthetic')
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['native_execution'])
        self.assertEqual(result['uncompressed_FASTA_files'],0)
        self.assertEqual(result['sample_bytes_verified'],32)

    def test_synthetic_memory_probe_fixed_allocation_budget(self):
        from tools.axis4_stream_memory import benchmark
        result=benchmark(self.root/'memory',sizes=(1048576,8388608))
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['uncompressed_FASTA_files'],0)
        self.assertEqual([r['queries'] for r in result['rows']],[4,4])
        for row in result['rows']:
            self.assertLessEqual(row['prepare_traced_peak_bytes'],2097152)
            self.assertLessEqual(row['verify_traced_peak_bytes'],2097152)
