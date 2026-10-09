"""B job: deterministic production orchestration with artificial clocks, never native rates."""
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import verdict_refrel3 as job
from tools.axis3_window_engine import Window, freeze_windows, sample_coordinates
from tools.window_law import diagnose, main as law_main
from review.axis3.verdict_data import (
    DOMAIN, FastaTruth, checked_file, file_ref, load_json, normalize_full,
    sha256_file, verify_protocol, write_json,
)
from review.axis3.verdict_readers import bgzf_canonical_sizes, positive_mean, _check_receipt, REFREL_PIN

ROOT = Path(__file__).resolve().parents[1]


class ArtificialClock:
    def __init__(self):
        self.value = 0
        self.calls = 0
    def __call__(self):
        self.calls += 1
        return self.value
    def advance(self, n):
        self.value += int(n)


class SyntheticReader:
    scope = 'cpu-in-process'
    decoder_threads = 1
    build = {'kind': 'synthetic-fixture-not-a-native-codec'}
    full_timing_boundary = 'artificial-clock synthetic decode only'
    def __init__(self, clock, q=4096):
        self.clock = clock
        self.q = Fraction(q)
        self.geometry = [{'method': 'synthetic', 'Q': q}]
        self.seq = {f'a{i}': b'ACGT' * 20000 for i in range(4)}
        self.bad_window = None
        self.bad_full = False
        self.probe_ns = 20000
        self.factor = {}
        self.full_calls = 0
        self.fetch_count = 0
    def contig_length(self, a, c):
        if c != 'ctg':
            raise KeyError(c)
        return len(self.seq[a])
    def translated(self, r):
        return {**r.canonical(), 'api': 'synthetic-fixture'}
    def fetch(self, a, c, s, e):
        self.contig_length(a, c)
        if not 0 <= s < e <= len(self.seq[a]):
            raise ValueError('bounds')
        self.fetch_count += 1
        duration = self.probe_ns + ((e - s - 1) * 1000000 + 319999) // 320000
        self.clock.advance(max(1, duration * self.factor.get(e - s, 1)))
        out = self.seq[a][s:e]
        return b'N' * len(out) if e - s == self.bad_window else out
    def decode_native(self):
        self.full_calls += 1
        self.clock.advance(1000000)
        return [(a, 'sequence', b'N' * len(s) if self.bad_full else s) for a, s in self.seq.items()]


def corpus_for(reader):
    return {'assemblies': [{'assembly_id': a, 'canonical_bytes': len(s),
            'canonical_sha256': hashlib.sha256(s).hexdigest(),
            'contigs': [{'contig_id': 'ctg', 'length': len(s)}]} for a, s in reader.seq.items()]}


def frozen_requests(reader, windows=(1, 2, 1024, 8192, 65536), count=3):
    coords = [(a, 'ctg', len(seq)) for a, seq in reader.seq.items()]
    # Use a separate ground-truth object: mutating the decoder cannot mutate SHA truth.
    class Truth:
        def fetch(self, a, c, s, e):
            return reader.seq[a][s:e]
    return {w: freeze_windows(sample_coordinates(coords, w, count=count), Truth()) for w in windows}


def eval_fixture(root, *, reader=None, name='refrel-q4k', family='refrel3', variant='q4k', count=3):
    r = reader or SyntheticReader(ArtificialClock())
    spec = {'id': name, 'family': family, 'variant': variant}
    result = job.evaluate_variant(spec, r, corpus_for(r), frozen_requests(r, count=count), Path(root)/name,
                                  clock=r.clock, expected_count=count, kind='synthetic')
    return result, r


