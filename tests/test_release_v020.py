"""A9 release integrity, adversarial inputs and independently rebuilt reports."""
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
from urllib.parse import unquote, urlsplit

import jsonschema
import yaml

from review.axis3.verdict_data import file_ref, load_json
from tools import release_synthetic as synthetic
from tools import release_v020 as job


class Release(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = synthetic.prepare(self.root/'input')
        self.out = self.root/'release'

    def write(self, path, value):
        path.write_bytes(job.encoded(value))

    def edit_config(self, callback):
        data = load_json(self.config)
        callback(data)
        self.write(self.config, data)

    def refresh(self):
        data = load_json(self.config)
        for key in ('catalogs', 'artifacts'):
            data[key] = [file_ref(self.config.parent, self.config.parent/r['path']) for r in data[key]]
        self.write(self.config, data)

    def catalog(self, group, callback):
        path = self.config.parent/'catalogs'/group/'leaderboard-input.json'
        data = load_json(path)
        callback(data)
        self.write(path, data)
        self.refresh()

    def evidence(self, group, index, callback):
        root = self.config.parent/'catalogs'/group
        path = root/'leaderboard-input.json'
        catalog = load_json(path)
        record = catalog['records'][index]
        evidence = root/record['evidence']['path']
        data = load_json(evidence)
        callback(data)
        self.write(evidence, data)
        record['evidence'] = file_ref(root, evidence)
        self.write(path, catalog)
        self.refresh()

    def build(self, out=None, **kwargs):
        return job.release(self.config, out or self.out, **kwargs)

    def rejects(self, message=None, **kwargs):
        with self.assertRaises((ValueError, jsonschema.ValidationError, FileNotFoundError)) as ctx:
            self.build(**kwargs)
        if message:
            self.assertIn(message, str(ctx.exception))
        self.assertFalse(self.out.exists())

    def output_edit(self, name, callback):
        path = self.out/name
        data = load_json(path)
        callback(data)
        self.write(path, data)

    def rehash_manifest(self):
        self.output_edit('RELEASE_MANIFEST.json', lambda d: d.update(artifacts=[
            {**r, **file_ref(self.out, self.out/r['path'])} for r in d['artifacts']]))

    def test_manifest_and_every_output_byte_determinism(self):
        first = self.build()
        other = self.root/'second'
        second = self.build(other)
        a = {p.relative_to(self.out).as_posix(): p.read_bytes() for p in job.files(self.out)}
        b = {p.relative_to(other).as_posix(): p.read_bytes() for p in job.files(other)}
        self.assertEqual(a, b)
        self.assertEqual(first, second)
        self.assertEqual((first['tables'], first['rows']), (5, 5))

    def test_relocation_determinism(self):
        first = self.build()
        moved = self.root/'moved'
        shutil.copytree(self.config.parent, moved)
        result = job.release(moved/'release-input.json', self.root/'other')
        self.assertEqual(first, result)
        self.assertEqual((self.out/'RELEASE_MANIFEST.json').read_bytes(),
                         (self.root/'other/RELEASE_MANIFEST.json').read_bytes())

    def test_all_axes_reverified_from_staged_dependencies(self):
        self.build()
        with mock.patch.object(job.leaderboard.axis4_evidence_verify, 'verify',
                               wraps=job.leaderboard.axis4_evidence_verify.verify) as a4, \
             mock.patch.object(job.leaderboard.axis5_evidence_verify, 'verify',
                               wraps=job.leaderboard.axis5_evidence_verify.verify) as a5, \
             mock.patch.object(job.leaderboard, 'recompute', wraps=job.leaderboard.recompute) as a3:
            self.assertEqual(job.verify(self.out)['status'], 'PASS')
            self.assertEqual((a3.call_count, a4.call_count, a5.call_count), (1, 2, 1))

    def test_every_artifact_has_hash_size_axis_machine_commit(self):
        self.build()
        manifest = load_json(self.out/'RELEASE_MANIFEST.json')
        expected = {p.relative_to(self.out).as_posix() for p in job.files(self.out)}-{'RELEASE_MANIFEST.json'}
        self.assertEqual({r['path'] for r in manifest['artifacts']}, expected)
        for record in manifest['artifacts']:
            self.assertEqual(record['commit'], synthetic.BASE_COMMIT)
            self.assertEqual(record['commit_scope'], 'release-input')
            self.assertIn('machine_id', record)
            self.assertIn('axis', record)
            self.assertEqual({k: record[k] for k in ('path', 'bytes', 'sha256')},
                             file_ref(self.out, self.out/record['path']))

    def test_no_clock_or_native_codec_execution(self):
        with mock.patch('time.time', side_effect=AssertionError('clock')), \
             mock.patch('tools.axis4.open_reader', side_effect=AssertionError('native')), \
             mock.patch('socket.socket.connect', side_effect=AssertionError('network')), \
             mock.patch('urllib.request.urlopen', side_effect=AssertionError('network')), \
             mock.patch.object(job, 'capture_silence', side_effect=AssertionError('synthetic gate')):
            self.build()
        text = (self.out/'RELEASE_MANIFEST.json').read_text()
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('created_at', text)

    def test_external_manifest_anchor(self):
        receipt = self.build()
        self.assertEqual(job.verify(self.out, receipt['manifest_sha256']), receipt)
        with self.assertRaisesRegex(ValueError, 'external SHA'):
            job.verify(self.out, '0'*64)

    def test_wrong_input_schema_refused(self):
        self.edit_config(lambda d: d.update(schema='release-input-v2'))
        self.rejects()

    def test_missing_axis_refused(self):
        self.edit_config(lambda d: d.update(catalogs=d['catalogs'][1:]))
        self.rejects('every axis')

    def test_missing_artifact_refused(self):
        (self.config.parent/'CHANGELOG.md').unlink()
        self.rejects()

    def test_omitted_required_artifact_refused(self):
        self.edit_config(lambda d: d.update(artifacts=[r for r in d['artifacts'] if r['path']!='CITATION.cff']))
        self.rejects('required release artifact')

    def test_changed_catalog_anchor_refused(self):
        self.edit_config(lambda d: d['catalogs'][0].update(sha256='0'*64))
        self.rejects('frozen file changed')

    def test_evidence_schema_refused_even_after_reanchoring(self):
        self.evidence('golden', 0, lambda d: d.update(schema='axis4-evidence-v2'))
        self.rejects('unsupported evidence schema')

    def test_axis4_forged_answer_sha_refused(self):
        self.evidence('golden', 0, lambda d: d['rows'][0].update(observed_sha256='0'*64))
        self.rejects()

    def test_axis5_forged_classification_refused(self):
        self.evidence('golden', 1, lambda d: d['rows'][0].update(classification='harmless'))
        self.rejects()

    def test_axis3_forged_raw_summary_refused(self):
        self.evidence('axis3-unit', 0, lambda d: d['metrics'].update(p50_us=99))
        self.rejects()

    def test_duplicate_format_variant_refused(self):
        self.catalog('golden', lambda d: d['records'].append(copy.deepcopy(d['records'][0])))
        self.rejects('duplicate format/variant')

    def test_unknown_machine_forced_comparison_refused(self):
        self.catalog('golden', lambda d: [d['records'][i].update(table='forced') for i in (0, 2)])
        self.rejects('machine unrecorded')

    def add_axis3(self, change):
        root = self.config.parent/'catalogs/axis3-unit'
        shutil.copytree(root, root/'other')
        data = load_json(root/'other/evidence.json')
        data['format'] = 'unit-other'
        change(data)
        self.write(root/'other/evidence.json', data)
        self.catalog('axis3-unit', lambda d: d['records'].append({
            'evidence': file_ref(root, root/'other/evidence.json'), 'input_root': 'other'}))

    def test_mixed_machines_in_table_refused(self):
        self.add_axis3(lambda d: d['hardware'].update(machine_id='other'))
        self.rejects('mixed conditions')

    def test_mixed_requests_in_table_refused(self):
        self.add_axis3(lambda d: None)
        root = self.config.parent/'catalogs/axis3-unit/other'
        (root/'requests.json').write_bytes(b'different ordered requests')
        data = load_json(root/'evidence.json')
        data['requests'] = file_ref(root, root/'requests.json')
        self.write(root/'evidence.json', data)
        self.catalog('axis3-unit', lambda d: d['records'][1].update(evidence=file_ref(root.parent, root/'evidence.json')))
        self.rejects('mixed conditions')

    def test_missing_dependency_refused(self):
        (self.config.parent/'catalogs/golden/data/libhwa_refrel3.so').unlink()
        self.rejects()

    def test_traversal_refused(self):
        self.edit_config(lambda d: d['artifacts'][0].update(path='../outside'))
        self.rejects()

    def test_symlink_artifact_refused(self):
        root = self.config.parent/'catalogs/axis3-unit'
        (root/'alias').symlink_to(root/'fixture.txt')
        self.rejects('symlink')

    def test_duplicate_catalog_refused(self):
        self.edit_config(lambda d: d['catalogs'].append(copy.deepcopy(d['catalogs'][0])))
        self.rejects()

    def test_existing_output_refused(self):
        self.build()
        with self.assertRaisesRegex(ValueError, 'must not exist'):
            self.build()

    def test_output_inside_input_root_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside input'):
            self.build(self.config.parent/'release')

    def test_changed_manifest_sha_refused(self):
        self.build()
        self.output_edit('RELEASE_MANIFEST.json', lambda d: d['artifacts'][0].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError, 'frozen file changed'):
            job.verify(self.out)

    def test_forged_provenance_refused(self):
        self.build()
        self.output_edit('RELEASE_MANIFEST.json', lambda d: d['artifacts'][0].update(machine_id='ace-core'))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            job.verify(self.out)

    def test_rehashed_forged_leaderboard_refused(self):
        self.build()
        self.output_edit('leaderboard.json', lambda d: d['tables'][0]['rows'][0].update(verified=123))
        self.rehash_manifest()
        with self.assertRaisesRegex(ValueError, 'leaderboard does not match'):
            job.verify(self.out)

    def test_rehashed_forged_evidence_refused(self):
        self.build()
        manifest = load_json(self.out/'RELEASE_MANIFEST.json')
        target = next(r['path'] for r in manifest['artifacts'] if r['role']=='evidence')
        self.output_edit(target, lambda d: d.update(forged=True))
        self.rehash_manifest()
        with self.assertRaisesRegex(ValueError, 'copied evidence changed'):
            job.verify(self.out)

    def test_unlisted_extra_file_refused(self):
        self.build()
        (self.out/'extra').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'missing/extra artifact'):
            job.verify(self.out)

    def test_missing_manifest_artifact_refused(self):
        self.build()
        (self.out/'leaderboard.csv').unlink()
        with self.assertRaisesRegex(ValueError, 'missing/extra artifact'):
            job.verify(self.out)

    def test_manifest_duplicate_path_refused(self):
        self.build()
        self.output_edit('RELEASE_MANIFEST.json', lambda d: d['artifacts'].append(d['artifacts'][0]))
        with self.assertRaisesRegex(ValueError, 'sorted and unique'):
            job.verify(self.out)

    def test_real_requires_gate(self):
        self.rejects('mandatory silence', mode='real', data_root=self.config.parent,
                     native_so=[self.config.parent/'catalogs/golden/data/libhwa_refrel3.so'])

    def test_real_refuses_synthetic_only(self):
        self.rejects('measured/official', mode='real', data_root=self.config.parent,
                     native_so=[self.config.parent/'catalogs/golden/data/libhwa_refrel3.so'], require_silence=True)

    def test_real_wrong_data_root_refused(self):
        self.rejects('equal release config', mode='real', data_root=self.root,
                     native_so=[self.config.parent/'catalogs/golden/data/libhwa_refrel3.so'], require_silence=True)

    def measured_fixture(self):
        snapshot = {'host': 'ace-core', 'load1': 0.01, 'disk_available_bytes': 30000000000,
                    'sampling_seconds': 1.1, 'processes': []}
        gate = job.judge(snapshot)
        root = self.config.parent/'catalogs/axis3-unit'
        self.write(root/'gate.json', gate)
        self.evidence('axis3-unit', 0, lambda d: d.update(
            kind='measured', silence_gate=file_ref(root, root/'gate.json')))
        return gate, [self.config.parent/'catalogs/golden/data/libhwa_refrel3.so']

    def test_real_fresh_gates_and_library_binding(self):
        gate, native = self.measured_fixture()
        with mock.patch.object(job, 'capture_silence', return_value=gate) as gather:
            receipt = self.build(mode='real', data_root=self.config.parent,
                                 native_so=native, require_silence=True)
        self.assertEqual(gather.call_count, 2)
        self.assertEqual(receipt['silence_before'], gate)
        self.assertEqual(receipt['silence_after'], gate)
        self.assertEqual(job.verify(self.out)['status'], 'PASS')

    def test_real_failed_before_gate_refused(self):
        gate, native = self.measured_fixture()
        gate = job.judge({**gate['snapshot'], 'load1': 0.5})
        with mock.patch.object(job, 'capture_silence', return_value=gate):
            self.rejects('silence gate failed', mode='real', data_root=self.config.parent,
                         native_so=native, require_silence=True)

    def test_real_failed_after_gate_rolls_back(self):
        gate, native = self.measured_fixture()
        bad = job.judge({**gate['snapshot'], 'host': 'other'})
        with mock.patch.object(job, 'capture_silence', side_effect=[gate, bad]):
            self.rejects('after verification', mode='real', data_root=self.config.parent,
                         native_so=native, require_silence=True)

    def test_real_forged_gate_refused(self):
        gate, native = self.measured_fixture()
        gate = {**gate, 'reasons': ['forged']}
        with mock.patch.object(job, 'capture_silence', return_value=gate):
            self.rejects('silence gate failed', mode='real', data_root=self.config.parent,
                         native_so=native, require_silence=True)

    def test_real_wrong_native_library_refused(self):
        gate, native = self.measured_fixture()
        wrong = self.root/'wrong.so'
        wrong.write_bytes(b'not the frozen native binary')
        with mock.patch.object(job, 'capture_silence', return_value=gate):
            self.rejects('native-so', mode='real', data_root=self.config.parent,
                         native_so=[wrong], require_silence=True)

    def test_real_missing_native_parameter_refused(self):
        self.rejects('native-so', mode='real', data_root=self.config.parent, require_silence=True)

    def test_changed_input_during_build_rolls_back(self):
        original = job.leaderboard.build
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.config.parent/'PROTOCOL_AXIS5.md'
            path.write_bytes(path.read_bytes()+b'\nchanged\n')
            return result
        with mock.patch.object(job.leaderboard, 'build', side_effect=changed):
            self.rejects('input changed')

    def test_changed_config_during_build_rolls_back(self):
        original = job.leaderboard.build
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.edit_config(lambda d: d.update(commit='b'*40))
            return result
        with mock.patch.object(job.leaderboard, 'build', side_effect=changed):
            self.rejects('input changed')

    def test_metadata_schemas_and_identity(self):
        job.validate_metadata(self.config.parent)
        spec = load_json(job.REPO/'tools/schemas/cff-1.2.0.schema.json')
        self.assertEqual(hashlib.sha256((job.REPO/'tools/schemas/cff-1.2.0.schema.json').read_bytes()).hexdigest(),
                         '0b8d22140da702d766df318dcff3a91af2f39521298dcf36d76315fd99cc169b')
        jsonschema.Draft7Validator.check_schema(spec)

    def test_invalid_citation_schema_refused(self):
        path = self.config.parent/'CITATION.cff'
        data = yaml.safe_load(path.read_text())
        data['authors'] = 'invalid'
        path.write_text(yaml.safe_dump(data))
        self.refresh()
        self.rejects()

    def test_invalid_zenodo_schema_refused(self):
        path = self.config.parent/'.zenodo.json'
        data = load_json(path)
        data['upload_type'] = 'dataset'
        self.write(path, data)
        self.refresh()
        self.rejects()

    def test_wrong_metadata_version_refused(self):
        path = self.config.parent/'CITATION.cff'
        path.write_text(path.read_text().replace('version: "0.2.0"', 'version: "0.1.0"'))
        self.refresh()
        self.rejects('identity mismatch')

    def test_pending_official_placeholder_refused(self):
        self.evidence('axis3-unit', 0, lambda d: d.clear())
        self.rejects('unsupported evidence schema')

    def test_all_relative_document_links_exist(self):
        for name in ('METHODOLOGY.md', 'CHANGELOG.md', 'RELEASE_NOTES_v0.2.0.md'):
            path = job.REPO/name
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
                url = urlsplit(link)
                if url.scheme or url.netloc or not url.path:
                    continue
                self.assertTrue((path.parent/unquote(url.path)).is_file(), (name, link))

    def test_offline_shell_entry_point(self):
        result = subprocess.run(['bash', str(job.REPO/'reproduce_v020.sh'), 'synthetic',
                                 '--out', str(self.root/'shell')], cwd=job.REPO,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['rerun'], 'BYTE_IDENTICAL')
        self.assertFalse(receipt['native_execution'])

    def test_cli_verification_and_bad_anchor(self):
        receipt = self.build()
        for anchor, expected in ((receipt['manifest_sha256'], 0), ('0'*64, 1)):
            result = subprocess.run([sys.executable, '-m', 'tools.release_v020', '--verify',
                                     str(self.out), '--manifest-sha256', anchor],
                                    cwd=job.REPO, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_real_shell_cannot_bypass_gate_using_verify(self):
        self.build()
        result = subprocess.run(['bash', str(job.REPO/'reproduce_v020.sh'), 'real',
                                 '--verify', str(self.out)], cwd=job.REPO,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 1)
        self.assertIn('invalid verify arguments', result.stderr)
