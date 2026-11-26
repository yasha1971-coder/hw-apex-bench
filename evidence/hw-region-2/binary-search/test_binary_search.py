# SPDX-License-Identifier: Apache-2.0
"""Untimed actual-C tests of the pinned casefix and binary-search softMask.

Only the two extracted softMask functions are compiled, using minimal structs.
No archive decoder, study worker, clock or performance measurement is called.
Run outside the benchmark lock; keep --workdir and its compiler/runtime logs.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
UPSTREAM_BLOB = '30631d05d305be8720ef3cc10a71a0d646163cfd'
CASEFIX_OLD = b"if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);"
CASEFIX_NEW = b'seq[pos] = tolower(seq[pos]);'
PATCH = HERE / 'lib2bit-binary-search.patch'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path.read_bytes()))


def write(path, raw):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == raw, 'retained synthetic artifact changed: ' + str(path))
    else:
        with path.open('xb') as output:
            output.write(raw)


def apply_patch(source, patch):
    """Apply this one-file unified diff exactly, without Git/patch subprocesses."""
    rows = patch.decode('utf-8').splitlines(keepends=True)
    require(rows[:2] == ['--- a/2bit.c\n', '+++ b/2bit.c\n'], 'unexpected patch target')
    original = source.decode('utf-8').splitlines(keepends=True)
    result, used, i, hunks = [], 0, 2, 0
    while i < len(rows):
        match = re.fullmatch(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n', rows[i])
        require(match is not None, 'malformed unified hunk')
        old_start, old_n, new_start, new_n = map(int, match.groups())
        require(old_start - 1 >= used, 'overlapping unified hunks')
        result.extend(original[used:old_start - 1]); used = old_start - 1
        require(len(result) == new_start - 1, 'new hunk position differs')
        old_count = new_count = 0; i += 1; hunks += 1
        while i < len(rows) and not rows[i].startswith('@@ '):
            kind, text = rows[i][:1], rows[i][1:]
            require(kind in (' ', '+', '-'), 'unsupported patch line')
            if kind in (' ', '-'):
                require(used < len(original) and original[used] == text, 'patch context differs')
                used += 1; old_count += 1
            if kind in (' ', '+'):
                result.append(text); new_count += 1
            i += 1
        require((old_count, new_count) == (old_n, new_n), 'unified hunk extent differs')
    require(hunks == 1, 'only the single softMask search hunk is permitted')
    result.extend(original[used:])
    return ''.join(result).encode('utf-8')


def extract_function(source):
    text = source.decode('utf-8'); first = text.index('void softMask(')
    brace = text.index('{', first); depth = 1; last = brace + 1
    while depth:
        require(last < len(text), 'unterminated softMask')
        depth += (text[last] == '{') - (text[last] == '}'); last += 1
    return text[first:last]


HARNESS = r'''
#include <ctype.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint32_t *maskBlockCount;
    uint32_t **maskBlockStart;
    uint32_t **maskBlockSizes;
} TwoBitMaskedIdx;
typedef struct { TwoBitMaskedIdx *idx; } TwoBit;

@LINEAR@

@BINARY@

/* Verbatim production search, with an independent linear index oracle below. */
static uint32_t candidate_index(TwoBit *tb, uint32_t tid, uint32_t start) {
    if(!tb->idx->maskBlockStart) return 0;
@SEARCH@
    return lo;
}

static uint64_t checks, index_checks, empty_checks, null_checks, n_lowered;
static uint32_t rng_state = UINT32_C(0x5eed2765);
static uint32_t random32(void) {
    uint32_t x = rng_state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return rng_state = x;
}
static void failure(const char *what, uint32_t start, uint32_t end, size_t at) {
    fprintf(stderr, "%s start=%"PRIu32" end=%"PRIu32" at=%zu\n", what,start,end,at);
    exit(1);
}
static void run_case(uint32_t *starts, uint32_t *sizes, uint32_t count,
                     uint32_t start, uint32_t end, int null_tables, unsigned phase) {
    enum { GUARD = 32 }; const unsigned char sentinel = 0xa7;
    static const unsigned char pattern[] = "ACGTNNacgtnn";
    if(end < start || end-start > 16384) failure("invalid synthetic query",start,end,0);
    uint64_t previous = 0;
    for(uint32_t k=0;k<count;k++) {
        uint64_t limit = (uint64_t)starts[k] + sizes[k];
        if(!sizes[k] || starts[k] < previous || limit > UINT32_MAX)
            failure("invalid sorted/nonoverlapping synthetic geometry",start,end,k);
        previous = limit;
    }
    size_t n = (size_t)(end-start), bytes = GUARD+n+1+GUARD;
    unsigned char *a = malloc(bytes), *b = malloc(bytes), *expected = malloc(bytes);
    if(!a || !b || !expected) failure("allocation",start,end,0);
    memset(a,sentinel,bytes);
    for(size_t j=0;j<n;j++) a[GUARD+j]=pattern[(j+phase)%(sizeof(pattern)-1)];
    a[GUARD+n]=0; memcpy(b,a,bytes); memcpy(expected,a,bytes);
    TwoBitMaskedIdx idx={&count,&starts,&sizes}; TwoBit tb={&idx};
    if(null_tables) { idx.maskBlockCount=NULL; idx.maskBlockStart=NULL; idx.maskBlockSizes=NULL; }
    uint32_t want=0;
    if(!null_tables) {
        while(want<count && (uint64_t)starts[want]+sizes[want] <= start) want++;
        for(size_t j=0;j<n;j++) {
            uint64_t coordinate=(uint64_t)start+j;
            for(uint32_t k=0;k<count;k++) {
                if(coordinate >= starts[k] && coordinate < (uint64_t)starts[k]+sizes[k]) {
                    if(expected[GUARD+j]=='N') n_lowered++;
                    expected[GUARD+j]=(unsigned char)tolower(expected[GUARD+j]);
                    break;
                }
            }
        }
    }
    uint32_t actual=candidate_index(&tb,0,start);
    if(actual!=want) failure("first intersecting index differs",start,end,actual);
    index_checks++;
    softMask_linear((char*)a+GUARD,&tb,0,start,end);
    softMask_binary((char*)b+GUARD,&tb,0,start,end);
    for(size_t j=0;j<bytes;j++) {
        if(a[j]!=expected[j] || b[j]!=expected[j])
            failure("linear/binary/oracle bytes or guards differ",start,end,j);
    }
    checks++; empty_checks+=(start==end); null_checks+=(null_tables!=0);
    free(a);free(b);free(expected);
}

int main(void) {
    uint32_t starts[]={3,11,15,31}, sizes[]={4,1,5,9};
    uint32_t adjacent[]={3,7,11}, adjacent_sizes[]={4,4,4};
    /* Every empty/nonempty interval: before/inside/end/after and multi-block. */
    for(uint32_t start=0;start<=48;start++) {
        for(uint32_t end=start;end<=48;end++) {
            for(unsigned phase=0;phase<3;phase++) {
                run_case(starts,sizes,4,start,end,0,phase);
                run_case(adjacent,adjacent_sizes,3,start,end,0,phase);
                run_case(NULL,NULL,0,start,end,0,phase);
            }
        }
    }
    /* storeMasked=0 absence: neither count nor per-contig pointers may be read. */
    run_case(NULL,NULL,0,0,0,1,0);run_case(NULL,NULL,0,10,25,1,1);
    /* Valid exclusive ends near UINT32_MAX; addition/index arithmetic stays safe. */
    uint32_t high[]={UINT32_MAX-90,UINT32_MAX-40}, high_sizes[]={20,40};
    for(uint32_t d=0;d<=100;d++) {
        uint32_t start=UINT32_MAX-d;
        for(uint32_t n=0;n<=d;n++) run_case(high,high_sizes,2,start,start+n,0,n%3);
    }
    /* Fixed seed, valid disjoint runs, many gaps and multiple touched blocks. */
    for(unsigned table=0;table<256;table++) {
        uint32_t s[64],z[64],count=random32()%65,position=0;
        for(uint32_t k=0;k<count;k++) {
            position+=random32()%13;s[k]=position;z[k]=1+random32()%19;position+=z[k];
        }
        uint32_t limit=position+64;
        for(unsigned q=0;q<128;q++) {
            uint32_t start=random32()%(limit+1), n=random32()%513;
            if(n>limit-start)n=limit-start;
            run_case(s,z,count,start,start+n,0,q%3);
        }
    }
    /* The production query length, independent of an archive or decoder. */
    uint32_t long_s[]={0,1024,8192,20000}, long_n[]={32,6000,4000,300};
    run_case(long_s,long_n,4,0,16384,0,0);run_case(long_s,long_n,4,4000,20384,0,1);
    if(!n_lowered || !empty_checks || null_checks!=2 || checks!=index_checks)
        failure("required coverage missing",0,0,0);
    printf("{\"status\":\"PASS\",\"byte_equality_cases\":%"PRIu64
           ",\"first_index_cases\":%"PRIu64",\"empty_ranges\":%"PRIu64
           ",\"null_table_cases\":%"PRIu64",\"masked_N_to_n_bytes\":%"PRIu64
           ",\"guard_bytes_each_side\":32,\"random_tables\":256,\"seed\":%"PRIu32"}\n",
           checks,index_checks,empty_checks,null_checks,n_lowered,UINT32_C(0x5eed2765));
    return 0;
}
'''


def make_harness(upstream):
    require(hashlib.sha1(b'blob '+str(len(upstream)).encode()+b'\0'+upstream).hexdigest() == UPSTREAM_BLOB,
            'source is not the exact pinned upstream Git blob')
    require(upstream.count(CASEFIX_OLD) == 1, 'casefix site is not unique')
    casefix = upstream.replace(CASEFIX_OLD, CASEFIX_NEW, 1)
    patch = PATCH.read_bytes()
    binary = apply_patch(casefix, patch)
    fixed_fn, binary_fn = extract_function(casefix), extract_function(binary)
    search_start = binary_fn.index('    uint32_t lo = 0, hi =')
    search_end = binary_fn.index('    for(i=lo;')
    search = binary_fn[search_start:search_end].rstrip()
    # Everything outside the search insertion and loop initializer is identical.
    restored = binary_fn[:search_start]+binary_fn[search_end:].replace('for(i=lo;', 'for(i=0;', 1)
    require(restored == fixed_fn, 'binary patch changed more than search/loop initialization')
    require(binary.replace(binary_fn.encode(), fixed_fn.encode(), 1) == casefix, 'patch changed code outside softMask')
    canonical = ''.join(difflib.unified_diff(casefix.decode().splitlines(True), binary.decode().splitlines(True),
                                          fromfile='a/2bit.c', tofile='b/2bit.c')).encode()
    require(canonical == patch, 'patch is not the exact casefix-to-binary unified diff')
    c = HARNESS.replace('@LINEAR@', fixed_fn.replace('void softMask(', 'static void softMask_linear(', 1))
    c = c.replace('@BINARY@', binary_fn.replace('void softMask(', 'static void softMask_binary(', 1)).replace('@SEARCH@', search)
    return c.encode(), dict(upstream_git_blob=UPSTREAM_BLOB, upstream_sha256=sha(upstream),
                           casefix_sha256=sha(casefix), binary_source_sha256=sha(binary), patch_sha256=sha(patch),
                           harness_sha256=sha(c.encode()))


def run_tests(source, workdir, cc='gcc'):
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'), 'synthetic build/tests must run outside the benchmark lock')
    workdir = Path(workdir).resolve(); workdir.mkdir(parents=True, exist_ok=True)
    c, identity = make_harness(Path(source).read_bytes())
    source_path = workdir/'softmask-synthetic.c'; binary = workdir/'softmask-synthetic'
    write(source_path,c)
    compiler = shutil.which(cc); require(compiler is not None, 'C compiler not found: '+cc)
    compiler = Path(compiler).resolve(); commands=[]
    def command(label, argv):
        proc = subprocess.run(list(map(str,argv)), cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = workdir/(label+'.stdout'), workdir/(label+'.stderr')
        write(out,proc.stdout);write(err,proc.stderr)
        commands.append(dict(argv=list(map(str,argv)), cwd=str(workdir), returncode=proc.returncode,
                             stdout=artifact(out), stderr=artifact(err)))
        require(proc.returncode == 0, 'synthetic command failed; inspect '+str(err))
        return proc.stdout
    version = command('compiler-version',[compiler,'--version']).decode().strip()
    command('compile',[compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror',source_path,'-o',binary])
    native = json.loads(command('run',[binary]));require(native['status']=='PASS','synthetic C checks failed')
    return dict(schema='hw-region-2-binary-search-synthetic-v1',status='PASS',no_clocks=True,
                measurements_of_time=False, archive_decodes=0, study_worker_calls=0,
                scope='extracted actual softMask functions only; valid sorted/disjoint metadata; public API and EOF not tested',
                source_sha256=sha(Path(__file__).read_bytes()), patch_sha256=identity['patch_sha256'], identity=identity, native=native,
                native_stdout=commands[-1]['stdout'], native_stderr=commands[-1]['stderr'],
                compiler=dict(executable=artifact(compiler),version=version), commands=commands,
                artifacts=dict(source=artifact(source_path),binary=artifact(binary)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source','--upstream',dest='source',type=Path,required=True)
    parser.add_argument('--workdir',type=Path,required=True);parser.add_argument('--output',type=Path)
    parser.add_argument('--cc',default='gcc');args=parser.parse_args()
    result=run_tests(args.source,args.workdir,args.cc)
    raw=(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode()
    if args.output:write(args.output,raw)
    print(raw.decode(),end='')


if __name__=='__main__':
    main()
