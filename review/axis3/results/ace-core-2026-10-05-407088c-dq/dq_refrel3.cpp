// dq_refrel3.cpp - Axis 3 window-law D_Q for ACEAPEX-refrel3 (refrel3 v1, research/refrel @ 5b6d5ce): full sequential
// decode with exactly one decode thread, in process; the decoded reference (T2T) and every archive resident in memory
// before timing (reference load, SHA-256 check and archive open with all FORMAT.md section 5 checks are outside the
// timed region). One run = full_v1(..., verify=false, threads=1) of every archive in order -> FASTA bytes in memory.
// After each run (outside timing) SHA-256 of every decoded FASTA (OpenSSL libcrypto SHA256) is compared with the
// reference SHA-256 of the source FASTA. Output: DQRUN lines (run, kind warmup|timed, seconds, bytes, per-archive
// seconds, SHA ok), DQGEOM lines (bases, blocks, FASTA bytes per archive).
//   dq_refrel3 <ref.fa> <warmups> <runs> <archive.rr3> <sha256 of its source FASTA> [...]
// Build: g++ -std=c++17 -O3 -march=native -funroll-loops -I<aceapex>/src -I<aceapex>/research/refrel
//        dq_refrel3.cpp <aceapex>/src/aceapex_api.cpp -lzstd -lpthread -l:libcrypto.so.3
#include "refrel3v1_nomain.cpp"   // = refrel3v1.cpp with line 243 "int main(" -> "static int refrel3v1_main(" (sed; see RUN.md)
extern "C" unsigned char* SHA256(const unsigned char* d, size_t n, unsigned char* md);
int main(int argc, char** argv) {
    if (argc < 6 || (argc - 4) % 2) { fprintf(stderr, "usage: dq_refrel3 <ref.fa> <warmups> <runs> <archive> <sha256> [...]\n"); return 1; }
    for (int c = 0; c < 256; c++) COMP[c] = rr_comp((uint8_t)c);
    const int WU = atoi(argv[2]), R = atoi(argv[3]);
    Ref ref = load_ref(argv[1], 1, false);
    struct A { std::string path, want; std::vector<uint8_t> bytes; V1 X; };
    std::vector<A> as((argc - 4) / 2);
    for (size_t i = 0; i < as.size(); i++) { as[i].path = argv[4 + 2 * i]; as[i].want = argv[5 + 2 * i]; as[i].bytes = slurp(as[i].path); std::string why;
        if (open_v1(as[i].bytes.data(), as[i].bytes.size(), ref, as[i].X, why)) { fprintf(stderr, "%s refused: %s\n", as[i].path.c_str(), why.c_str()); return 2; }
        printf("DQGEOM\t%s\tQ %u\tbases %llu\tblocks %llu\tarchive_bytes %zu\n", as[i].path.c_str(), as[i].X.Q, (unsigned long long)as[i].X.nbases, (unsigned long long)as[i].X.nb, as[i].bytes.size()); }
    fflush(stdout); int bad = 0;
    for (int r = 0; r < WU + R; r++) {
        std::vector<double> t(as.size()); std::vector<std::string> fa(as.size()); uint64_t out = 0; double tot = 0;
        for (size_t i = 0; i < as.size(); i++) { std::string s; const double t0 = now_s(); const int e = full_v1(as[i].X, ref, s, false, 1); t[i] = now_s() - t0;
            if (e) { fprintf(stderr, "decode error %d\n", e); return 3; } tot += t[i]; out += s.size(); fa[i].swap(s);
            if (i + 1 < as.size()) { } }
        int ok = 0; for (size_t i = 0; i < as.size(); i++) { unsigned char md[32]; SHA256((const unsigned char*)fa[i].data(), fa[i].size(), md); ok += hex(md, 32) == as[i].want; std::string().swap(fa[i]); }
        if (ok != (int)as.size()) bad++;
        printf("DQRUN\t%d\t%s\t%.6f\t%llu\t", r, r < WU ? "warmup" : "timed", tot, (unsigned long long)out);
        for (size_t i = 0; i < as.size(); i++) printf("%s%.6f", i ? "," : "", t[i]);
        printf("\tsha256 %d/%zu\n", ok, as.size()); fflush(stdout);
    }
    return bad ? 4 : 0;
}