def complete_report(root):
    root = Path(root)
    entries = []
    for name, family, variant, q in (
            ('rr4', 'refrel3', 'q4k', 4096), ('rr16', 'refrel3', 'q16k', 16384),
            ('bgd', 'bgzf', 'default', 64000), ('bgm', 'bgzf', 'matched-g', 16384),
            ('zsk', 'zstd-seekable', 'l3', 16384), ('lz4', 'lz4-indexed', 'l1', 65536),
            ('oz', 'ozseg', 'l1_w64k', 65536), ('oz1m', 'ozseg', 'l1_w1m', 1048576),
            ('oz3', 'ozseg', 'l3_w64k', 65536), ('oz3m', 'ozseg', 'l3_w1m', 1048576),
            ('agct', 'agc', 't2t', 20000), ('agcn', 'agc', 'noref', 20000)):
        r = SyntheticReader(ArtificialClock(), q=q)
        # Independent positive overhead for every Q; no factor is fitted to windows.
        r.probe_ns = 5000000
        e, _ = eval_fixture(root, reader=r, name=name, family=family, variant=variant)
        entries.append(e)
    contract = root/'contract/review/axis3'
    contract.mkdir(parents=True)
    for name in ('PROTOCOL_AXIS3.md','PROTOCOL_FREEZE.json'):
        shutil.copyfile(ROOT/'review/axis3'/name, contract/name)
    ref = {'path':'synthetic-input.json','bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}
    result = {'schema':'window-law-verdict-v1','run_id':'synthetic-acceptance','kind':'synthetic',
              'protocol_sha256':verify_protocol(ROOT)['sha256'],'protocol_version':'1.1','domain':DOMAIN,
              'scope':'cpu-in-process','threads':1,'seed':20261003,'plan':ref,'prepared':ref,
              'input_references':[],'windows_bytes':[1,2,1024,8192,65536],'samples_per_window':3,
              'entries':entries,'summary':job.aggregate(entries),'immutable_input_error':None,'silence_logs':[]}
    write_json(root/'results.json', result)
    return result


class WindowRoles(unittest.TestCase):
    def test_one_byte_has_no_error_verdict(self):
        r=diagnose(1000000,1,100,9999,200)
        self.assertEqual(r['verdict'],'CALIBRATION_ONLY')
        self.assertFalse(r['verdict_eligible'])
    def test_intermediate_has_no_error_verdict(self):
        r=diagnose(1000000,4096,100,999999,200)
        self.assertEqual(r['verdict'],'DIAGNOSTIC_ONLY')
        self.assertFalse(r['verdict_eligible'])
    def test_only_three_windows_eligible(self):
        for w in (1,2,512,1024,4096,8192,16384,32768,65536):
            self.assertEqual(diagnose(1000000,w,100,1,200)['verdict_eligible'],w in (1024,8192,65536))
    def test_negative_c0_is_not_clamped_on_diagnostic(self):
        r=diagnose(1000000,2,100,1,20)
        self.assertEqual(r['c0_us'],-80)
        self.assertEqual(r['model_status'],'FAIL')
        self.assertEqual(r['verdict'],'DIAGNOSTIC_ONLY')
    def test_both_twenty_percent_boundaries_inclusive(self):
        for measured in ('978.4','1467.6'):
            self.assertEqual(diagnose(1000000,1024,100,measured,200)['verdict'],'PASS')
    def test_outside_window_range_refused(self):
        for w in (0,65537,1.1):
            with self.assertRaises(ValueError):diagnose(1000000,w,100,1,200)
    def test_diagnostic_error_cli_exit_is_not_failure(self):
        self.assertEqual(law_main(['--dq-bps','1000000','--window','4096','--q','100',
                                  '--measured-p50-us','999999','--probe-w1-p50-us','200']),0)
    def test_negative_c0_cli_exit_is_failure_even_for_diagnostic(self):
        self.assertEqual(law_main(['--dq-bps','1000000','--window','2','--q','100',
                                  '--measured-p50-us','20','--probe-w1-p50-us','20']),1)


class InputContracts(unittest.TestCase):
    def test_default_sweep_is_predeclared(self):
        self.assertEqual(job.checked_windows(job.DEFAULT_SWEEP),[1<<k for k in range(17)])
    def test_missing_verdict_window_rejected(self):
        with self.assertRaises(ValueError):job.checked_windows([1,1024,8192])
    def test_duplicate_and_unsorted_sweep_rejected(self):
        for ws in ([1,1,1024,8192,65536],[1024,1,8192,65536],[True,1024,8192,65536]):
            with self.assertRaises(ValueError):job.checked_windows(ws)
    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for path in ('../x','/tmp/x','x\\y','x:2'):
                with self.assertRaises(ValueError):checked_file(Path(d),{'path':path,'bytes':0,'sha256':'0'*64})
    def test_changed_file_ref_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'x');ref=file_ref(d,p);p.write_bytes(b'y')
            with self.assertRaises(ValueError):checked_file(d,ref)
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):load_json(p)
    def test_fasta_truth_lf_crlf_and_empty_contig(self):
        with tempfile.TemporaryDirectory() as d:
            for sep in (b'\n',b'\r\n'):
                p=Path(d)/'a';p.write_bytes(sep.join([b'>c comment',b'acgt',b'ACGT',b'AA',b'>empty',b'>d',b'NN'])+sep)
                t=FastaTruth([('a',p)])
                try:
                    self.assertEqual(t.fetch('a','c',2,9),b'GTACGTA')
                    self.assertEqual(t.fetch('a','d',0,2),b'NN')
                    self.assertEqual(t.full_identity('a')['canonical_bytes'],12)
                    with self.assertRaises(ValueError):t.fetch('a','empty',0,1)
                finally:t.close()
    def test_truth_rejects_irregular_wrap_and_duplicate_name(self):
        with tempfile.TemporaryDirectory() as d:
            for data in (b'>x\nACGT\nA\nACGT\n',b'>x\nAC\n>x\nAC\n'):
                p=Path(d)/'x';p.write_bytes(data)
                with self.assertRaises(ValueError):FastaTruth([('a',p)])
    def test_normalization_only_removes_framing_and_uppercases(self):
        chunks=list(normalize_full('fasta',b'>x note\r\nacgt\r\nAA\n',[{'contig_id':'x','length':6}]))
        self.assertEqual(b''.join(chunks),b'ACGTAA')
    def test_normalization_rejects_contig_reordering(self):
        with self.assertRaises(ValueError):list(normalize_full('fasta',b'>b\nAC\n',[{'contig_id':'a','length':2}]))
    def test_positive_unit_mean_excludes_zero_not_framing(self):
        self.assertEqual(positive_mean([0,2,4]),3)
        with self.assertRaises(ValueError):positive_mean([0])
    def test_protocol_digest_and_clarification(self):
        f=verify_protocol(ROOT)
        self.assertEqual(f['verdict_windows_bytes'],[1024,8192,65536])
        self.assertEqual(f['calibration_window_bytes'],1)
    def test_bgzf_geometry_counts_canonical_not_isize(self):
        with tempfile.TemporaryDirectory() as d:
            import struct,zlib
            data=b'>x\nacgt\nACGT\n>y\nNN\n';p=Path(d)/'x.fa';p.write_bytes(data)
            # Genuine BGZF members produced by stdlib raw deflate, no native timing.
            def member(raw):
                z=zlib.compressobj(wbits=-15);payload=z.compress(raw)+z.flush()
                size=18+len(payload)+8
                return bytes.fromhex('1f8b08040000000000ff060042430200')+struct.pack('<H',size-1)+payload+struct.pack('<II',zlib.crc32(raw),len(raw))
            arc=Path(d)/'x.bgz';arc.write_bytes(b''.join(member(data[i:i+5]) for i in range(0,len(data),5)))
            sizes=bgzf_canonical_sizes(arc,p,'a')
            self.assertEqual(sum(sizes),10)
            self.assertLess(sum(sizes),len(data))
    def test_prepare_is_deterministic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'a.fa';p.write_bytes(b'>ctg\n'+b'ACGT'*20000+b'\n')
            manifest={'schema':'window-law-corpus-v1','assemblies':[{'assembly_id':'a','fasta':file_ref(root,p),
                        'source_url':'synthetic:fixture','source_sha256':sha256_file(p)}]}
            write_json(root/'manifest.json',manifest)
            ws=[1,1024,8192,65536]
            a=job.prepare(root,'manifest.json','p1',ws)
            b=job.prepare(root,'manifest.json','p2',ws)
            x=load_json(root/a['path']);y=load_json(root/b['path'])
            self.assertEqual([r['file']['sha256'] for r in x['requests']],[r['file']['sha256'] for r in y['requests']])
            self.assertEqual(x['samples_per_window'],10000)
            corpus=load_json(root/x['corpus']['path']);req=job.read_requests(root,x,corpus)
            self.assertEqual(len(req[1]),10000)
            with self.assertRaises(FileExistsError):job.prepare(root,'manifest.json','p1',ws)
    def test_nonfinite_json_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{"x":NaN}')
            with self.assertRaises(ValueError):load_json(p)


