import unittest
from adapters import validate_metadata, AXES


class ContractTests(unittest.TestCase):
    def test_minimal(self):
        validate_metadata(['ratio', 'decode'], {a: 'not implemented' for a in AXES if a not in ('ratio', 'decode')})

    def test_missing_reason(self):
        with self.assertRaises(ValueError):
            validate_metadata(['ratio', 'decode'], {})

    def test_blank_reason(self):
        with self.assertRaises(ValueError):
            validate_metadata(['ratio', 'decode'], {a: ' ' for a in AXES if a not in ('ratio', 'decode')})

    def test_duplicate_capability(self):
        with self.assertRaises(ValueError):
            validate_metadata(['ratio', 'ratio', 'decode'], {})

    def test_unknown_capability(self):
        with self.assertRaises(ValueError):
            validate_metadata(['ratio', 'decode', 'fast'], {})

    def test_derived_axis_needs_region(self):
        supported = ['ratio', 'decode', 'h_alpha']
        with self.assertRaises(ValueError):
            validate_metadata(supported, {a: 'no API' for a in AXES if a not in supported})

    def test_cannot_explain_supported_axis_as_unavailable(self):
        with self.assertRaises(ValueError):
            validate_metadata(list(AXES), {'ratio': 'no API'})


if __name__ == '__main__':
    unittest.main()

class NativeContractTests(unittest.TestCase):
    """An independent tiny plugin proves rejection at the actual ABI boundary."""
    def test_native_rejections(self):
        import json
        from pathlib import Path
        import subprocess
        import tempfile
        from adapters import ROOT
        source = r'''
#include "adapter_api.h"
static void *op(const char*p,uint64_t n){return 0;}
static uint64_t sz(void*p){return 0;}
static int64_t dec(void*p,void*d,size_t n){return 0;}
static void cl(void*p){}
const cb_api*cabench_adapter_v1(void){
static const cb_api a={VER,sizeof(cb_api),"outside-codecs","1","one",CAP,
0,op,sz,dec,0,0,0,0,0,cl};return &a;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); (tmp/'plugin.c').write_text(source)
            subprocess.run(['gcc','-O2',str(ROOT/'harness/adapter_worker.c'),'-ldl','-o',str(tmp/'worker')], check=True, capture_output=True)
            for version, caps, passes in [(1,5,True),(2,5,False),(1,13,False),(1,7,False),(1,1029,False)]:
                with self.subTest(version=version, caps=caps):
                    subprocess.run(['gcc','-shared','-fPIC','-I'+str(ROOT/'harness'),f'-DVER={version}',f'-DCAP={caps}',str(tmp/'plugin.c'),'-o',str(tmp/'plugin.so')], check=True, capture_output=True)
                    r=subprocess.run([str(tmp/'worker'),str(tmp/'plugin.so'),'probe'],capture_output=True,text=True)
                    self.assertEqual(r.returncode==0,passes,r.stderr)
                    if passes:self.assertEqual(json.loads(r.stdout)['name'],'outside-codecs')
