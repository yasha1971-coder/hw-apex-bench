"""Native decoder workers, distinct from concurrent request emulation.

The current BGZF shim returns faidx_t* directly. One htslib pool is shared
by all cohort handles; pool destruction follows destruction of those handles.
Scalar reader APIs have no decoder-worker configuration and are unsupported
above one thread. No Python executors, request threads or codec substitutions.
"""
from __future__ import annotations
import ctypes
import os
from pathlib import Path


class NotSupported(ValueError):
    pass


def hardware():
    models = set()
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            key, sep, value = line.partition(':')
            if sep and key.strip() in ('model name', 'Hardware'):
                models.add(value.strip())
    return {'cpu_models': sorted(models),
            'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None}


def capability(family, threads):
    if type(threads) is not int or not 1 <= threads <= 256:
        raise ValueError('decoder_threads must be an integer in 1..256')
    if threads == 1:
        return {'status': 'SUPPORTED', 'api': 'scalar', 'reason': None}
    if family == 'bgzf':
        return {'status': 'SUPPORTED', 'api': 'htslib-fai-thread-pool', 'reason': None}
    return {'status': 'NOT_SUPPORTED', 'api': None,
            'reason': 'current pinned native reader exposes only a scalar decoder API'}


class PoolReader:
    def __init__(self, reader, threads):
        self.reader = reader
        self.decoder_threads = threads
        self.pool = None
        self.closed = False
        handles = [s.reader.inner for s in reader.singles.values()]
        if not handles:
            raise ValueError('empty BGZF cohort')
        self.lib = handles[0].lib
        if any(h.lib._name != self.lib._name for h in handles):
            raise ValueError('BGZF cohort must use the same pinned library')
        for name, args, restype in (
            ('hts_tpool_init', [ctypes.c_int], ctypes.c_void_p),
            ('hts_tpool_size', [ctypes.c_void_p], ctypes.c_int),
            ('hts_tpool_destroy', [ctypes.c_void_p], None),
            ('fai_thread_pool', [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int], ctypes.c_int)):
            try:
                f = getattr(self.lib, name)
            except AttributeError:
                raise NotSupported('pinned BGZF library lacks '+name) from None
            f.argtypes, f.restype = args, restype
        self.pool = self.lib.hts_tpool_init(threads)
        if not self.pool:
            raise MemoryError('hts_tpool_init failed')
        try:
            if self.lib.hts_tpool_size(self.pool) != threads:
                raise ValueError('native worker count differs from requested count')
            for h in handles:
                if self.lib.fai_thread_pool(h.handle, self.pool, 2*threads) != 0:
                    raise ValueError('fai_thread_pool refused BGZF handle')
        except BaseException:
            self.close()
            raise

    def __getattr__(self, name):
        return getattr(self.reader, name)

    def close(self):
        if self.closed:
            return
        # A pool still referenced by a live handle must never be destroyed.
        self.reader.close()
        self.closed = True
        self.reader._axis4_thread_closed = True
        if self.pool:
            self.lib.hts_tpool_destroy(self.pool)
            self.pool = None


def configure(reader, family, threads):
    cap = capability(family, threads)
    if cap['status'] != 'SUPPORTED':
        raise NotSupported(cap['reason'])
    if threads == 1:
        return reader
    try:
        return PoolReader(reader, threads)
    except BaseException:
        if not getattr(reader, "_axis4_thread_closed", False):
            reader.close()
        raise
