"""A10 static HTML, source integrity, golden bytes, contrast and Pages policy."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import html5lib
import jsonschema
import yaml

from review.axis3.verdict_data import load_json
from tools import build_site as job
from tools import site_synthetic, release_v020

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO/'tests/fixtures/site/expected'


class Site(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root/'release'
        shutil.copytree(GOLDEN/'downloads/release', self.release)
        self.out = self.root/'site'

    def build(self, output=None, **kwargs):
        return job.build(self.release, output or self.out, **kwargs)

    def write(self, path, value):
        path.write_bytes(release_v020.encoded(value))

    def edit(self, path, callback):
        data = load_json(path)
        callback(data)
        self.write(path, data)

    def rehash(self):
        manifest = load_json(self.release/'RELEASE_MANIFEST.json')
        for r in manifest['artifacts']:
            p = self.release/r['path']
            r.update(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.write(self.release/'RELEASE_MANIFEST.json', manifest)

    def rejects(self, message=None):
        with self.assertRaises((ValueError, FileNotFoundError, jsonschema.ValidationError)) as ctx:
            self.build()
        if message:
            self.assertIn(message, str(ctx.exception))
        self.assertFalse(self.out.exists())

    def test_exact_complete_golden_site(self):
        receipt = self.build()
        self.assertEqual(site_synthetic.snapshot(self.out), site_synthetic.snapshot(GOLDEN))
        self.assertEqual((receipt['html_pages'], receipt['rows']), (10, 5))

    def test_repeated_site_byte_determinism(self):
        first = self.build()
        other = self.root/'other'
        second = self.build(other)
        self.assertEqual(first, second)
        self.assertEqual(site_synthetic.snapshot(self.out), site_synthetic.snapshot(other))

    def test_relocated_input_byte_determinism(self):
        first = self.build()
        relocated = self.root/'relocated'
        shutil.copytree(self.release, relocated)
        second = job.build(relocated, self.root/'other')
        self.assertEqual(first, second)
        self.assertEqual(site_synthetic.snapshot(self.out), site_synthetic.snapshot(self.root/'other'))

    def test_all_generated_html5_documents_have_no_parser_errors(self):
        self.build()
        for p in self.out.rglob('*.html'):
            parser = html5lib.HTMLParser(namespaceHTMLElements=False)
            tree = parser.parse(p.read_text())
            self.assertFalse(parser.errors, (p.name, parser.errors))
            self.assertEqual(tree.get('lang'), 'en')
            self.assertIsNotNone(tree.find('.//title'))
            self.assertIsNotNone(tree.find('.//main'))

    def test_every_internal_file_and_fragment_exists(self):
        self.build()
        result = job.validate_site(self.out)
        self.assertEqual(result['internal_links'], 'PASS')
        self.assertGreater(result['links'], 0)

    def test_no_js_or_external_resource_libraries(self):
        with mock.patch('socket.socket.connect', side_effect=AssertionError('network')), \
             mock.patch('urllib.request.urlopen', side_effect=AssertionError('network')), \
             mock.patch('time.time', side_effect=AssertionError('clock')), \
             mock.patch('tools.axis4.open_reader', side_effect=AssertionError('native')):
            self.build()
        for p in self.out.rglob('*.html'):
            tree = html5lib.parse(p.read_text(), namespaceHTMLElements=False)
            self.assertFalse(list(tree.iter('script')))
            for e in tree.iter():
                self.assertFalse(any(k.startswith('on') for k in e.attrib))
        self.assertFalse(list(self.out.rglob('*.js')))
        self.assertIn('prefers-color-scheme: dark', (self.out/'assets/site.css').read_text())

    def test_semantic_result_tables_and_keyboard_access(self):
        self.build()
        tree = html5lib.parse((self.out/'index.html').read_text(), namespaceHTMLElements=False)
        for table in tree.iter('table'):
            self.assertIsNotNone(table.find('caption'))
            self.assertTrue(all(e.get('scope') in ('row', 'col') for e in table.iter('th')))
        self.assertTrue(any(e.get('tabindex')=='0' and e.get('aria-label') for e in tree.iter('div')))
        self.assertTrue(any(e.get('href')=='#main' for e in tree.iter('a')))
        synthetic = copy.deepcopy(load_json(self.release/'leaderboard.json')['tables'][0])
        synthetic['rows'][0]['status'] = 'DIAGNOSTIC_ONLY'
        text = job.table('index.html', synthetic)
        self.assertRegex(text, r'class="muted" data-field="status"[^>]*>DIAGNOSTIC_ONLY')

    def test_light_dark_text_contrast_AA(self):
        def luminance(value):
            channels = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
            channels = [v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in channels]
            return sum(a*b for a, b in zip(channels, (0.2126, 0.7152, 0.0722)))
        for theme, colors in job.COLORS.items():
            for bg in ('background', 'surface'):
                for fg in ('text', 'muted', 'link', 'pass', 'fail'):
                    a, b = sorted([luminance(colors[bg]), luminance(colors[fg])])
                    self.assertGreaterEqual((b+0.05)/(a+0.05), 4.5, (theme, bg, fg))
                for fg in ('border', 'focus'):
                    a, b = sorted([luminance(colors[bg]), luminance(colors[fg])])
                    self.assertGreaterEqual((b+0.05)/(a+0.05), 3, (theme, bg, fg))

    def test_every_row_page_preserves_all_evidence_fields(self):
        self.build()
        board = load_json(self.release/'leaderboard.json')
        for table in board['tables']:
            for row in table['rows']:
                page = self.out/'rows'/job.row_id(row)/'index.html'
                tree = html5lib.parse(page.read_text(), namespaceHTMLElements=False)
                source = load_json(self.release/row['evidence'])
                self.assertIn(job.pretty(source), [''.join(e.itertext()) for e in tree.iter('pre')])
                self.assertIn(row['evidence_sha256'], ''.join(tree.itertext()))
                self.assertIn('python3 -m tools.release_v020 --verify site/downloads/release', page.read_text())
                self.assertIn('python3 -m tools.build_site', page.read_text())

    def test_downloads_are_exact_verified_bytes(self):
        self.build()
        for name in ('leaderboard.csv', 'leaderboard.json', 'RELEASE_MANIFEST.json'):
            self.assertEqual((self.out/'downloads'/name).read_bytes(), (self.release/name).read_bytes())
        self.assertEqual(site_synthetic.snapshot(self.out/'downloads/release'), site_synthetic.snapshot(self.release))

    def test_axis_pages_have_methodology_definitions_and_criteria(self):
        self.build()
        expected = {3: ('c0', 'model-B', 'canonical'), 4: ('32', 'FASTA', 'SHA'),
                    5: ('silent_error', 'watchdog', 'synthetic evidence only')}
        for axis, terms in expected.items():
            tree = html5lib.parse((self.out/'axes'/str(axis)/'index.html').read_text(), namespaceHTMLElements=False)
            text = ' '.join(''.join(tree.itertext()).split())
            for term in terms:
                self.assertIn(term, text)

    def test_missing_machine_not_imputed_and_synthetic_not_performance(self):
        self.build()
        text = (self.out/'index.html').read_text()
        self.assertIn('Synthetic evidence establishes correctness, not performance', text)
        self.assertIn('Not recorded', text)
        self.assertNotIn('data-field="p50_us"', text)
        self.assertNotIn('data-field="seconds"', text)

    def test_missing_artifact_refused(self):
        (self.release/'leaderboard.csv').unlink()
        self.rejects('missing/extra artifact')

    def test_changed_manifest_hash_refused(self):
        self.edit(self.release/'RELEASE_MANIFEST.json', lambda d: d['artifacts'][0].update(sha256='0'*64))
        self.rejects('frozen file changed')

    def test_wrong_manifest_schema_refused(self):
        self.edit(self.release/'RELEASE_MANIFEST.json', lambda d: d.update(schema='unknown'))
        self.rejects()

    def test_external_manifest_anchor_refused(self):
        with self.assertRaisesRegex(ValueError, 'external SHA'):
            self.build(expected_manifest_sha256='0'*64)
        self.assertFalse(self.out.exists())

    def test_rehashed_number_without_evidence_refused(self):
        self.edit(self.release/'leaderboard.json', lambda d: d['tables'][0]['rows'][0].update(verified=123456))
        self.rehash()
        self.rejects('leaderboard does not match')

    def test_rehashed_extra_metric_refused(self):
        self.edit(self.release/'leaderboard.json', lambda d: d['tables'][0]['rows'][0].update(invented_metric=123))
        self.rehash()
        self.rejects('leaderboard does not match')

    def test_valid_manifest_but_missing_methodology_link_refused(self):
        path = self.release/'metadata/METHODOLOGY.md'
        path.write_text(path.read_text()+'\n[missing](nonexistent.json)\n')
        self.rehash()
        release_v020.verify(self.release)
        self.rejects()

    def test_missing_axis_methodology_section_refused(self):
        path = self.release/'metadata/METHODOLOGY.md'
        path.write_text(path.read_text().replace('## Axis 4:', '## Removed Axis 4:'))
        self.rehash()
        self.rejects('missing Axis 4 methodology')

    def test_injected_numeric_cell_without_provenance_rolls_back(self):
        original = job.table
        def bad(*args):
            return original(*args).replace('</tr></tbody>', '<td>999</td></tr></tbody>')
        with mock.patch.object(job, 'table', side_effect=bad):
            self.rejects('number without evidence')

    def test_changed_numeric_cell_with_forged_source_marker_rolls_back(self):
        original = job.table
        def bad(*args):
            result = original(*args)
            return re.sub(r'(data-field="verified"[^>]*>)\d+', r'\g<1>123456', result)
        with mock.patch.object(job, 'table', side_effect=bad):
            self.rejects('does not match evidence')

    def test_unsafe_methodology_scheme_refused(self):
        path = self.release/'metadata/METHODOLOGY.md'
        path.write_text(path.read_text()+'\n[unsafe](javascript:alert%281%29)\n')
        self.rehash()
        self.rejects('unsafe methodology')

    def test_external_image_refused(self):
        path = self.release/'metadata/METHODOLOGY.md'
        path.write_text(path.read_text()+'\n![remote](https://example.org/image.png)\n')
        self.rehash()
        self.rejects('external image')

    def test_raw_html_in_methodology_is_inert(self):
        path = self.release/'metadata/METHODOLOGY.md'
        path.write_text('<script>alert(1)</script>\n'+path.read_text())
        self.rehash()
        self.build()
        self.assertEqual(job.validate_site(self.out)['HTML5'], 'PASS')
        self.assertNotIn('<script>', (self.out/'axes/3/index.html').read_text())
        self.assertIn('&lt;script&gt;', (self.out/'axes/3/index.html').read_text())

    def test_valid_release_with_active_html_artifact_refused(self):
        path = self.release/'metadata/active.html'
        path.write_text('<!doctype html><script>alert(1)</script>')
        manifest = load_json(self.release/'RELEASE_MANIFEST.json')
        record = copy.deepcopy(next(r for r in manifest['artifacts'] if r['role']=='metadata'))
        record.update(path='metadata/active.html', bytes=path.stat().st_size,
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest['artifacts'].append(record)
        manifest['artifacts'].sort(key=lambda r: r['path'])
        self.write(self.release/'RELEASE_MANIFEST.json', manifest)
        release_v020.verify(self.release)
        self.rejects('active web artifact')

    def test_external_stylesheet_in_generated_html_rolls_back(self):
        original = job.document
        def bad(*args):
            return original(*args).replace(b'</head>', b'<link rel="stylesheet" href="https://example.org/cdn.css"></head>')
        with mock.patch.object(job, 'document', side_effect=bad):
            self.rejects('external resource')

    def test_minimal_A9_release_requires_link_closure(self):
        from tools import release_synthetic
        config = release_synthetic.prepare(self.root/'minimal-input')
        path = self.root/'minimal-release'
        release_v020.release(config, path)
        release_v020.verify(path)
        with self.assertRaises(FileNotFoundError):
            job.build(path, self.out)
        self.assertFalse(self.out.exists())

    def test_synthetic_RUN_snapshot_preserves_server_overlay(self):
        fake = self.root/'server-overlay-RUN.md'
        fake.write_bytes(b'Server AGC overlay, not the historical synthetic input')
        original = release_v020.leaderboard.relative
        def overlay(root, name):
            return fake if name == 'review/axis3/RUN.md' and Path(root)==REPO else original(root, name)
        with mock.patch.object(release_v020.leaderboard, 'relative', side_effect=overlay):
            site_synthetic.prepare(self.root/'frozen-input')
        actual = self.root/'frozen-input/review/axis3/RUN.md'
        self.assertEqual(hashlib.sha256(actual.read_bytes()).hexdigest(), site_synthetic.PINNED_RUN_SHA)
        self.assertEqual(fake.read_bytes(), b'Server AGC overlay, not the historical synthetic input')

    def test_existing_output_refused(self):
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError, 'new and disjoint'):
            self.build()

    def test_output_inside_release_refused(self):
        with self.assertRaisesRegex(ValueError, 'new and disjoint'):
            self.build(self.release/'site')

    def test_input_symlink_refused(self):
        (self.release/'alias').symlink_to(self.release/'leaderboard.csv')
        self.rejects('symlink')

    def test_missing_generated_link_rolls_back(self):
        original = job.document
        def bad(*args):
            return original(*args).replace(b'</main>', b'<a href="missing.html">missing</a></main>')
        with mock.patch.object(job, 'document', side_effect=bad):
            self.rejects()

    def test_missing_fragment_rolls_back(self):
        original = job.document
        def bad(*args):
            return original(*args).replace(b'href="#main"', b'href="#missing"')
        with mock.patch.object(job, 'document', side_effect=bad):
            self.rejects('missing internal fragment')

    def test_invalid_html5_rolls_back(self):
        original = job.document
        def bad(*args):
            return original(*args).replace(b'</main>', b'<div></span></main>')
        with mock.patch.object(job, 'document', side_effect=bad):
            with self.assertRaises(html5lib.html5parser.ParseError):
                self.build()
        self.assertFalse(self.out.exists())

    def test_changed_release_during_build_rolls_back(self):
        original = job.validate_site
        def changed(*args):
            result = original(*args)
            p = self.release/'metadata/CHANGELOG.md'
            p.write_bytes(p.read_bytes()+b'\nchanged\n')
            return result
        with mock.patch.object(job, 'validate_site', side_effect=changed):
            self.rejects('release changed')

    def test_cli_site_build(self):
        result = subprocess.run([sys.executable, '-m', 'tools.build_site', str(self.release),
                                 '--out', str(self.out)], cwd=REPO,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')


class PagesPolicy(unittest.TestCase):
    def setUp(self):
        self.path = REPO/'.github/workflows/pages.yml'
        self.config = yaml.safe_load(self.path.read_text())

    def test_deny_by_default_and_read_only_build(self):
        self.assertEqual(self.config['permissions'], {})
        build = self.config['jobs']['build']
        self.assertEqual(build['permissions'], {'contents': 'read'})
        self.assertFalse(build['steps'][0]['with']['persist-credentials'])

    def test_deploy_only_main_for_push_or_dispatch_never_PR(self):
        deploy = self.config['jobs']['deploy']
        self.assertEqual(deploy['if'], "github.ref == 'refs/heads/main' && github.event_name != 'pull_request'")
        self.assertEqual(deploy['needs'], 'build')
        self.assertEqual(deploy['permissions'], {'pages': 'write', 'id-token': 'write'})
        events = self.config.get('on', self.config.get(True))
        self.assertEqual(events['push']['branches'], ['main'])
        self.assertIn('pull_request', events)

    def test_PR_artifact_and_guarded_pages_artifact(self):
        steps = self.config['jobs']['build']['steps']
        ordinary = next(s for s in steps if s.get('uses','').startswith('actions/upload-artifact@'))
        pages = next(s for s in steps if s.get('uses','').startswith('actions/upload-pages-artifact@'))
        self.assertNotIn('if', ordinary)
        self.assertTrue(ordinary['with']['include-hidden-files'])
        self.assertEqual(ordinary['with']['path'], '${{ runner.temp }}/site-acceptance')
        self.assertEqual(pages['if'], self.config['jobs']['deploy']['if'])
        self.assertIn('/first', pages['with']['path'])

    def test_all_actions_pinned_and_no_extra_write_or_status_POST(self):
        for job_config in self.config['jobs'].values():
            for step in job_config['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'^[\w/-]+@[0-9a-f]{40}$')
        text = self.path.read_text()
        for unsafe in ('pull_request_target', 'statuses: write', 'contents: write', 'configure-pages', '/statuses/', 'curl '):
            self.assertNotIn(unsafe, text)

    def test_shell_blocks_strict_and_workflow_syntax(self):
        for job_config in self.config['jobs'].values():
            for step in job_config['steps']:
                if 'run' in step:
                    self.assertTrue(step['run'].startswith('set -euo pipefail\n'))
        result = subprocess.run([sys.executable, 'tools/check_workflow_syntax.py', str(self.path)],
                                cwd=REPO, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_gate_event_ref_matrix(self):
        guard = self.config['jobs']['deploy']['if']
        self.assertEqual(guard, "github.ref == 'refs/heads/main' && github.event_name != 'pull_request'")
        cases = [('push', 'refs/heads/main', True), ('push', 'refs/heads/feature', False),
                 ('pull_request', 'refs/pull/63/merge', False), ('pull_request', 'refs/heads/main', False),
                 ('workflow_dispatch', 'refs/heads/main', True), ('workflow_dispatch', 'refs/heads/feature', False)]
        for event, ref, expected in cases:
            self.assertEqual(ref == 'refs/heads/main' and event != 'pull_request', expected)
