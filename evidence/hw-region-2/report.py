"""Render only a completed saved equivalence Kill; never invoke the reader.

All string comparisons below use retained public captures. No experiment
imports, native libraries, subprocesses, network access or clock calls.
"""
import gzip
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIGNATURE = "[written by ChatGPT (AI) at the author's request; checked by the author]"
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
CALIBRATION = '7fdcbd78b27739cbe1739bf0a8650f395c2afbde'
FROZEN_SOURCES = '327090a0'
BASE_URL = 'https://github.com/dpryan79/lib2bit/blob/' + PIN + '/'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique(pairs):
    result = {}
    for key, item in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = item
    return result


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def public_path(record):
    name = record['path'].replace('\\', '/')
    marker = '/evidence/hw-region-2/'
    if marker in name:
        name = name.split(marker, 1)[1]
    require(not name.startswith('/') and ':' not in name, 'expected a public HW-REGION-2 artifact')
    path = (HERE / name).resolve()
    require(path.is_relative_to(HERE.resolve()), 'artifact escaped this experiment')
    return path


def public_artifact(record):
    require(valid_sha(record.get('sha256')) and integer(record.get('bytes')), 'invalid artifact identity')
    path = public_path(record)
    require(path.is_file() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'public artifact changed: ' + str(path))
    return path


def public_reference(record):
    require(set(record) == {'path', 'sha256'} and valid_sha(record['sha256']), 'invalid public receipt reference')
    path = public_path(record)
    require(path.is_file() and sha(path) == record['sha256'], 'command receipt changed')
    return path


def compressed_metadata(record):
    path = public_artifact(record)
    return json.loads(gzip.decompress(path.read_bytes()), object_pairs_hook=unique)


def validate_intervals(rows, length):
    require(isinstance(rows, list), 'interval table missing')
    end = 0
    for row in rows:
        require(isinstance(row, list) and len(row) == 2 and integer(row[0]) and integer(row[1], 1)
                and end <= row[0] <= length and row[1] <= length - row[0], 'invalid interval table')
        end = row[0] + row[1]


def covering_interval(rows, coordinate):
    matches = [row for row in rows if row[0] <= coordinate < row[0] + row[1]]
    require(len(matches) == 1, 'first difference must be in exactly one corresponding interval')
    return matches[0]


def validate_writer(metadata, identity, source=None):
    require(metadata.get('schema') == 'hw-region-2-original-writer-v1' and metadata.get('status') == 'PASS'
            and metadata['license'] == 'Apache-2.0' and metadata['clocks'] == 0 and metadata['native_calls'] == 0
            and metadata['measurements_of_time'] is False
            and metadata['source_sha256'] == identity['source_sha256']['evidence/hw-region-2/writer.py'], 'writer identity/untimed proof differs')
    sequence, archive, check = metadata['sequence'], metadata['archive'], metadata['structural_check']
    length = sequence['bytes']
    require(integer(length, 1) and length < 1 << 32 and archive['length'] == length and archive['version'] == 0
            and archive['endianness'] == 'little' and check['status'] == 'PASS' and check['case_preserved'] is True
            and check['lib2bit_invoked'] is False and check['sha256'] == sequence['sha256'], 'whole structural case-preserving proof missing')
    validate_intervals(archive['n_blocks'], length)
    validate_intervals(archive['mask_blocks'], length)
    index_end = 16 + 1 + len(archive['name'].encode('ascii')) + 4
    packed_start = index_end + 16 + 8 * (len(archive['n_blocks']) + len(archive['mask_blocks']))
    require(archive['record_offset'] == index_end and archive['packed_bases_offset'] == packed_start
            and archive['packed_bases_bytes'] == (length + 3) // 4 and archive['bytes'] == packed_start + (length + 3) // 4,
            'standard one-sequence version0 2bit extent differs')
    fai = metadata['fai']['geometry']
    require(fai['name'] == archive['name'] and fai['length'] == length and integer(fai['offset'], 1)
            and integer(fai['line_bases'], 1) and fai['line_width'] >= fai['line_bases'], 'FAI/sequence geometry differs')
    fixture = metadata['known_fixture']
    require(fixture['status'] == 'PASS' and fixture['packed_hex'] == '1b1b0093' and fixture['n_blocks'] == [[8, 4]]
            and fixture['mask_blocks'] == [[4, 4], [10, 2]] and fixture['case_preserving_roundtrip'] is True,
            'known packed/N/mask fixture failed')
    if source is not None:
        require(sequence['bytes'] == source['sequence_bytes'] and sequence['sha256'] == source['sequence_sha256']
                and sequence['alphabet'] == source['alphabet'] and sequence['lowercase_n_count'] == source['alphabet']['n']
                and sequence['first_lowercase_n'] == source['first_lowercase_n']
                and metadata['source_fasta']['bytes'] == source['source_bytes']
                and metadata['source_fasta']['sha256'] == source['source_sha256'], 'writer did not preserve the exact preflight source')


