"""Manual real-release Pages deploy: workflow wiring and the offline site check it runs."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_site  # noqa: E402

GOLDEN = ROOT/'tests/fixtures/site/expected'


class PagesReal(unittest.TestCase):
    def test_workflow_is_manual_hash_checked_and_verified_before_deploy(self):
        text = (ROOT/'.github/workflows/pages-real.yml').read_text()
        flow = yaml.safe_load(text)
        trigger = flow.get('on', flow.get(True))
        self.assertEqual(set(trigger), {'workflow_dispatch'})
        self.assertEqual(set(trigger['workflow_dispatch']['inputs']), {'release_tag', 'site_sha256'})
        steps = ' '.join(str(s.get('run', '')) + str(s.get('uses', '')) for s in flow['jobs']['build']['steps'])
        order = [steps.index(k) for k in ('sha256sum -c', "filter='data'", 'tools.verify_site', 'upload-pages-artifact')]
        self.assertEqual(order, sorted(order))
        self.assertEqual(flow['jobs']['deploy']['needs'], 'build')
        self.assertEqual(flow['permissions'], {})
        self.assertIn("github.ref == 'refs/heads/main'", flow['jobs']['deploy']['if'])

    def test_verify_site_refuses_synthetic_or_tampered_site(self):
        with tempfile.TemporaryDirectory() as t:
            site = Path(t)/'site'
            shutil.copytree(GOLDEN, site)
            # A synthetic release never deploys.
            with self.assertRaisesRegex(ValueError, 'PAGES_DEPLOY_SKIPPED'):
                verify_site.verify(site)
            tree, _ = verify_site.check_sums(site)
            with self.assertRaisesRegex(ValueError, 'tree SHA-256'):
                verify_site.verify(site, '0'*64)
            page = site/'index.html'
            page.write_bytes(page.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                verify_site.check_sums(site)
            self.assertEqual(len(tree), 64)


if __name__ == '__main__':
    unittest.main()
