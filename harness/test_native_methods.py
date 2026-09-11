"""Native counter/batch protocol and configuration regression tests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_native_execution import FAKE, ROOT
from reader_environment import scope, parameters

EXTENSIONS=r'''
void hc_count_reset(void *p){(void)p;counted=0;}
uint64_t hc_count_bytes(void *p){(void)p;return counted;}
typedef struct {S *s;const uint64_t *off;size_t n,len;char *out;size_t written;} B;
void *hc_batch_open(void *s,const uint64_t *o,size_t n,size_t len,void *out){B *b=malloc(sizeof(*b));*b=(B){s,o,n,len,out,0};return b;}
void hc_batch_reset(void *p){((B*)p)->written=0;}
int64_t hc_batch_run(void *p,size_t n,int threads){B *b=p;if(threads!=1||n>b->n)return -1;for(size_t i=0;i<n;i++)memcpy(b->out+i*b->len,b->s->p+b->off[i],b->len);b->written=n;return n;}
int hc_batch_valid(void *p,size_t n){return !getenv("BAD_BATCH_STATUS") && ((B*)p)->written==n;}
void hc_batch_close(void *p){free(p);}
'''
class Methods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.d=Path(cls.temp.name)
        cls.original=cls.d/'input';cls.original.write_bytes(bytes(range(256))*2048)
        source='#include <stdint.h>\nstatic uint64_t counted;\n'+FAKE.replace('return n;','counted+=n;return n;')+EXTENSIONS
        (cls.d/'codec.c').write_text(source)
        cls.library=cls.d/'codec.so'
        subprocess.run(['gcc','-O2','-shared','-fPIC','-I'+str(ROOT/'harness'),str(cls.d/'codec.c'),'-o',str(cls.library)],check=True,capture_output=True)
        for name in ('native_measure','native_batch'):
            subprocess.run(['gcc','-O3','-Wall','-Wextra','-Werror',str(ROOT/'harness'/(name+'.c')),'-ldl','-o',str(cls.d/name)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_counter_pass_has_exact_counts_without_timings(self):
        run=subprocess.run([str(self.d/'native_measure'),str(self.library),str(self.original),str(self.original),'amplification',''],check=True,capture_output=True,text=True)
        rows=[json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(rows),200)
        self.assertTrue(all(r['decoded_bytes']==16384 and 'latency_ms' not in r for r in rows))
    def test_batch_matches_loop_and_rejects_bad_status(self):
        trace=self.d/'trace';trace.write_text(''.join(f'{i*31} 16384\n' for i in range(100)))
        command=[str(self.d/'native_batch'),str(self.library),str(self.original),str(self.original),'',str(trace),'100','batch']
        run=subprocess.run(command,check=True,capture_output=True,text=True)
        rows=[json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(rows),6)
        self.assertEqual({r['method'] for r in rows},{'batch','loop'})
        self.assertTrue(all(r['verified'] for r in rows))
        bad=subprocess.run(command,env=dict(os.environ,BAD_BATCH_STATUS='1'),capture_output=True)
        self.assertNotEqual(bad.returncode,0)
    def test_duplicate_labels_cannot_silently_replace_baseline(self):
        from native_results import rows
        manifest={'adapters':[{'plan':{'codec':'bgzip+htslib'}},{'plan':{'codec':'bgzip+htslib'}}]}
        with self.assertRaisesRegex(ValueError,'duplicate codec labels'):rows(manifest)

    def test_reader_scope_is_restored_after_failure(self):
        with patch.dict(os.environ,{'FSE_CHUNK':'old'}):
            with self.assertRaisesRegex(ValueError,'failure'):
                with scope({'reader_environment':{'FSE_CHUNK':'4096'}}):
                    self.assertEqual(os.environ['FSE_CHUNK'],'4096');raise ValueError('failure')
            self.assertEqual(os.environ['FSE_CHUNK'],'old')
        with self.assertRaisesRegex(ValueError,'loader'):
            parameters({'reader_environment':{'LD_PRELOAD':'bad'}})

if __name__=='__main__':unittest.main()