def compare_capture(call, executable, expected_start, expected_length, literal=None):
    value = call['result']
    require(value['schema'] == 'hw-region-2-equivalence-v1' and value['no_clocks'] is True and value['storeMasked'] == 1
            and value['start0'] == expected_start and value['length'] == expected_length, 'wrong native correctness call')
    left_path = public_artifact(call['outputs']['expected'])
    right_path = public_artifact(call['outputs']['actual'])
    left, right = left_path.read_bytes(), right_path.read_bytes()
    require(len(left) == len(right) == expected_length, 'NULL/short native result is METHOD ERROR, not equivalence Kill')
    differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
    status = 'KILL' if differences else 'PASS'
    require(value['status'] == status and call['returncode'] == (2 if differences else 0) and value['mismatches'] == len(differences),
            'native status/returncode differs from independently compared captures')
    if literal is not None:
        require(left == right == literal, 'positive known-answer control failed')
    if differences:
        first = differences[0]
        require((value['first_difference0'], value['first_difference1'], value['expected_byte'], value['actual_byte'])
                == (expected_start + first, expected_start + first + 1, left[first], right[first]), 'first differing coordinate/bytes differs')
    command_path = public_reference(call['command'])
    command = load(command_path)
    argv = command['identity']['argv']
    require(command['status'] == 'COMPLETE' and command['returncode'] == call['returncode']
            and command['identity']['allowed_returncodes'] == [0, 2]
            and len(argv) == 12 and argv[:3] == ['taskset', '-c', '15'] and argv[3] == executable['path']
            and argv[8:10] == [str(expected_start), str(expected_length)] and command['identity']['outputs'] == argv[10:12],
            'native command/build/workload receipt differs')
    require(load(command_path.parent / 'stdout') == value and (command_path.parent / 'stderr').read_bytes() == b'', 'native raw stdout/stderr differs')
    for name, private_path in zip(('expected', 'actual'), argv[10:12]):
        matches = [item for item in command['artifacts'] if item['path'] == private_path]
        require(len(matches) == 1 and all(matches[0][key] == call['outputs'][name][key] for key in ('bytes', 'sha256')),
                'public capture does not match retained native command output')
    return dict(status=status, differences=differences, expected=left, actual=right, result=value, command=command,
                command_path=command_path, expected_path=left_path, actual_path=right_path)


