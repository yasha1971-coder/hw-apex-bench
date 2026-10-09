"""Pages deploy gate: deploy from main only with measured/official evidence; synthetic-only releases are skipped."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import pages_deploy_gate as gate  # noqa: E402


def site(root, kinds, mode='real'):
    d = Path(root) / 'downloads'
    d.mkdir(parents=True)
    tables = [{'id': f't{i}', 'conditions': {'kind': k}, 'rows': [{'kind': k, 'format': 'f', 'variant': str(i)}]}
              for i, k in enumerate(kinds)]
    (d / 'leaderboard.json').write_text(json.dumps({'schema': 'leaderboard-v1', 'tables': tables}))
    (d / 'RELEASE_MANIFEST.json').write_text(json.dumps({'schema': 'release-manifest-v1', 'mode': mode, 'artifacts': []}))
    return Path(root)


class PagesDeployGate(unittest.TestCase):
    def test_synthetic_only_is_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            deploy, measured, line = gate.decide(site(t, ['synthetic'] * 5, mode='synthetic'))
            self.assertFalse(deploy)
            self.assertEqual(measured, 0)
            self.assertIn('PAGES_DEPLOY_SKIPPED', line)

    def test_measured_row_in_real_release_deploys(self):
        with tempfile.TemporaryDirectory() as t:
            deploy, measured, line = gate.decide(site(t, ['synthetic', 'measured']))
            self.assertTrue(deploy)
            self.assertEqual(measured, 1)
            self.assertIn('deploy=true', line)

    def test_official_row_deploys(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(gate.decide(site(t, ['official']))[0])

    def test_measured_label_in_synthetic_release_is_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertFalse(gate.decide(site(t, ['measured'], mode='synthetic'))[0])

    def test_missing_or_malformed_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(OSError):
                gate.decide(Path(t))
            root = site(t, ['measured'])
            (root / 'downloads' / 'RELEASE_MANIFEST.json').write_text('{"schema": "other", "mode": "real"}')
            with self.assertRaises(ValueError):
                gate.decide(root)

    def test_cli_writes_github_output_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root = site(Path(t) / 's', ['synthetic'])
            out = Path(t) / 'gh_output'
            cp = subprocess.run([sys.executable, '-m', 'tools.pages_deploy_gate', str(root), '--github-output', str(out)],
                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertIn('PAGES_DEPLOY_SKIPPED', cp.stdout)
            self.assertEqual(out.read_text(), 'deploy=false\nmeasured_rows=0\n')
            cp = subprocess.run([sys.executable, '-m', 'tools.pages_deploy_gate', str(Path(t) / 'missing'),
                                 '--github-output', str(Path(t) / 'gh2')], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(cp.returncode, 1)
            self.assertFalse((Path(t) / 'gh2').exists())

    def test_workflow_wires_the_gate(self):
        text = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('python" -m tools.pages_deploy_gate', text)
        self.assertIn("steps.deploy-gate.outputs.deploy == 'true'", text)
        self.assertIn("needs.build.outputs.deploy == 'true'", text)


if __name__ == '__main__':
    unittest.main()
