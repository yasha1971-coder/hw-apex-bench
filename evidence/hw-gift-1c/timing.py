"""Optional single paired observation; selfcheck never reads a clock.

Both shared libraries use the same bridge, static zstd and native decoder.
Only the srcSizeHint line differs. Builds/correctness checks take no benchmark
lock. The worker must be launched by the retained OVH-BENCH lock helper.
"""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import run as study

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1c/timing'
LEVEL, FRAME = 3, 262144
VARIANTS = ('original', 'patched')
BRIDGE = r'''
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include "zstd_seekable.h"
#include <stdint.h>
#include <stddef.h>
/* The example's read-hint and output-buffer boundaries, over resident buffers. */
size_t probe_encode(ZSTD_seekable_CStream *ctx, const void *source, size_t size,
                    void *destination, size_t capacity) {
    const unsigned char *src = (const unsigned char *)source;
    unsigned char *dst = (unsigned char *)destination;
    const size_t input_capacity = ZSTD_CStreamInSize();
    const size_t output_capacity = ZSTD_CStreamOutSize();
    size_t offset = 0, used = 0, to_read = input_capacity;
    while (offset < size) {
        size_t amount = size - offset;
        ZSTD_inBuffer input;
        if (amount > to_read) amount = to_read;
        if (!amount) return (size_t)-1;
        input.src = src + offset; input.size = amount; input.pos = 0;
        while (input.pos < input.size) {
            size_t previous = input.pos, available = capacity - used;
            ZSTD_outBuffer output;
            if (!available) return (size_t)-1;
            if (available > output_capacity) available = output_capacity;
            output.dst = dst + used; output.size = available; output.pos = 0;
            to_read = ZSTD_seekable_compressStream(ctx, &output, &input);
            if (ZSTD_isError(to_read)) return to_read;
            if (to_read > input_capacity) to_read = input_capacity;
            used += output.pos;
            if (!output.pos && input.pos == previous) return (size_t)-1;
        }
        offset += amount;
    }
    for (;;) {
        size_t remaining, available = capacity - used;
        ZSTD_outBuffer output;
        if (!available) return (size_t)-1;
        if (available > output_capacity) available = output_capacity;
        output.dst = dst + used; output.size = available; output.pos = 0;
        remaining = ZSTD_seekable_endStream(ctx, &output);
        if (ZSTD_isError(remaining)) return remaining;
        used += output.pos;
        if (!remaining) return used;
        if (!output.pos) return (size_t)-1;
    }
}
'''


