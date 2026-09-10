"""Build separate counting copies. Dependency checkouts and timed objects stay untouched."""
import hashlib, json, pathlib, shutil

def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError("Counter hook no longer matches pinned source: " + old)
    return source.replace(old, new)

def build_counters(D, compile, inc):
    ace = D / "aceapex" / "src"
    dst = D / "counter-aceapex"
    dst.mkdir(exist_ok=True)
    main = (ace / "aceapex_main.cpp").read_text()
    main = '#include <stdint.h>\nstatic unsigned cabench_ace_stream;\nstatic uint64_t cabench_ace_counts[4];\nextern "C" void cabench_ace_reset(void) { for(int i=0;i<4;i++) cabench_ace_counts[i]=0; }\nextern "C" uint64_t cabench_ace_bytes(unsigned i) { return cabench_ace_counts[i]; }\n' + main
    for marker in ("            uint8_t* dst=out+(d_off-win_lo);", "            uint8_t* d2=out+(off-win_lo);"):
        main = replace_once(main, marker, "            cabench_ace_counts[cabench_ace_stream] += raw;\n" + marker)
    api = (ace / "aceapex_api.cpp").read_text()
    for i, marker in enumerate(("    uint8_t* lit = lit_range(", "    uint8_t* off = fse_range(", "    uint8_t* len = fse_range(", "    uint8_t* cmd = fse_range(")):
        api = replace_once(api, marker, f"    cabench_ace_stream={i};\n" + marker)
    (dst / "aceapex_main.cpp").write_text(main)
    (dst / "aceapex_api.cpp").write_text(api)
    compile(["g++", "-O3", "-std=c++17", "-pthread", *inc, "-c", dst / "aceapex_api.cpp", "-o", D / "aceapex_count.o"])

    # Streaming API output excludes bytes still buffered inside zstd. Count
    # actual block reconstruction in both its streaming and fast one-shot paths.
    zsrc = D / "zstd"
    zdst = D / "counter-zstd"
    if zdst.exists(): shutil.rmtree(zdst)
    shutil.copytree(zsrc, zdst, ignore=shutil.ignore_patterns(".git", "obj", "*.o", "*.a", "*.so*"))
    p = zdst / "lib/decompress/zstd_decompress.c"
    z = p.read_text()
    z = '#include <stdint.h>\nstatic uint64_t cabench_zstd_count;\nvoid cabench_zstd_reset(void) { cabench_zstd_count=0; }\nuint64_t cabench_zstd_bytes(void) { return cabench_zstd_count; }\n' + z
    z = replace_once(z, '        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");',
                    '        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");\n        cabench_zstd_count += decodedSize;')
    z = replace_once(z, '            dctx->decodedSize += rSize;',
                    '            cabench_zstd_count += rSize;\n            dctx->decodedSize += rSize;')
    p.write_text(z)
    compile(["make", "-C", zdst / "lib", "-j4", "libzstd.a"])
    paths = [ace / "aceapex_main.cpp", ace / "aceapex_api.cpp", dst / "aceapex_main.cpp", dst / "aceapex_api.cpp",
             zsrc / "lib/decompress/zstd_decompress.c", p]
    hashes = {str(p.relative_to(D)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (D / "counter-sources.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return hashes