def load_all(admission_path=HERE / 'admission.json'):
    admission_path = Path(admission_path).resolve()
    require(admission_path.is_relative_to(HERE.resolve()), 'admission escaped experiment')
    admission = load(admission_path)
    require(admission.get('schema') == 'hw-region-2-admission-v1' and admission.get('status') == 'KILL',
            'a completed actual KILL admission is required; source prediction/PASS/ERROR is insufficient')
    require(admission['no_clocks'] is True and admission['measurements_of_time'] is False
            and admission['performance_native_calls'] == 0 and admission['correctness_native_calls'] == 3
            and admission['forecasts'] == {key: 'NOT TESTED: Kill' for key in ('P1', 'P2', 'P3')}, 'timing/forecast admission scope differs')
    identity = admission['identity']
    require(identity['calibration_commit'] == CALIBRATION and identity['frozen_sources_commit'].startswith(FROZEN_SOURCES)
            and len(identity['frozen_sources_commit']) == 40 and identity['lib2bit_commit'] == PIN, 'first calibration/frozen source/library pin differs')
    expected_sources = {'evidence/hw-region-2/' + name for name in ('CALIBRATION.md', 'PROTOCOL.md', 'writer.py', 'equivalence.c', 'input-preflight.json', 'reproduce.py')} | {'LICENSE'}
    require(set(identity['source_sha256']) == expected_sources, 'incomplete frozen source closure')
    for name, expected in identity['source_sha256'].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT.resolve()) and valid_sha(expected), 'invalid source binding')
        raw = path.read_bytes()
        # The historical license can be CRLF-converted on a Windows checkout;
        # the driver binds canonical LF repository bytes on the Linux executor.
        if name == 'LICENSE' and digest(raw) != expected:
            raw = raw.replace(b'\r\n', b'\n')
        require(digest(raw) == expected, 'frozen admission source changed: ' + name)
    preflight = load(HERE / 'input-preflight.json')
    require(preflight['schema'] == 'hw-region-2-input-preflight-v1' and preflight['no_clocks'] is True and preflight['no_codecs'] is True
            and len(preflight['records']) == 31, 'full case-preserving input preflight missing')
    source = admission['source']
    require([row for row in preflight['records'] if row['corpus'] == 'chr1'] == [source]
            and source['alphabet']['n'] > 0 and source['first_lowercase_n'] is not None, 'admission/preflight source differs')
    dependency = admission['dependency']
    require(dependency['commit'] == PIN and dependency['url'] == 'https://github.com/dpryan79/lib2bit.git'
            and dependency['source_clean'] is True, 'upstream source was not the unmodified pinned library')
    source_files = {row['path']: row for row in dependency['source_files']}
    require(len(source_files) == len(dependency['source_files']) and source_files
            and all(valid_sha(row['sha256']) and integer(row['bytes']) for row in source_files.values()), 'invalid tracked upstream file inventory')
    for key, basename in (('license', 'LICENSE'), ('header', '2bit.h')):
        item = dependency[key]
        require(item['path'].replace('\\', '/').endswith('/' + basename) and source_files.get(item['path']) == item, 'upstream header/license binding differs')
    c_source = [row for row in source_files.values() if row['path'].replace('\\', '/').endswith('/2bit.c')]
    require(len(c_source) == 1, 'unique pinned upstream C source missing')
    inventory = {}
    public_inventory = {}
    for item in admission['artifacts']:
        require(item['path'] not in inventory and valid_sha(item['sha256']) and integer(item['bytes']), 'invalid/duplicate admission artifact')
        inventory[item['path']] = item
        if '/evidence/hw-region-2/' in item['path'].replace('\\', '/'):
            path = public_artifact(item)
            require(path not in public_inventory, 'duplicate public artifact path')
            public_inventory[path] = item
    for key in ('object', 'static_library', 'executable'):
        require(inventory.get(dependency[key]['path']) == dependency[key], 'compiled dependency/binary outside retained inventory')
    command_paths = set((HERE / 'commands').glob('*/command.json'))
    require(command_paths and command_paths <= public_inventory.keys(), 'orphan/unretained public command receipt')
    native_paths = set()
    for path in sorted(command_paths):
        command = load(path)
        require(command['status'] == 'COMPLETE' and command['returncode'] in command['identity']['allowed_returncodes'], 'unfinished/error admission command')
        for stream in ('stdout', 'stderr'):
            stream_path = path.parent / stream
            require(stream_path in public_inventory, 'command stream outside retained inventory')
        argv = command['identity']['argv']
        if len(argv) > 3 and argv[3] == dependency['executable']['path']:
            native_paths.add(path)
    require(len(native_paths) == 3 and len(admission['positive_controls']) == 2, 'extra/missing correctness query; no fourth native call is admitted')
    fixture_records = [row for path, row in public_inventory.items() if path == HERE / 'writer-metadata/fixture.json.gz']
    require(len(fixture_records) == 1, 'public fixture writer metadata missing')
    fixture = compressed_metadata(fixture_records[0])
    writer = compressed_metadata(admission['writer_metadata'])
    validate_writer(fixture, identity)
    validate_writer(writer, identity, source)
    require(fixture['sequence']['bytes'] == 16 and fixture['archive']['name'] == 'fixture', 'wrong positive fixture sequence')
    positives = [compare_capture(call, dependency['executable'], start, length, literal)
                 for call, start, length, literal in zip(admission['positive_controls'], (0, 8), (8, 2), (b'TCAGtcag', b'NN'))]
    require(all(item['status'] == 'PASS' for item in positives), 'positive API controls must precede Kill')
    start = source['first_lowercase_n'] - 8192
    require(start >= 0 and start + 16384 < source['sequence_bytes'], 'witness must be valid and nonterminal')
    witness = compare_capture(admission['witness'], dependency['executable'], start, 16384)
    require(witness['status'] == 'KILL' and witness['result']['first_difference0'] == source['first_lowercase_n'], 'actual first mismatch differs from full-source witness')
    require({item['command_path'] for item in positives + [witness]} == native_paths, 'native command inventory includes an additional call')
    fai = writer['fai']['geometry']
    first_byte = fai['offset'] + start // fai['line_bases'] * fai['line_width'] + start % fai['line_bases']
    last_base = start + 16384 - 1
    last_byte = fai['offset'] + last_base // fai['line_bases'] * fai['line_width'] + last_base % fai['line_bases'] + 1
    require(witness['result']['reference_byte_start'] == first_byte and witness['result']['reference_byte_span'] == last_byte - first_byte,
            'native plain-FASTA/.fai reference byte span differs')
    first0 = witness['result']['first_difference0']
    n_block = covering_interval(writer['archive']['n_blocks'], first0)
    mask_block = covering_interval(writer['archive']['mask_blocks'], first0)
    require(all(witness['expected'][i] == ord('n') and witness['actual'][i] == ord('N') for i in witness['differences']),
            'the captured Kill is not solely the claimed lowercase-n to uppercase-N difference')
    return dict(admission=admission, admission_path=admission_path, admission_sha256=sha(admission_path), source=source,
                dependency=dependency, c_source=c_source[0], writer=writer, fixture=fixture, positives=positives, witness=witness,
                first_n_block=n_block, first_mask_block=mask_block, public_artifacts=len(public_inventory),
                renderer_sha256=sha(__file__))