def check(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('wb') as stream:
        stream.write(packed(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def request():
    """Read-only admission and identity; no encoder calls and no clocks."""
    check(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    check(study.git('branch', '--show-current').decode().strip() == 'hw-gift-1c', 'wrong branch')
    protocol = HERE / 'TIMING_PROTOCOL.md'
    check(protocol.is_file(), 'commit TIMING_PROTOCOL.md before timing preparation')
    paths = [str(p.relative_to(ROOT)) for p in (Path(__file__), protocol)]
    check(not study.git('status', '--porcelain', '--', *paths).strip(), 'uncommitted timing instrument or protocol')
    commit = study.git('log', '-1', '--format=%H', '--', paths[1]).decode().strip()
    check(len(commit) == 40 and study.git('show', f'{commit}:{paths[1]}') == protocol.read_bytes(), 'timing protocol is not committed')
    check(study.git('rev-parse', 'HEAD', repo=study.ZSTD).decode().strip() == study.PIN, 'wrong zstd source pin')
    check(not study.git('status', '--porcelain', repo=study.ZSTD).strip(), 'original zstd source changed')
    study.require_controls()
    minimal = HERE / 'minimal-proof.json'
    check(json.loads(minimal.read_bytes())['status'] == 'PASS', 'minimal byte reproduction must pass before timing')
    controls_sha, proof_sha = file_sha(HERE / 'method-check.json'), file_sha(minimal)
    cases = []
    for chunk, frame in study.CASES:
        path = HERE / 'cases' / f'{chunk}-{frame}.json'
        value = json.loads(path.read_bytes())
        check(value['all_patched_frames_identical_to_pyzstd'] and value['normalized_patched_equals_pyzstd']
              and value['rebuilt_pyzstd_equals_patched'] and value['original_source_clean'], 'matrix must pass before optional timing')
        check(value['method_check_sha256'] == controls_sha and value['minimal_proof_sha256'] == proof_sha
              and file_sha(path.parent / value['frame_records_file']) == value['frame_records_sha256'],
              'matrix provenance or per-frame bytes changed')
        cases.append(dict(file=path.name, sha256=file_sha(path)))
    target = HERE / 'cases/enwik8-L3-262144.json'
    matrix = json.loads(target.read_bytes())
    return dict(protocol_commit=commit, protocol_sha256=file_sha(protocol), timing_py_sha256=file_sha(__file__),
                zstd_commit=study.PIN, static_library_sha256=file_sha(study.ZSTD / 'lib/libzstd.a'),
                method_check_sha256=controls_sha, minimal_proof_sha256=proof_sha, matrix=cases,
                target_matrix_sha256=file_sha(target), level=LEVEL, frame_bytes=FRAME,
                input_bytes=matrix['input_bytes'], input_sha256=matrix['input_sha256'],
                expected_archives={v: {k: matrix['archives'][v][k] for k in ('bytes', 'sha256')} for v in VARIANTS})


def build(allow_create=True):
    identity = request()
    source = study.ZSTD / 'contrib/seekable_format'
    original = (source / 'zstdseek_compress.c').read_bytes()
    before = b'ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize'
    check(original.count(before) == 1, 'one-line patch target changed')
    patched = original.replace(before, b'ZSTD_c_srcSizeHint, 0')
    decoder = (source / 'zstdseek_decompress.c').read_bytes()
    payloads = {'bridge.c': BRIDGE.encode(), 'original-compress.c': original,
                'patched-compress.c': patched, 'decompress.c': decoder}
    identity['source_sha256'] = {name: digest(data) for name, data in payloads.items()}
    receipt = STATE / 'build.json'
    if receipt.exists():
        saved = json.loads(receipt.read_bytes())
        check(saved['request'] == identity, 'timing build identity changed')
        for name, expected in identity['source_sha256'].items():
            check(file_sha(STATE / name) == expected, 'timing source copy changed')
        for name, value in saved['libraries'].items():
            check(file_sha(STATE / f'{name}.so') == value['sha256'], 'timing shared library changed')
        return saved
    check(allow_create, 'build timing libraries outside the shared benchmark lock before running the worker')
    check(not os.environ.get('OVH_BENCH_LOCK_HELD'), 'compilation must not hold the shared benchmark lock')
    STATE.mkdir(parents=True, exist_ok=True)
    check(not any((STATE / f'{v}.so').exists() for v in VARIANTS), 'unrecorded timing library; inspect rather than replace')
    for name, data in payloads.items():
        path = STATE / name
        if path.exists():
            check(path.read_bytes() == data, 'partial build source changed')
        else:
            path.write_bytes(data)
    libraries = {}
    for variant in VARIANTS:
        args = ['cc', '-O3', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror', '-Wl,-Bsymbolic',
                '-DXXH_NAMESPACE=ZSTD_', '-I' + str(source), '-I' + str(study.ZSTD / 'lib'),
                '-I' + str(study.ZSTD / 'lib/common'), str(STATE / 'bridge.c'),
                str(STATE / f'{variant}-compress.c'), str(STATE / 'decompress.c'),
                str(study.ZSTD / 'lib/libzstd.a'), '-pthread', '-o', str(STATE / f'{variant}.so')]
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (STATE / f'{variant}-build.stdout').write_bytes(result.stdout)
        (STATE / f'{variant}-build.stderr').write_bytes(result.stderr)
        result.check_returncode()
        libraries[variant] = dict(command=args, sha256=file_sha(STATE / f'{variant}.so'))
    compiler = subprocess.check_output(['cc', '--version']).decode().splitlines()[0]
    saved = dict(request=identity, libraries=libraries, compiler=compiler, measurements_of_time=False)
    save(receipt, saved)
    return saved


def load(variant):
    lib = ct.CDLL(str(STATE / f'{variant}.so'), mode=ct.RTLD_LOCAL)
    ptr, size = ct.c_void_p, ct.c_size_t
    bindings = {'ZSTD_versionNumber': ([], ct.c_uint), 'ZSTD_isError': ([size], ct.c_uint),
                'ZSTD_getErrorName': ([size], ct.c_char_p),
                'ZSTD_seekable_createCStream': ([], ptr),
                'ZSTD_seekable_initCStream': ([ptr, ct.c_int, ct.c_int, ct.c_uint], size),
                'ZSTD_seekable_freeCStream': ([ptr], size),
                'probe_encode': ([ptr, ptr, size, ptr, size], size),
                'ZSTD_seekable_create': ([], ptr), 'ZSTD_seekable_free': ([ptr], size),
                'ZSTD_seekable_initBuff': ([ptr, ptr, size], size),
                'ZSTD_seekable_decompress': ([ptr, ptr, size, ct.c_ulonglong], size)}
    for name, (args, returns) in bindings.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, returns
    check(lib.ZSTD_versionNumber() == 10507, 'timing library is not zstd 1.5.7')
    return lib


def native_check(lib, result):
    check(not lib.ZSTD_isError(result), lib.ZSTD_getErrorName(result).decode())


def evaluate(identity, clock=None):
    """Exactly one native encode and one native full decode per variant."""
    source = study.INPUTS / 'enwik8'
    raw = source.read_bytes()
    check(len(raw) == identity['input_bytes'] and digest(raw) == identity['input_sha256'], 'timing input changed')
    source_buffer = ct.create_string_buffer(raw, len(raw))
    # Fixed generous capacity, outside every interval. Every output page is
    # written before timing; internal first-use codec allocations remain inside.
    capacity = 2 * len(raw) + (1 << 20)
    slots, result = {}, {}
    try:
        for variant in VARIANTS:
            lib = load(variant)
            encoded, restored = ct.create_string_buffer(capacity), ct.create_string_buffer(len(raw))
            ct.memset(encoded, 0xA5, capacity)
            ct.memset(restored, 0xA5, len(raw))
            encoder = lib.ZSTD_seekable_createCStream()
            check(bool(encoder), 'fresh C encoder allocation failed')
            native_check(lib, lib.ZSTD_seekable_initCStream(encoder, LEVEL, 1, FRAME))
            slots[variant] = dict(lib=lib, encoded=encoded, restored=restored, encoder=encoder, decoder=None)
        for variant in VARIANTS:
            slot, elapsed = slots[variant], None
            if clock is not None:
                start = clock()
            length = slot['lib'].probe_encode(slot['encoder'], source_buffer, len(raw), slot['encoded'], capacity)
            if clock is not None:
                elapsed = clock() - start
            native_check(slot['lib'], length)
            check(length <= capacity, 'native encoder exceeded output capacity')
            data = ct.string_at(slot['encoded'], length)
            actual = dict(bytes=length, sha256=digest(data))
            check(actual == identity['expected_archives'][variant], 'native timing encoder differs from verified matrix: ' + variant)
            result[variant] = dict(archive=actual)
            if clock is not None:
                check(type(elapsed) is int and elapsed > 0, 'invalid compression clock interval')
                result[variant]['compression_elapsed_ns'] = elapsed
            slot['length'] = length
        for variant in VARIANTS:
            slot = slots[variant]
            decoder = slot['lib'].ZSTD_seekable_create()
            check(bool(decoder), 'fresh native decoder allocation failed')
            slot['decoder'] = decoder
            native_check(slot['lib'], slot['lib'].ZSTD_seekable_initBuff(decoder, slot['encoded'], slot['length']))
        for variant in VARIANTS:
            slot, elapsed = slots[variant], None
            if clock is not None:
                start = clock()
            length = slot['lib'].ZSTD_seekable_decompress(slot['decoder'], slot['restored'], len(raw), 0)
            if clock is not None:
                elapsed = clock() - start
            native_check(slot['lib'], length)
            check(length == len(raw), 'native full restore length differs: ' + variant)
            restored = ct.string_at(slot['restored'], length)
            restored_sha = digest(restored)
            check(restored == raw and restored_sha == identity['input_sha256'], 'native timing full restore differs: ' + variant)
            result[variant].update(bit_perfect=True, restored_bytes=length, restored_sha256=restored_sha)
            if clock is not None:
                check(type(elapsed) is int and elapsed > 0, 'invalid decompression clock interval')
                result[variant]['decompression_elapsed_ns'] = elapsed
    finally:
        for slot in slots.values():
            if slot['decoder']:
                slot['lib'].ZSTD_seekable_free(slot['decoder'])
            slot['lib'].ZSTD_seekable_freeCStream(slot['encoder'])
    return result


def selfcheck():
    saved = build()
    target = STATE / 'selfcheck.json'
    key = dict(build_sha256=file_sha(STATE / 'build.json'), request=saved['request'])
    if target.exists():
        old = json.loads(target.read_bytes())
        check(old['identity'] == key and old['status'] == 'PASS', 'saved native selfcheck changed')
        return old
    result = dict(status='PASS', measurements_of_time=False, identity=key,
                  variants=evaluate(saved['request'], clock=None), clock_calls=0)
    save(target, result)
    return result


def worker(output):
    check(os.environ.get('OVH_BENCH_LOCK_HELD') == '/run/lock/ovh-bench.lock', 'worker requires the shared OVH-BENCH lock')
    check(hasattr(os, 'sched_getaffinity') and os.sched_getaffinity(0) == {0}, 'timing worker must be pinned to CPU 0')
    output = output.resolve()
    check(output.is_relative_to(ROOT.resolve()) and not output.exists(), 'timing output must be new and inside this benchmark checkout')
    saved = build(allow_create=False)
    check_path = STATE / 'selfcheck.json'
    check(check_path.exists(), 'untimed native selfcheck must pass before the timed worker')
    control = json.loads(check_path.read_bytes())
    check(control['status'] == 'PASS' and control['clock_calls'] == 0
          and control['identity']['build_sha256'] == file_sha(STATE / 'build.json')
          and control['identity']['request'] == saved['request'], 'native selfcheck identity changed')
    import time
    result = dict(identity=saved['request'], build_sha256=file_sha(STATE / 'build.json'),
                  selfcheck_sha256=file_sha(check_path), measurements_of_time=True,
                  host=platform.node(), kernel=platform.release(), python=platform.python_version(),
                  cpu_affinity=[0], lock_path=os.environ['OVH_BENCH_LOCK_HELD'],
                  operation_order=['original.compress', 'patched.compress', 'original.decompress', 'patched.decompress'],
                  observations_per_operation=1, warmups=0, clock='time.perf_counter_ns', clock_calls=8,
                  timer_scope='one ctypes call over native API loop; context init, buffer prefault, hashing and byte checks excluded; internal first-use allocations included',
                  variants=evaluate(saved['request'], clock=time.perf_counter_ns))
    save(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'selfcheck', 'worker'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'worker':
        check(args.output is not None, '--output is required for a timed worker')
        result = worker(args.output)
    else:
        check(args.output is None, '--output belongs to the timed worker')
        result = build() if args.action == 'build' else selfcheck()
    print(json.dumps(result, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
