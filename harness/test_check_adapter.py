import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from check_adapter import check
from resident_probe import AXES, capabilities

class CheckContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.adapter=self.root/'external.sh'
        self.work=self.root/'work'
    def tearDown(self): self.tmp.cleanup()
    def adapter_text(self, wrong=False, omit=False):
        missing={axis:'not implemented by this CLI-only fixture' for axis in AXES if axis!='decode'}
        from check_adapter import ROOT
        return f'''#!/usr/bin/env bash
set -euo pipefail
source "{ROOT}/harness/check_common.sh"
codec_name() {{ echo external-identity; }}
codec_version() {{ echo 1; }}
codec_supports() {{ echo decode; }}
codec_unavailable() {{ echo '{json.dumps(missing)}'; }}
codec_build() {{ :; }}
codec_compress() {{ cp -- "$1" "$2"; }}
codec_decompress() {{ {'printf bad > "$2"' if wrong else 'cp -- "$1" "$2"'}; }}
{'unset -f codec_region' if omit else ''}
if [[ "${{BASH_SOURCE[0]}}" != "$0" ]]; then return; fi
hb_entry "$@"
case "$1" in
 supports) codec_supports;;
 unavailable) codec_unavailable;;
 *) exit 2;;
esac
'''
    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()): check(self.adapter,self.work)
    def test_external_cli_only_adapter_without_native_library(self):
        self.adapter.write_text(self.adapter_text())
        self.execute()
        r=json.loads((self.work/'check.json').read_text())
        self.assertEqual(r['codec'],'external-identity')
        self.assertEqual(len(r['cases']),5)
        self.assertIsNone(r['native_library_sha256'])
    def test_bad_restore_never_receives_success_receipt(self):
        self.adapter.write_text(self.adapter_text(wrong=True))
        self.work.mkdir(); (self.work/'check.json').write_text('{"status":"pass"}')
        with self.assertRaisesRegex(ValueError,'CLI full restore differs'): self.execute()
        self.assertFalse((self.work/'check.json').exists())
    def test_missing_required_function_rejected_before_build(self):
        self.adapter.write_text(self.adapter_text(omit=True))
        with self.assertRaisesRegex(RuntimeError,'command failed'): self.execute()
        self.assertFalse((self.work/'check.json').exists())
    def test_concurrent_check_cannot_replace_receipt(self):
        self.adapter.write_text(self.adapter_text())
        self.work.mkdir()
        receipt=self.work/'check.json'; receipt.write_text('previous completed check')
        with (self.work/'check.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError,'another check owns'): self.execute()
        self.assertEqual(receipt.read_text(),'previous completed check')
    def test_empty_na_reason_rejected(self):
        text=self.adapter_text().replace('not implemented by this CLI-only fixture','')
        self.adapter.write_text(text)
        with self.assertRaisesRegex(ValueError,'nonempty reason'): capabilities(self.adapter)

if __name__=='__main__': unittest.main()