def line_number(path, needle):
    for index, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if needle in line:
            return index
    raise ValueError('foundation reference absent: ' + needle)


def relative(path):
    return Path(path).relative_to(HERE).as_posix()


def render(data):
    admission, source, writer, witness = (data[key] for key in ('admission', 'source', 'writer', 'witness'))
    value, fai = witness['result'], writer['fai']['geometry']
    start, length = value['start0'], value['length']
    n_start, n_size = data['first_n_block']
    mask_start, mask_size = data['first_mask_block']
    expected_count = witness['expected'].count(b'n')
    actual_count = witness['actual'].count(b'n')
    region_line = line_number(HERE.parent / 'hw-region-1/RESULTS.md', 'The primary chr1/g=16 KiB measurement')
    method_line = line_number(ROOT / 'docs/METHOD_PROGNOZ_ZADANIE.md', '## 2. Проверка метода')
    faidx_line = line_number(ROOT / 'review/axis3/bgzf_shim.c', 'char *p = faidx_fetch_seq64')
    lines = [SIGNATURE, '', '# HW-REGION-2 — equivalence Kill before timing', '',
        '**KILL confirmed by an actual successful `twobitSequence` call, not source inspection alone.** '
        'On the exact chr1 source, `storeMasked=1` returns uppercase `N` where the required reference contains lowercase `n`. '
        'The writer retains both the N interval and overlapping lowercase mask; its independent structural reader restores the full case-preserved sequence. '
        'The unchanged library API fails the mandatory result-equivalence condition.', '',
        '**P1: NOT TESTED: Kill. P2: NOT TESTED: Kill. P3: NOT TESTED: Kill.** '
        'No timing table, p50/p99 ranking, size-forecast verdict, or four-codec performance comparison is produced.', '',
        '## Actual saved witness', '',
        '- Sequence: `' + fai['name'] + '`, ' + str(source['sequence_bytes']) + ' bases; exact FASTA '
        + str(source['source_bytes']) + ' B, SHA256 `' + source['source_sha256'] + '`. '
        'Case-preserved sequence SHA256 `' + source['sequence_sha256'] + '`; preflight counts '
        + str(source['alphabet']['n']) + ' lowercase `n` over the full chromosome.',
        '- Query, zero-based half-open: **[' + str(start) + ', ' + str(start + length) + ')**, exactly '
        + str(length) + ' returned bases. The pointer was non-NULL and the returned string had the required length; '
        'the native program exited **2 (KILL)**, rather than **3 (method/input error)**.',
        '- First differing coordinate: **' + str(value['first_difference0']) + ' zero-based / '
        + str(value['first_difference1']) + ' one-based**; expected `' + chr(value['expected_byte']) + '` (ASCII '
        + str(value['expected_byte']) + ', hex `' + format(value['expected_byte'], '02x') + '`), actual `'
        + chr(value['actual_byte']) + '` (ASCII ' + str(value['actual_byte']) + ', hex `'
        + format(value['actual_byte'], '02x') + '`). Full captured-string mismatch count: **' + str(len(witness['differences'])) + '**; '
        'all differences are `n→N`. Expected/actual lowercase-`n` counts in this interval: '
        + str(expected_count) + ' / ' + str(actual_count) + '.',
        '- The first difference lies in **both** writer intervals: N block [' + str(n_start) + ', ' + str(n_start + n_size)
        + ') and lowercase-mask block [' + str(mask_start) + ', ' + str(mask_start + mask_size) + '). '
        'This information is present in the `.2bit` file; it was not lost by normalization or omitted by the writer.',
        '- Reference `.fai`: name `' + fai['name'] + '`, length ' + str(fai['length']) + ', byte offset '
        + str(fai['offset']) + ', line bases ' + str(fai['line_bases']) + ', line width ' + str(fai['line_width'])
        + '; the independent plain-FASTA reference reads byte span [' + str(value['reference_byte_start']) + ', '
        + str(value['reference_byte_start'] + value['reference_byte_span']) + ') and removes only CR/LF. Case is unchanged.', '',
        '[Complete reference capture](' + relative(witness['expected_path']) + ') '
        + '(SHA256 `' + admission['witness']['outputs']['expected']['sha256'] + '`) · '
        '[Complete actual capture](' + relative(witness['actual_path']) + ') '
        + '(SHA256 `' + admission['witness']['outputs']['actual']['sha256'] + '`) · '
        '[Native command/stdout](' + relative(witness['command_path']) + ') · [Admission](admission.json).', '',
        '## Controls and stop', '',
        'Two preceding successful nonterminal calls on the invented `TCAGtcagNNnnACTG` fixture returned '
        '`TCAGtcag` for [0,8) and `NN` for [8,10), exactly. The known packed bases are `1b1b0093`, '
        'with N [8,12) and mask [4,8),[10,12). These are correctness controls, not benchmark observations. '
        'The actual chr1 witness is also nonterminal, so a NULL/short EOF result cannot be mislabelled as this case mismatch.', '',
        'The retained inventory contains exactly **3 correctness-native calls**, including the two positive controls, '
        'and **0 performance-native calls / 0 clock calls**. The driver stops after this witness; no fourth query is admitted. '
        'Coordinate trace mapping, other-codec archive preparation, A/A, boundary-performance controls, warmup/query timing, '
        'open-time measurements, peak-RSS measurements, the main grid and the separate `storeMasked=0` row **were not run**. '
        'No reader patch, output postprocessing, case normalization, replacement sequence or Kent/UCSC binary was used.', '',
        'A generic byte-reader/capacity row does not qualify this required genome-coordinate operation. '
        'The four-way coordinate adapter, `codecs/twobit.sh` promotion and a new README performance row are withheld because the mandatory Kill fired. '
        'The previous byte-domain measurements remain their own evidence and do not supply missing coordinate timings.', '',
        '## Source and artifact provenance', '',
        'First unchanged calibration commit `' + admission['identity']['calibration_commit'] + '`; frozen admission source commit `'
        + admission['identity']['frozen_sources_commit'] + '`. The original writer is [Apache-2.0](../../LICENSE), '
        '[writer.py:1](writer.py#L1); lib2bit remains the clean, unmodified **MIT** source at `' + PIN + '`. '
        'The admission verifies the checkout pin and tracked source hashes before/after the build; this renderer rechecks the saved public source/receipt/capture bytes.', '',
        'The standard little-endian `.2bit` integer variant has magic bytes `' + struct.pack('<I', 0x1A412743).hex()
        + '`; packed bases remain MSB-first TCAG=00/01/10/11. This matches the pinned reader on the executor. '
        '[Format specification](https://genome.ucsc.edu/FAQ/FAQformat.html#format7) · '
        '[Full writer metadata](writer-metadata/chr1.json.gz) · [Fixture writer metadata](writer-metadata/fixture.json.gz). '
        'The structural whole-sequence restored SHA256 `' + writer['structural_check']['sha256'] + '` equals the preflight sequence SHA256.', '',
        '- Upstream C source SHA256: `' + data['c_source']['sha256'] + '`.',
        '- Upstream API header SHA256: `' + data['dependency']['header']['sha256'] + '`; MIT license SHA256: `'
        + data['dependency']['license']['sha256'] + '`.',
        '- Compiled object SHA256: `' + data['dependency']['object']['sha256'] + '`; static library SHA256: `'
        + data['dependency']['static_library']['sha256'] + '`.',
        '- Actual correctness executable SHA256: `' + data['dependency']['executable']['sha256'] + '`.',
        '- Exact `.2bit` archive: ' + str(writer['archive']['bytes']) + ' B, SHA256 `' + writer['archive']['sha256'] + '`; writer source SHA256: `'
        + writer['source_sha256'] + '`.',
        '- Admission SHA256: `' + data['admission_sha256'] + '`; saved-data renderer SHA256: `' + data['renderer_sha256'] + '`. '
        + str(data['public_artifacts']) + ' retained public artifacts were hash-checked.', '',
        'This admission ran on `' + admission['host']['hostname'] + '`, kernel `' + admission['host']['kernel']
        + '`, correctness/build CPU affinity `' + str(admission['host']['cpu_affinity']) + '`; '
        'the planned CPU0 / RAM performance experiment was never admitted.', '',
        '## Foundations', '',
        '- [HW-REGION-1/RESULTS.md:' + str(region_line) + '](../hw-region-1/RESULTS.md#primary-measured-tradeoff) '
        'retains the earlier chr1 **FASTA-byte** comparison on EPYC 4344P; its p50/p99 are not 16384-base coordinate measurements.',
        '- [docs/METHOD_PROGNOZ_ZADANIE.md:' + str(method_line) + '](../../docs/METHOD_PROGNOZ_ZADANIE.md#2-проверка-метода-до-основного-прогона) '
        'requires known-answer and correctness gates before the main run; [PROTOCOL.md](PROTOCOL.md) makes this admission stop explicit.',
        '- [lib2bit/2bit.h:90](' + BASE_URL + '2bit.h#L90) and [2bit.h:116](' + BASE_URL + '2bit.h#L116) '
        'document masked open and malloc-owned sequence retrieval; [2bit.c:126](' + BASE_URL + '2bit.c#L126) '
        'assigns N-block bases, [2bit.c:155](' + BASE_URL + '2bit.c#L155) excludes `N` from lowercasing, '
        'and [2bit.c:187–190](' + BASE_URL + '2bit.c#L187-L190) applies N masking before soft masking. '
        'The actual saved captures above, not the source prediction alone, determine Kill.',
        '- [review/axis3/bgzf_shim.c:' + str(faidx_line) + '](../../review/axis3/bgzf_shim.c#L' + str(faidx_line) + ') '
        'shows `faidx_fetch_seq64` with inclusive end; the proposed operation would use start+16384−1. '
        'That adapter and the other coordinate codecs were not executed after the failed admission.', '',
        '## Reproduction without another query', '',
        'From a completed owned admission checkout, the retained-data replay command verifies hashes and returns without invoking lib2bit again:', '',
        '```bash', 'taskset -c 15 python3 -B evidence/hw-region-2/reproduce.py', 'python3 -B evidence/hw-region-2/report.py', '```', '',
        '`reproduce.py` is a build/admission driver on a fresh checkout; its documented hash-only branch applies when the completed '
        '`admission.json` and retained artifacts already exist. Generating this report itself only reads saved JSON/gzip/capture files. '
        'No external issue/post or merge was performed.', '']
    return '\n'.join(line.rstrip() for line in lines).rstrip() + '\n'


def main():
    data = load_all()
    text = render(data)
    output = HERE / 'RESULTS.md'
    output.write_bytes(text.encode('utf-8'))
    print('SAVED_KILL_REPORT', sha(output))


if __name__ == '__main__':
    main()
