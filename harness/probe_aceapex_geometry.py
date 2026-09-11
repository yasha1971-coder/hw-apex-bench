#!/usr/bin/env python3
"""Untimed diagnosis of the pinned ACEAPEX one-shot encoder header."""
import argparse
import ctypes
import json
import os
import struct


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', default='.adapter-work/build/aceapex/plugin.so')
    args = p.parse_args()
    os.environ.update(ACEAPEX_BS='16384', LIT_CHUNK='65536', FSE_CHUNK='4096', MIN_MATCH='0')
    library = ctypes.CDLL(args.library)
    encode = library.aceapex_compress
    encode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                       ctypes.c_size_t, ctypes.c_int, ctypes.c_int]
    encode.restype = ctypes.c_int64
    source = bytes(range(256))*1025
    output = ctypes.create_string_buffer(len(source)*2+1048576)
    written = encode(source, len(source), output, len(output), 2, 1)
    if written < 68:
        raise RuntimeError(f'encoder returned {written}')
    block, count = struct.unpack_from('<II', output.raw, 20)
    print(json.dumps(dict(requested_block=16384, header_block=block,
                         num_blocks=count, input_bytes=len(source),
                         expected_blocks=(len(source)+16383)//16384,
                         timed=False), indent=2))


if __name__ == '__main__':
    main()
