"""Worker integration: a new native codec needs no worker-side dispatch changes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from native_execution import samples

ROOT=Path(__file__).resolve().parents[1]
FAKE=r'''
#include "resident_context.h"
#include <stdlib.h>
#include <string.h>
typedef struct {const char *p; size_t n;} S;
unsigned hc_abi(void){return 2;}
uint64_t hc_size(void *p){return ((S*)p)->n;}
void *hc_open(const void *p,size_t n,const char *s,uint64_t expected){
 (void)s;(void)expected; S *c=malloc(sizeof(*c)); *c=(S){p,n};return c;
}
int64_t hc_region(void *p,uint64_t o,void *out,size_t n){
 S *s=p;if(!hc_bounds(s->n,o,n))return -1;memcpy(out,s->p+o,n);
 if(getenv("BAD_BYTES") && n) ((char*)out)[0]^=1;
 if(getenv("BAD_GUARD")) ((char*)out)[n]=0;
 return n;
}
int64_t hc_decode(void *p,void *out,size_t n){return hc_region(p,0,out,n);}
void hc_close(void *p){free(p);}
'''
class NativeWorkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.d=Path(cls.temp.name)
        cls.worker=cls.d/'worker';cls.lib=cls.d/'identity.so'
        (cls.d/'identity.c').write_text(FAKE)
        for command in (
            ['gcc','-O3','-Wall','-Wextra','-Werror',str(ROOT/'harness/native_measure.c'),'-ldl','-o',str(cls.worker)],
            ['gcc','-O3','-shared','-fPIC','-I'+str(ROOT/'harness'),str(cls.d/'identity.c'),'-o',str(cls.lib)]):
            subprocess.run(command,check=True,capture_output=True)
        cls.original=cls.d/'input';cls.original.write_bytes(bytes(range(256))*2048)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def run_worker(self,phase,env=None,extra=()):
        return subprocess.run([str(self.worker),str(self.lib),str(self.original),str(self.original),phase,'',*extra],
                              capture_output=True,text=True,env=env)
    def test_workload_and_verification(self):
        for phase,count in [('region',200),('decode',5)]:
            run=self.run_worker(phase);self.assertEqual(run.returncode,0,run.stderr)
            path=self.d/(phase+'.jsonl');path.write_text(run.stdout)
            self.assertEqual(len(samples(path,phase,self.original.stat().st_size)),count)
    def test_wrong_bytes_and_guard_are_fatal(self):
        import os
        for flag in ('BAD_BYTES','BAD_GUARD'):
            for phase in ('region','decode'):
                run=self.run_worker(phase,dict(os.environ,**{flag:'1'}))
                self.assertNotEqual(run.returncode,0)
                self.assertEqual(run.stdout,'')
    def test_verification_only_and_invalid_repeats(self):
        run=self.run_worker('decode',extra=('0',))
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout,'')
        for extra in ('no','21','-1'):
            self.assertNotEqual(self.run_worker('decode',extra=(extra,)).returncode,0)
    def test_incomplete_or_changed_workload_rejected(self):
        run=self.run_worker('region');path=self.d/'bad.jsonl'
        rows=run.stdout.splitlines();path.write_text('\n'.join(rows[:-1]))
        with self.assertRaisesRegex(ValueError,'incomplete'): samples(path,'region',self.original.stat().st_size)
        row=json.loads(rows[0]);row['byte_offset']+=1;rows[0]=json.dumps(row)
        path.write_text('\n'.join(rows))
        with self.assertRaisesRegex(ValueError,'workload'): samples(path,'region',self.original.stat().st_size)

class ExternalRatioTest(unittest.TestCase):
    def test_cli_codec_ratio_counts_required_sidecar_without_native_library(self):
        import contextlib
        import io
        from check_adapter import check
        from axis_planner import plan_adapter, dispatch_adapter
        from native_execution import NativeExecution
        from resident_probe import AXES
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);adapter=root/'external.sh';work=root/'build'
            missing={axis:'fixture has no such API' for axis in AXES if axis!='ratio'}
            adapter.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
source "{ROOT}/harness/check_common.sh"
codec_name() {{ echo external-identity-indexed; }}
codec_version() {{ echo 1; }}
codec_supports() {{ echo ratio; }}
codec_unavailable() {{ echo '{json.dumps(missing)}'; }}
codec_build() {{ :; }}
codec_compress() {{ cp -- "$1" "$2"; printf IDX > "$2.idx"; }}
codec_decompress() {{ cp -- "$1" "$2"; }}
codec_artifacts() {{ python3 -c 'import json,sys; print(json.dumps([sys.argv[1],sys.argv[1]+".idx"]))' "$1"; }}
hb_entry "$@"
case "$1" in
 supports) codec_supports;;
 unavailable) codec_unavailable;;
esac
''')
            with contextlib.redirect_stdout(io.StringIO()): check(adapter,work)
            original=root/'input';original.write_bytes(b'hello')
            destination=root/'run';destination.mkdir()
            runner=NativeExecution(root/'unused-worker',original,destination)
            result=dispatch_adapter(plan_adapter(adapter,work,['ratio']),runner.handlers())[0]['value']
            self.assertEqual(result['archive_bytes'],8)
            self.assertEqual(result['ratio'],5/8)
            self.assertEqual(result['verified'],'byte-exact')
            self.assertEqual(len(result['archive_artifacts']),2)

if __name__=='__main__': unittest.main()
