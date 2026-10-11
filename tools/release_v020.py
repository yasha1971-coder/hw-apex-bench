#!/usr/bin/env python3
"""Offline, hash-bound v0.2.0 release assembly and independent verification.

No codec or measurement is executed. A scientific FAIL can be valid evidence;
a verifier exception is fatal. Commit denotes the declared release-input commit,
not an inferred codec/measurement commit. Hashes do not authenticate authorship.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import jsonschema
import yaml

from review.axis3.verdict_data import checked_file, file_ref, load_json, sha256_file, capture_silence
from tools import build_leaderboard as leaderboard
from tools.silence_contract import judge

REPO = Path(__file__).resolve().parents[1]
METADATA = ('CITATION.cff', '.zenodo.json', 'METHODOLOGY.md', 'CHANGELOG.md',
            'RELEASE_NOTES_v0.2.0.md')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False)+'\n').encode('utf-8')


def schema(value, name):
    spec = load_json(REPO/'schemas'/name)
    jsonschema.validators.validator_for(spec)(spec, format_checker=jsonschema.FormatChecker()).validate(value)


def validate_metadata(root):
    citation = yaml.safe_load((root/'CITATION.cff').read_text())
    spec = load_json(REPO/'tools/schemas/cff-1.2.0.schema.json')
    jsonschema.Draft7Validator(spec, format_checker=jsonschema.FormatChecker()).validate(citation)
    zenodo = load_json(root/'.zenodo.json')
    schema(zenodo, 'zenodo-v020.schema.json')
    expected = {'family-names': 'Shavidze', 'given-names': 'Yakiv',
                'orcid': 'https://orcid.org/0009-0008-3622-3448'}
    if citation.get('version') != '0.2.0' or citation.get('authors') != [expected]:
        raise ValueError('CITATION release identity mismatch')
    if zenodo['version'] != '0.2.0' or zenodo['creators'] != [
            {'name': 'Shavidze, Yakiv', 'orcid': '0009-0008-3622-3448'}]:
        raise ValueError('Zenodo release identity mismatch')
    for name in METADATA:
        if not (root/name).is_file():
            raise ValueError('missing release metadata: '+name)


def files(root):
    """No symlinks, devices, or filesystem-dependent enumeration order."""
    root = Path(root).resolve(strict=True)
    result = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink artifact refused: '+path.name)
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('nonregular artifact')
        # Also validates normalized, confined POSIX names.
        leaderboard.relative(root, path.relative_to(root).as_posix())
        result.append(path)
    return result


def inputs(config_path):
    config_path = Path(config_path).resolve(strict=True)
    root = config_path.parent
    config = load_json(config_path)
    schema(config, 'release-input-v1.schema.json')
    catalogs = [checked_file(root, ref) for ref in config['catalogs']]
    if any(p.name != 'leaderboard-input.json' for p in catalogs):
        raise ValueError('catalog filename must be leaderboard-input.json')
    if len({p.parent for p in catalogs}) != len(catalogs):
        raise ValueError('duplicate catalog')
    directories = [p.parent for p in catalogs]
    for a in directories:
        for b in directories:
            if a != b and a.is_relative_to(b):
                raise ValueError('overlapping catalog directories')
    artifacts = [checked_file(root, ref) for ref in config['artifacts']]
    if len(set(artifacts)) != len(artifacts):
        raise ValueError('duplicate release artifact')
    if not set(METADATA) <= {p.relative_to(root).as_posix() for p in artifacts}:
        raise ValueError('missing required release artifact')
    data, sources = leaderboard.collect(directories)  # All axis verifiers.
    axes = {r['axis'] for t in data['tables'] for r in t['rows']}
    if axes != {3, 4, 5}:
        raise ValueError('release requires evidence for every axis 3/4/5')
    for p in catalogs:
        if config_path.is_relative_to(p.parent):
            raise ValueError('release config must be outside catalog directories')
    return root, config, catalogs, artifacts, data, sources


def provenance(data):
    result = {}
    for table in data['tables']:
        for row in table['rows']:
            sha = row['evidence_sha256']
            entry = result.setdefault(sha, {'axes': set(), 'machines': set()})
            entry['axes'].add(row['axis'])
            entry['machines'].add(row['machine'])
    return result


def attributes(identities, info, commit, role):
    axes, machines = set(), set()
    for identity in identities:
        axes.update(info[identity]['axes'])
        machines.update(info[identity]['machines'])
    return {'axis': next(iter(axes)) if len(axes) == 1 else None,
            'axes': sorted(axes), 'machine_id': next(iter(machines)) if len(machines) == 1 else None,
            'evidence_sha256': sorted(identities), 'commit': commit,
            'commit_scope': 'release-input', 'role': role}


def inventory(root, recipe, data):
    info = provenance(data)
    all_ids = set(info)
    records = []
    for path in files(root):
        name = path.relative_to(root).as_posix()
        if name == 'RELEASE_MANIFEST.json':
            continue  # A manifest cannot contain its own SHA; external anchor is supported.
        if name.startswith('inputs/'):
            key = '/'.join(name.split('/')[:2])+'/leaderboard-input.json'
            catalog = load_json(root/key)
            ids = {r['evidence']['sha256'] for r in catalog['records']}
            role = 'input'
        elif name.startswith('evidence/'):
            ids, role = {name.split('/')[1]}, 'evidence'
        elif name in ('LEADERBOARD.md', 'leaderboard.csv', 'leaderboard.json'):
            ids, role = all_ids, 'leaderboard'
        elif name == 'RELEASE_INPUT.json':
            ids, role = all_ids, 'recipe'
        else:
            ids, role = set(), 'metadata'
        records.append({**file_ref(root, path), **attributes(ids, info, recipe['commit'], role)})
    return records


def referenced_catalogs(root, recipe, data_root):
    """Real releases reference each catalog directory by a per-file hash listing (A13c).

    The listed directory under data_root must contain exactly the listed files, each with
    its recorded bytes and SHA-256, and the same leaderboard-input.json as the release copy."""
    if data_root is None:
        raise ValueError('referenced data roots require --data-root')
    data_root = Path(data_root).resolve(strict=True)
    if len(recipe['data_roots']) != len(recipe['catalogs']):
        raise ValueError('every catalog needs exactly one data-root listing')
    directories = []
    for listing_ref, catalog_ref in zip(recipe['data_roots'], recipe['catalogs']):
        listing_path = checked_file(root, listing_ref)
        catalog_copy = checked_file(root, catalog_ref)
        if listing_path.parent != catalog_copy.parent or listing_path.name != 'DATA_ROOT.json':
            raise ValueError('data-root listing must sit beside its catalog copy')
        listing = load_json(listing_path)
        schema(listing, 'release-data-root-v1.schema.json')
        base = leaderboard.relative(data_root, listing['catalog_dir'])
        if not base.is_dir() or base == data_root:
            raise ValueError('referenced catalog directory missing')
        if (base/'leaderboard-input.json').read_bytes() != catalog_copy.read_bytes():
            raise ValueError('referenced catalog differs from release copy')
        names = [f['path'] for f in listing['files']]
        if len(names) != len(set(names)):
            raise ValueError('data-root listing must be unique')
        if names != [p.relative_to(base).as_posix() for p in files(base)]:
            raise ValueError('referenced data root has missing or unlisted files')
        for ref in listing['files']:
            checked_file(base, ref)
        directories.append(base)
    return directories


def verify(directory, expected_manifest_sha256=None, data_root=None):
    root = Path(directory).resolve(strict=True)
    path = root/'RELEASE_MANIFEST.json'
    if expected_manifest_sha256 is not None and sha256_file(path) != expected_manifest_sha256:
        raise ValueError('manifest differs from external SHA anchor')
    manifest = load_json(path)
    schema(manifest, 'release-manifest-v1.schema.json')
    recipe = load_json(root/'RELEASE_INPUT.json')
    schema(recipe, 'release-recipe-v1.schema.json')
    names = [r['path'] for r in manifest['artifacts']]
    if names != sorted(set(names)):
        raise ValueError('manifest paths must be sorted and unique')
    actual = [p.relative_to(root).as_posix() for p in files(root)
              if p.name != 'RELEASE_MANIFEST.json' or p.parent != root]
    if names != actual:
        raise ValueError('manifest missing/extra artifact')
    for ref in manifest['artifacts']:
        checked_file(root, {k: ref[k] for k in ('path', 'bytes', 'sha256')})
    catalogs = [checked_file(root, ref) for ref in recipe['catalogs']]
    if len(set(p.parent for p in catalogs)) != len(catalogs):
        raise ValueError('duplicate catalog')
    if recipe['mode'] == 'real' and 'data_roots' not in recipe:
        raise ValueError('real release must reference its data roots')
    if 'data_roots' in recipe:
        data, sources = leaderboard.collect(referenced_catalogs(root, recipe, data_root))
    else:
        data, sources = leaderboard.collect([p.parent for p in catalogs])
    if recipe['mode'] == 'real' and not any(
            t['conditions']['kind'] in ('measured', 'official') for t in data['tables']):
        raise ValueError('real recipe requires measured/official evidence')
    if {r['axis'] for t in data['tables'] for r in t['rows']} != {3, 4, 5}:
        raise ValueError('release requires evidence for every axis 3/4/5')
    for name, blob in leaderboard.render(data).items():
        if (root/name).read_bytes() != blob:
            raise ValueError('leaderboard does not match verified evidence: '+name)
    for sha, blob in sources.items():
        if (root/'evidence'/sha/'evidence.json').read_bytes() != blob:
            raise ValueError('copied evidence changed')
    if manifest['artifacts'] != inventory(root, recipe, data):
        raise ValueError('manifest provenance mismatch')
    if manifest['commit'] != recipe['commit'] or manifest['mode'] != recipe['mode']:
        raise ValueError('manifest recipe mismatch')
    validate_metadata(root/'metadata')
    result = {'status': 'PASS', 'artifacts': len(names), 'tables': len(data['tables']),
              'rows': sum(len(t['rows']) for t in data['tables']),
              'manifest_sha256': sha256_file(path)}
    return result


QUIET_WAIT_BOUND_SECONDS = 1800
QUIET_POLL_SECONDS = 15


def admitted(directory, label, *, bound_seconds, poll_seconds, sleep, monotonic):
    """A13i: the release gates follow its own input verification and hashing; wait (bounded by
    monotonic wall time including every telemetry sample) until the unchanged judge passes.
    Returns the PASS record and the wait log; refuses when the bound expires."""
    started, refused = monotonic(), []
    while True:
        record = capture_silence(directory)
        if record == judge(record['snapshot']) and record['status'] == 'PASS':
            break
        refused.append({'load1': record['snapshot'].get('load1'), 'reasons': record.get('reasons')})
        if monotonic() - started + int(poll_seconds * 1e9) > int(bound_seconds * 1e9):
            raise ValueError('real silence gate failed' + ('' if label == 'before' else ' after verification')
                             + ': quiet wait bound expired')
        sleep(poll_seconds)
    waited = monotonic() - started
    if waited > int(bound_seconds * 1e9):
        raise ValueError('real silence gate failed: quiet wait bound expired')
    return record, {'label': label, 'bound_seconds': bound_seconds, 'poll_seconds': poll_seconds,
                    'waited_ns': waited, 'refused': refused}


def release(config_path, output, *, mode='synthetic', data_root=None,
            native_so=(), require_silence=False, quiet_bound_seconds=QUIET_WAIT_BOUND_SECONDS,
            quiet_poll_seconds=QUIET_POLL_SECONDS, sleep=None, monotonic=None):
    import time
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic_ns
    waits = []
    config_path = Path(config_path).resolve(strict=True)
    config_sha = sha256_file(config_path)
    root, config, catalogs, artifacts, data, sources = inputs(config_path)
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('output must not exist')
    if out.is_relative_to(root):
        raise ValueError('release output must be outside input root')
    if mode not in ('synthetic', 'real'):
        raise ValueError('unknown release mode')
    if mode == 'real':
        if not require_silence or data_root is None or not native_so:
            raise ValueError('real mode requires data-root, native-so and mandatory silence gate')
        if Path(data_root).resolve(strict=True) != root:
            raise ValueError('data-root must equal release config root')
        if not any(t['conditions']['kind'] in ('measured', 'official') for t in data['tables']):
            raise ValueError('real mode requires measured/official evidence; synthetic stays labelled')
        before, wait = admitted(out.parent, 'before', bound_seconds=quiet_bound_seconds,
                                poll_seconds=quiet_poll_seconds, sleep=sleep, monotonic=monotonic)
        waits.append(wait)
    # Preflight snapshots include every dependency, not just top-level evidence.
    snapshots = {p: (p.stat().st_size, sha256_file(p)) for c in catalogs for p in files(c.parent)}
    snapshots.update({p: (p.stat().st_size, sha256_file(p)) for p in artifacts})
    if mode == 'real':
        hashes = {sha for _, sha in snapshots.values()}
        supplied = {sha256_file(Path(p).resolve(strict=True)) for p in native_so}
        required = {sha for p, (_, sha) in snapshots.items() if p.suffix == '.so'}
        if not supplied <= hashes or not required <= supplied:
            raise ValueError('native-so must match every retained native library SHA')
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.release-v020-', dir=out.parent))
    try:
        # Use the public A8 builder, which repeats all verification before writing.
        leaderboard.build([p.parent for p in catalogs], staging/'built')
        built = staging/'built'
        recipe = {'schema': 'release-recipe-v1', 'commit': config['commit'], 'mode': mode,
                  'catalogs': []}
        listings = []
        for catalog in sorted(catalogs, key=sha256_file):
            destination = built/'inputs'/sha256_file(catalog)
            if mode == 'real':
                # A13c: reference the data root by per-file hashes; copy only the catalog.
                destination.mkdir(parents=True)
                shutil.copyfile(catalog, destination/'leaderboard-input.json')
                listing = {'schema': 'release-data-root-v1',
                           'catalog_dir': catalog.parent.relative_to(root).as_posix(),
                           'files': [{'path': p.relative_to(catalog.parent).as_posix(),
                                      'bytes': snapshots[p][0], 'sha256': snapshots[p][1]}
                                     for p in files(catalog.parent)]}
                (destination/'DATA_ROOT.json').write_bytes(encoded(listing))
                listings.append(file_ref(built, destination/'DATA_ROOT.json'))
            else:
                shutil.copytree(catalog.parent, destination)
            recipe['catalogs'].append(file_ref(built, destination/'leaderboard-input.json'))
        if listings:
            recipe['data_roots'] = listings
        metadata = built/'metadata'
        metadata.mkdir()
        for artifact in artifacts:
            target = metadata/artifact.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact, target)
        validate_metadata(metadata)
        (built/'RELEASE_INPUT.json').write_bytes(encoded(recipe))
        manifest = {'schema': 'release-manifest-v1', 'version': '0.2.0',
                    'commit': config['commit'], 'mode': mode,
                    'artifacts': inventory(built, recipe, data)}
        (built/'RELEASE_MANIFEST.json').write_bytes(encoded(manifest))
        result = verify(built, data_root=root if mode == 'real' else None)
        if sha256_file(config_path) != config_sha or any(
                (p.stat().st_size, sha256_file(p)) != snapshot for p, snapshot in snapshots.items()):
            raise ValueError('input changed during release assembly')
        if mode == 'real':
            after, wait = admitted(out.parent, 'after', bound_seconds=quiet_bound_seconds,
                                   poll_seconds=quiet_poll_seconds, sleep=sleep, monotonic=monotonic)
            waits.append(wait)
            # Admission telemetry stays in the receipt, not deterministic release bytes.
            result['silence_before'], result['silence_after'] = before, after
            result['silence_waits'] = waits
        built.rename(out)
        return result
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--input', type=Path)
    operation.add_argument('--verify', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--mode', choices=('synthetic', 'real'), default='synthetic')
    parser.add_argument('--data-root', type=Path, help='real: release config root; --verify: root holding the referenced catalog directories')
    parser.add_argument('--native-so', type=Path, action='append', default=[])
    parser.add_argument('--require-silence', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify:
            if args.mode == 'real' or args.out or args.manifest_sha256 and not leaderboard.HASH.fullmatch(args.manifest_sha256):
                raise ValueError('invalid verify arguments')
            result = verify(args.verify, args.manifest_sha256, args.data_root)
        else:
            if not args.out or args.manifest_sha256:
                raise ValueError('--input requires --out; manifest SHA is for --verify')
            result = release(args.input, args.out, mode=args.mode, data_root=args.data_root,
                             native_so=args.native_so, require_silence=args.require_silence)
    except Exception as exc:
        parser.exit(1, 'RELEASE_FAILED '+type(exc).__name__+': '+str(exc)+'\n')
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
