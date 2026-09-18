"""Test public routing without loading Python harnesses or executing codecs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ('ACEAPEX_BS', 'LIT_CHUNK', 'FSE_CHUNK', 'MIN_MATCH', 'LIT_LEVEL',
             'LIT_LANES', 'NO_REP', 'DIRECT8', 'FORCED_BIN', 'ACEAPEX_DUMP')


class EntryPoints(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'run.sh').write_bytes((ROOT / 'run.sh').read_bytes())
        self.marker = self.root / 'python-called'
        fake = self.root / 'python3'
        fake.write_text('#!/bin/sh\n'
                        'printf "%s\\n" "$@" > "$HWB_TEST_MARKER"\n'
                        'env > "$HWB_TEST_MARKER.env"\n'
                        'exit 91\n')
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:' + os.environ['PATH'],
                        HWB_TEST_MARKER=str(self.marker))
        self.env.update({name: 'unexpected-override' for name in OVERRIDES})

    def invoke(self, args):
        self.marker.unlink(missing_ok=True)
        return subprocess.run(['bash', str(self.root / 'run.sh'), *args],
                              env=self.env, cwd=self.root, capture_output=True,
                              text=True, timeout=5)

    def test_help_and_invalid_arguments_never_dispatch(self):
        cases = [(['--help'], 0), (['-h'], 0), (['--typo'], 2),
                 (['--codec'], 2), (['--stage'], 2), (['--stage', '0'], 2),
                 (['--stage', '6'], 2), (['--stage', '1', 'extra'], 2)]
        for args, code in cases:
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn('--', result.stdout + result.stderr)
                self.assertFalse(self.marker.exists(), 'Python dispatcher was invoked')
                self.assertFalse((self.root / '.work').exists())

    def test_existing_commands_forward_exact_arguments_and_clear_overrides(self):
        routes = {'--check': 'check_adapter.py', '--plan': 'axis_planner.py',
                  '--measure': 'native_execution.py', '--audit-axes': 'axes.py',
                  '--default-refresh': 'default_refresh.py', '--cg-curve': 'cg_curve.py'}
        cases = [([], ['harness/stage1.py'])]
        cases.extend((['--stage', str(n)], ['harness/stage1.py', '--stage', str(n)])
                     for n in range(1, 6))
        # Spaces and shell syntax must be passed literally, never evaluated.
        tail = ['--input', 'a file $(touch injected).bin', '--output-dir', 'out dir']
        cases.extend(([option, *tail], ['harness/' + script, *tail])
                     for option, script in routes.items())
        for args, expected in cases:
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result.returncode, 91, result.stderr)
                self.assertEqual(self.marker.read_text().splitlines(), expected)
                passed_env = dict(line.split('=', 1) for line in
                                  Path(str(self.marker) + '.env').read_text().splitlines()
                                  if '=' in line)
                for name in (*OVERRIDES, 'LD_PRELOAD'):
                    self.assertNotIn(name, passed_env)
                self.assertFalse((self.root / 'injected').exists())
                self.assertFalse((self.root / '.work').exists())


if __name__ == '__main__':
    unittest.main()