class ProductionOrchestration(unittest.TestCase):
    def test_dq_twelve_sha_checks_and_nine_raw_times(self):
        r=SyntheticReader(ArtificialClock());rows=[]
        got=job.run_dq_series(r,corpus_for(r),clock=r.clock,sink=rows.append)
        self.assertEqual(r.full_calls,12)
        self.assertEqual(len(rows),12)
        self.assertEqual(len(got['raw_ns']),9)
        self.assertTrue(all(all(c['observed_sha256']==c['expected_sha256'] for c in row['checks']) for row in rows))
    def test_sha_failure_in_warmup_is_not_ignored(self):
        r=SyntheticReader(ArtificialClock());r.bad_full=True;rows=[]
        with self.assertRaises(job.FullDecodeMismatch):job.run_dq_series(r,corpus_for(r),clock=r.clock,sink=rows.append)
        self.assertEqual(r.full_calls,1)
        self.assertEqual(rows[0]['status'],'FAILED')
        self.assertNotEqual(rows[0]['checks'][0]['expected_sha256'],rows[0]['checks'][0]['observed_sha256'])
    def test_normalization_and_sha_occur_outside_timed_interval(self):
        r=SyntheticReader(ArtificialClock())
        original=job.full_check
        def slow_judge(outputs,corpus):
            r.clock.advance(999999999)
            return original(outputs,corpus)
        with patch.object(job,'full_check',slow_judge):
            got=job.run_dq_series(r,corpus_for(r),clock=r.clock)
        self.assertEqual(got['raw_ns'],[1000000]*9)
    def test_negative_c0_keeps_value_and_fails_format(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock());r.probe_ns=1
            e,_=eval_fixture(d,reader=r)
            self.assertEqual(e['data_status'],'PASS')
            self.assertEqual(e['verdict'],'FAIL')
            self.assertTrue(all(o['c0_us']<0 for o in e['observations']))
    def test_intermediate_large_error_does_not_fail_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock());r.factor[2]=100
            e,_=eval_fixture(d,reader=r)
            self.assertEqual(e['verdict'],'PASS')
            row=next(x for x in e['observations'] if x['W_bytes']==2)
            self.assertGreater(abs(row['primary_signed_error_percent']),20)
            self.assertEqual(row['verdict'],'DIAGNOSTIC_ONLY')
    def test_intermediate_wrong_sha_still_fails_run(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock());r.bad_window=2
            e,_=eval_fixture(d,reader=r)
            self.assertEqual(e['data_status'],'FAILED')
            self.assertIsNone(e['dq']);self.assertEqual(e['observations'],[])
    def test_verdict_window_error_fails_format(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock());r.factor[1024]=2
            e,_=eval_fixture(d,reader=r)
            self.assertEqual(e['data_status'],'PASS');self.assertEqual(e['verdict'],'FAIL')
    def test_c0_probe_executed_once(self):
        with tempfile.TemporaryDirectory() as d:
            e,r=eval_fixture(d)
            self.assertEqual(r.fetch_count,5*3)
            self.assertEqual(sum(o['window_role']=='CALIBRATION_ONLY' for o in e['observations']),1)
    def test_official_expected_count_cannot_be_reduced(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock())
            e=job.evaluate_variant({'id':'x','family':'refrel3','variant':'q4k'},r,corpus_for(r),frozen_requests(r),Path(d)/'x',clock=r.clock,expected_count=3,kind='measured')
            self.assertEqual(e['data_status'],'FAILED');self.assertEqual(r.full_calls,0)
    def test_duplicate_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            eval_fixture(d)
            with self.assertRaises(FileExistsError):eval_fixture(d)
    def test_wrong_scope_refused_before_decode(self):
        r=SyntheticReader(ArtificialClock());r.scope='cli'
        with self.assertRaises(ValueError):job.run_dq_series(r,corpus_for(r),clock=r.clock)
        self.assertEqual(r.full_calls,0)
    def test_bgzf_modes_do_not_count_as_two_foreign_formats(self):
        entries=[{'id':'a','family':'bgzf','variant':'default','data_status':'PASS','verdict':'PASS'},
                 {'id':'b','family':'bgzf','variant':'matched-g','data_status':'PASS','verdict':'PASS'}]
        self.assertEqual(job.aggregate(entries)['foreign_format_count'],1)
        self.assertFalse(job.aggregate(entries)['coverage_complete'])
    def test_both_refrel_qs_required_for_comparison(self):
        entries=[{'id':f,'family':f,'variant':'default','data_status':'PASS','verdict':'PASS'} for f in ('bgzf','zstd-seekable','lz4-indexed','ozseg')]
        self.assertEqual(job.aggregate(entries)['foreign_format_count'],4)
        self.assertEqual(job.aggregate(entries)['refrel3_verdict'],'FAIL')
    def test_missing_predeclared_windows_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=SyntheticReader(ArtificialClock())
            with self.assertRaises(ValueError):job.evaluate_variant({'id':'x','family':'refrel3','variant':'q4k'},r,corpus_for(r),frozen_requests(r,windows=(1,1024)),Path(d)/'x',clock=r.clock,kind='synthetic',expected_count=3)


