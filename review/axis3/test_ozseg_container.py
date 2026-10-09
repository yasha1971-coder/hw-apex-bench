#!/usr/bin/env python3
import hashlib,importlib.util,json,tempfile
from pathlib import Path
mod=Path(__file__).with_name("openzl_segmented.py")
spec=importlib.util.spec_from_file_location("ozseg",mod);oz=importlib.util.module_from_spec(spec);spec.loader.exec_module(oz)
assert oz.MAGIC == bytes.fromhex("4f5a534547310a") and len(oz.MAGIC)==7

def run(name,frames):
    meta={"schema":"openzl-segmented-v1","variant":"mock","level":1,"windowLog":16,"lz_window_bytes":65536,"Q":4,"uncompressed_bases":sum(map(len,frames)),"contigs":[],"frames":[]}
    payload=bytearray();u=0
    for x in frames:
        meta["frames"].append({"uoff":u,"ulen":len(x),"coff":len(payload),"clen":len(x)});payload+=x;u+=len(x)
    table=json.dumps(meta,separators=(",",":"),sort_keys=True).encode()
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/name;oz.write_container(p,table,payload);f,m,base=oz.read_container(p)
        assert m==meta
        assert p.read_bytes()[:8] == bytes.fromhex("4f5a534547310a01")
        rebuilt=b"".join((lambda x:(f.seek(base+x["coff"]),f.read(x["clen"]))[1])(x) for x in m["frames"])
        assert rebuilt==b"".join(frames)
        print("PASS",name,"segments",len(frames),"size",p.stat().st_size,"first8",p.read_bytes()[:8].hex())
for name,frames in {"zero":[],"one":[b"ABCD"],"three":[b"ABCD",b"EFGH",b"I"],"empty":[],"exact_q":[b"ABCD",b"EFGH"]}.items(): run(name,frames)
