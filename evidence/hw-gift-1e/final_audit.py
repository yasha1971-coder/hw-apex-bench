"""Final saved-data adapter preserving the frozen HW-GIFT-1e auditor.

Correct only the recursive JSON reference context: historical files are still
SHA-checked by audit.file_ref, but their child references are not reinterpreted
relative to 1e. The frozen 1d final audit and all its source bindings are checked
separately by audit.bind_1d_report_inputs before a final PASS is produced.
No Git mutation, native operation, encoding, clock or network is invoked here.
"""
import audit as base


def verify_final_proofs(search_admitted):
    """Frozen final proof, with recursion limited to the current experiment."""
    if search_admitted:
        result_path = base.HERE/'search/result.json'
        search_result = base.load(result_path)
        search_audit = base.load(base.HERE/'search/audit.json')
        base.check(search_audit.get('status') == 'PASS' and search_audit.get('saved_data_only') is True
                   and search_audit.get('result_sha256') == base.sha(result_path), 'separate search audit does not bind the current result')
        base.sha(base.HERE/'SEARCH_PROTOCOL.md')
        visited = set()
        def references(value):
            if isinstance(value,dict):
                if set(value) == {'path','sha256'}:
                    path = base.file_ref(value,True)
                    if path.is_relative_to(base.HERE) and path.suffix == '.json' and path not in visited:
                        visited.add(path)
                        references(base.load(path))
                else:
                    for item in value.values():
                        references(item)
            elif isinstance(value,list):
                for item in value:
                    references(item)
        references(search_result);references(search_audit)
        # Freeze every public attempt/build/admission/classifier payload, even
        # when its hash is represented by a named field rather than a JSON ref.
        for path in sorted((base.HERE/'search').rglob('*')):
            if path.is_file():
                base.sha(path)
        for path in sorted(base.HERE.glob('*.py')):
            base.sha(path)
    native_path = base.HERE/'audit/native.json'
    native = base.load(native_path)
    base.check(native.get('schema') == 'hw-gift-1e-independent-native-v1' and native.get('status') == 'PASS'
               and native.get('source_sha256') == base.sha(base.HERE/'verify_native.py') and native.get('no_clocks') is True
               and native.get('measurements_of_time') is False and native.get('all_attempts') is True
               and type(native.get('encodings_performed')) is int and native['encodings_performed'] == 0,
               'independent native proof source/scope differs')
    base.check(native['setup_sha256'] == base.sha(base.HERE/'setup.json'), 'native proof uses a different setup')
    names = ('archive_references','archive_paths_verified','unique_archives_verified','frame_decodes_verified','restored_bytes_verified')
    base.check(all(base.positive(native.get(k)) for k in names)
               and len(native['archive_paths']) == native['archive_paths_verified']
               and len(native['archives']) == native['unique_archives_verified']
               and native['archive_references'] >= native['archive_paths_verified'] >= native['unique_archives_verified'],
               'native proof archive/path counts differ')
    base.check(sum(p['frame_count'] for p in native['archives']) == native['frame_decodes_verified']
               and sum(p['restored_bytes'] for p in native['archives']) == native['restored_bytes_verified']
               and all(p['seek_checksums_verified'] is True and p['empty_terminal_verified'] is True for p in native['archives']),
               'native proof frame/checksum totals differ')
    documents = native['documents_sha256']
    base.check(isinstance(documents,dict) and documents, 'native proof has no inspected-document bindings')
    for name,digest in documents.items():
        base.check(base.sha(base.public(name)) == digest, 'native proof document changed: '+name)
    required = {p.relative_to(base.HERE).as_posix() for p in base.COVERED_RESULTS}
    required |= {p.relative_to(base.HERE).as_posix() for p in (base.HERE/'selfchecks').rglob('*.json')}
    required |= {p.relative_to(base.HERE).as_posix() for p in (base.HERE/'cells').rglob('*.json')}
    required |= {p.name for p in base.HERE.glob('method-v*.json')}
    required |= {'method-controls.json','decision.json'}
    base.check(required <= set(documents), 'native proof omits selected/excluded output or a method/grid selfcheck')
    return dict(path='audit/native.json',sha256=base.sha(native_path),source_sha256=native['source_sha256'],
                encodings_performed=0,**{name:native[name] for name in names})


def main():
    base.verify_final_proofs = verify_final_proofs
    return base.main()


if __name__ == '__main__':
    raise SystemExit(main())