class EvidenceVerification(unittest.TestCase):
    def test_complete_synthetic_job_and_table(self):
        with tempfile.TemporaryDirectory() as d:
            result=complete_report(d)
            verified=job.verify_result(d)
            self.assertEqual(verified['summary']['comparison_verdict'],'PASS')
            text=job.render_table(verified)
            self.assertIn('DIAGNOSTIC_ONLY',text)
            self.assertIn('CALIBRATION_ONLY',text)
            self.assertIn('SHA-256',text)
            self.assertIn('synthetic',text)
    def test_manual_model_number_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['entries'][0]['observations'][2]['primary_predicted_p50_us']+=1
            (Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_raw_log_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);e=r['entries'][0];p=Path(d)/e['id']/e['raw_logs'][0]['path'];p.write_bytes(p.read_bytes()+b' ')
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_claim_of_six_foreign_formats_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['summary']['foreign_format_count']=6
            (Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_frozen_protocol_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            complete_report(d);p=Path(d)/'contract/review/axis3/PROTOCOL_AXIS3.md';p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_schema_rejects_metrics_on_failed_data(self):
        import jsonschema
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['entries'][0]['data_status']='FAILED';r['entries'][0]['error']='test'
            (Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(jsonschema.ValidationError):job.verify_result(d)
    def test_incomplete_refrel_claim_rejected_by_aggregate(self):
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['entries']=[e for e in r['entries'] if e['id']!='rr16']
            (Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_unknown_result_field_rejected(self):
        import jsonschema
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['made_up']='value';(Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(jsonschema.ValidationError):job.verify_result(d)


class PlanAndBindingAcceptance(unittest.TestCase):
    def prepared_plan(self, root):
        rows=[]
        for i in range(4):
            p=root/f'a{i}.fa';p.write_bytes(b'>ctg'+bytes([10])+b'ACGT'*20000+bytes([10]))
            rows.append({'assembly_id':f'a{i}','fasta':file_ref(root,p),
                         'source_url':'synthetic:fixture','source_sha256':sha256_file(p)})
        write_json(root/'cohort.json',{'schema':'window-law-corpus-v1','assemblies':rows})
        prepared=job.prepare(root,'cohort.json','prepared',[1,1024,8192,65536])
        (root/'RUN.md').write_text('synthetic fixture, no benchmark')
        variants=[{'id':name,'family':family,'variant':variant} for name,family,variant in (
                  ('r4','refrel3','q4k'),('r16','refrel3','q16k'),('bd','bgzf','default'),
                  ('bm','bgzf','matched-g'),('zs','zstd-seekable','l3'),('lz','lz4-indexed','l1'),
                  ('oz','ozseg','l1_w64k'))]
        plan={'schema':'window-law-plan-v1','run_id':'synthetic-plan','scope':'cpu-in-process',
              'threads':1,'seed':20261003,'dq_warmups':3,'dq_repeats':9,'prepared':prepared,
              'runbook':file_ref(root,root/'RUN.md'),'variants':variants}
        write_json(root/'plan.json',plan)
        return plan
    def test_real_preparation_validates_shared_requests(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.prepared_plan(root)
            plan,prepared,corpus,requests,protocol=job.load_plan(root,'plan.json')
            self.assertEqual(len(corpus['assemblies']),4)
            self.assertEqual({w:len(rs) for w,rs in requests.items()},dict.fromkeys((1,1024,8192,65536),10000))
    def test_runbook_drift_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.prepared_plan(root);(root/'RUN.md').write_text('changed')
            with self.assertRaises(ValueError):job.load_plan(root,'plan.json')
    def test_rehashed_changed_request_not_accepted_as_new_truth(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan=self.prepared_plan(root)
            prepared=load_json(root/plan['prepared']['path'])
            p=root/prepared['requests'][0]['file']['path'];rows=p.read_text().splitlines()
            first=json.loads(rows[0]);first['start0']+=1;first['end0']+=1;rows[0]=json.dumps(first)
            p.write_text(chr(10).join(rows)+chr(10))
            prepared['requests'][0]['file']=file_ref(root,p)
            (root/plan['prepared']['path']).write_text(json.dumps(prepared))
            plan['prepared']=file_ref(root,root/plan['prepared']['path'])
            (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaises(ValueError):job.load_plan(root,'plan.json')
    def test_displayed_q_cannot_differ_from_exact_q(self):
        with tempfile.TemporaryDirectory() as d:
            r=complete_report(d);r['entries'][0]['Q_bytes']=999
            (Path(d)/'results.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):job.verify_result(d)
    def test_full_decode_order_must_cover_same_cohort(self):
        r=SyntheticReader(ArtificialClock())
        with self.assertRaises(ValueError):job.full_check(list(reversed(r.decode_native())),corpus_for(r))
    def test_refrel3_translated_coordinates_match_actual_shim(self):
        from review.axis3.native_readers import Refrel3Reader
        r=object.__new__(Refrel3Reader)
        t=r.translated(Window(0,'a','c',2,8,'0'*64))
        self.assertEqual((t['start0'],t['end0']),(2,8))
        self.assertEqual(t['api'],'hwa_rr3_fetch')
        self.assertEqual(t['convention'],'0-based-half-open')
    def test_missing_native_library_is_not_a_skip_or_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            ref={'path':'missing.so','bytes':0,'sha256':'0'*64}
            spec={'family':'refrel3','library':ref,'build_receipt':ref}
            with self.assertRaises(FileNotFoundError):_check_receipt(Path(d),spec)
    def test_failed_duplicate_q_cannot_be_hidden_by_later_pass(self):
        entries=[{'id':'bad','family':'refrel3','variant':'q4k','data_status':'PASS','verdict':'FAIL'},
                 {'id':'good','family':'refrel3','variant':'q4k','data_status':'PASS','verdict':'PASS'},
                 {'id':'q16','family':'refrel3','variant':'q16k','data_status':'PASS','verdict':'PASS'}]
        self.assertEqual(job.aggregate(entries)['refrel3_verdict'],'FAIL')


if __name__=='__main__':
    unittest.main()
