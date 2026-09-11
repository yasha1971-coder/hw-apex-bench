import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from verify_native_extraction import ROOT, verify


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='extraction-test-', dir=ROOT/'.work')
        self.root = Path(self.tmp.name)
        manifest = json.loads((ROOT/'harness/native/extraction.json').read_text())
        paths = list(manifest['sources']) + ['results.jsonl', 'harness/native/extraction.json']
        paths += ['harness/native/'+c+'.inc' for c in manifest['fragments']]
        for name in paths:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            verify(self.root)

    def test_exact_copy(self):
        self.check()

    def test_changed_native_call(self):
        p = self.root/'harness/native/aceapex.inc'
        p.write_text(p.read_text().replace('start,span', 'start,span+1'))
        with self.assertRaisesRegex(ValueError, 'moved source changed'):
            self.check()

    def test_changed_timer_outside_fragment(self):
        p = self.root/'harness/region_latency.c'
        p.write_text(p.read_text().replace('CLOCK_MONOTONIC', 'CLOCK_REALTIME'))
        with self.assertRaisesRegex(ValueError, 'expanded source differs'):
            self.check()

    def test_injected_code_outside_fragment(self):
        p = self.root/'harness/native/bgzip.inc'
        p.write_text('int injected;\n'+p.read_text())
        with self.assertRaisesRegex(ValueError, 'outside fragment'):
            self.check()

    def test_changed_measurements(self):
        with (self.root/'results.jsonl').open('a') as f:
            f.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'measurements changed'):
            self.check()
