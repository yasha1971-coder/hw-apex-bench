"""Small synthetic contract tests; these are not benchmark results."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import cg_curve as cg


def fixture():
    rows = []
    samples = [dict(query=i,byte_offset=i*17,requested_bytes=16384,verified=True,latency_ms=(i+1)/1000) for i in range(200)]
    for codec in cg.CODECS:
        b = dict(total_bytes=1000,ratio=cg.CORPUS_SIZE/1000,full_restore_byte_equal=True,
                 restore_md5='9465e0f0df6e2c6eb39729c39cee5465',commands=['baseline'],geometry={'num_blocks':1}) if codec != cg.CODECS[2] else None
        for g in cg.GRID:
            p = dict(total_bytes=1100,ratio=cg.CORPUS_SIZE/1100,full_restore_byte_equal=True,
                     restore_md5='9465e0f0df6e2c6eb39729c39cee5465',commands=['blocked'],archive_sha256='test-only',
                     geometry={'actual_max_block_bytes':g},region_samples=copy.deepcopy(samples),p50_ms=.100,p99_ms=.198)
            if codec == cg.CODECS[2] and g > 65536: p = None
            rows.append(dict(evidence_group=cg.GROUP,run_id='unit-test-only',benchmark_commit='test-only',codec=codec,g=g,
                formula=cg.FORMULA,corpus=dict(bytes=cg.CORPUS_SIZE,md5='9465e0f0df6e2c6eb39729c39cee5465'),
                configuration={'encoder_threads':8 if codec==cg.CODECS[0] else 1},
                point=p,baseline=copy.deepcopy(b),value=cg.loss(1100,1000) if b else None,
                status='measured' if b else 'n/a',reason=None if b else 'format limit',
                versions={'aceapex_sha':cg.ACEAPEX_SHA,'zstd_sha':cg.ZSTD_SHA},source_provenance={},hardware={}))
    return rows


class Contract(unittest.TestCase):
    def test_valid(self):
        r = fixture()
        self.assertEqual(cg.validate(r),r)
        self.assertIn('Raw points',cg.render(r))
    def test_ratio_loss_is_not_archive_increase(self):
        self.assertAlmostEqual(cg.loss(110,100),100/11)
        self.assertNotAlmostEqual(cg.loss(110,100),10)
    def test_negative_cost_and_reversal_retained(self):
        rows = fixture()
        r=rows[1];r['point']['total_bytes']=900;r['point']['ratio']=cg.CORPUS_SIZE/900
        r['value']=cg.loss(900,1000)
        cg.validate(rows)
        self.assertIn('-11.111111',cg.render(rows))
    def test_incomplete_grid(self):
        with self.assertRaises(ValueError): cg.validate(fixture()[:-1])
    def test_duplicate(self):
        r=fixture();r[1]=copy.deepcopy(r[0])
        with self.assertRaises(ValueError): cg.validate(r)
    def test_changed_threads(self):
        r=fixture();r[1]['configuration']['encoder_threads']=1
        with self.assertRaises(ValueError): cg.validate(r)
    def test_changed_baseline(self):
        r=fixture();r[1]['baseline']['commands']=['different binary']
        with self.assertRaises(ValueError): cg.validate(r)
    def test_bgzf_no_fictitious_number(self):
        r=fixture();r[-1]['value']=0
        with self.assertRaises(ValueError): cg.validate(r)
    def test_bgzf_no_oversized_block(self):
        r=fixture();r[-1]['point']=copy.deepcopy(r[0]['point'])
        with self.assertRaises(ValueError): cg.validate(r)
    def test_wrong_trace(self):
        r=fixture();r[1]['point']['region_samples'][0]['byte_offset']+=1
        with self.assertRaises(ValueError): cg.validate(r)
    def test_wrong_p99(self):
        r=fixture();r[0]['point']['p99_ms']=.199
        with self.assertRaises(ValueError): cg.validate(r)
    def test_wrong_cg(self):
        r=fixture();r[0]['value']=.41
        with self.assertRaises(ValueError): cg.validate(r)
    def test_unverified_restore(self):
        r=fixture();r[0]['baseline']['full_restore_byte_equal']=False
        with self.assertRaises(ValueError): cg.validate(r)
    def test_mixed_run(self):
        r=fixture();r[0]['run_id']='other'
        with self.assertRaises(ValueError): cg.validate(r)
    def test_clean_env(self):
        env={'PATH':'x','ACEAPEX_BS':'1','ACEAPEX_NEW_OVERRIDE':'yes','HASH_LOG':'9','LIT_CHUNK':'3','ZSTD_CLEVEL':'22'}
        self.assertEqual(cg.clean_env(env),{'PATH':'x'})


class Geometry(unittest.TestCase):
    def test_seek_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic'
            entries=[(5,4,0),(6,4,0),(3,2,0)]
            p.write_bytes(b'x'*14+struct.pack('<II',0x184D2A5E,45)+b''.join(struct.pack('<III',*e) for e in entries)+struct.pack('<IBI',3,128,0x8F92EAB1))
            r=cg.seek_geometry(p,10,4)
            self.assertEqual(r['actual_max_block_bytes'],4)
            self.assertEqual(r['seek_table_bytes'],53)
            with self.assertRaises(ValueError): cg.seek_geometry(p,10,8)
    def test_bgzf_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic'
            def block(n):
                return bytes.fromhex('1f8b08040000000000ff060042430200')+struct.pack('<H',27)+b'\0\0'+struct.pack('<II',0,n)
            p.write_bytes(block(4)+block(4)+block(2)+block(0))
            self.assertEqual(cg.bgzf_geometry(p,10,4)['num_blocks'],3)
            with self.assertRaises(ValueError): cg.bgzf_geometry(p,10,2)


if __name__ == '__main__': unittest.main()
