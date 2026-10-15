// libagc 3.2.4, e67e3fc865a459779118d3d4e9fbdf42c70ba75e.
// Public API: src/lib-cxx/agc-api.h; GetCtgSeq implementation in lib-cxx.cpp.
// AGC start/end are ZERO-BASED INCLUSIVE. The wrapper accepts start0 + length.
#include "agc-api.h"
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <string>

namespace {
thread_local std::string last_error;
struct Handle { CAGCFile file; };
int64_t fail(const char* message) { last_error = message; return -1; }
}
extern "C" const char* hwa_agc_error() { return last_error.c_str(); }
extern "C" const char* hwa_agc_version() {
    return "libagc-3.2.4@e67e3fc865a459779118d3d4e9fbdf42c70ba75e";
}
extern "C" void* hwa_agc_open(const char* path, int prefetch) {
    last_error.clear();
    try {
        if (!path) { fail("null archive path"); return nullptr; }
        auto h = std::make_unique<Handle>();
        if (!h->file.Open(path, prefetch != 0)) { fail("AGC open refused"); return nullptr; }
        return h.release();
    } catch (const std::exception& e) { fail(e.what()); return nullptr; }
      catch (...) { fail("AGC open exception"); return nullptr; }
}
extern "C" int64_t hwa_agc_length(void* context, const char* sample, const char* contig) {
    try {
        if (!context || !sample || !*sample || !contig || !*contig)
            return fail("explicit sample and contig names are required");
        int n = static_cast<Handle*>(context)->file.GetCtgLen(sample, contig);
        return n < 0 ? fail("unknown contig or length outside libagc int API") : n;
    } catch (const std::exception& e) { return fail(e.what()); }
      catch (...) { return fail("AGC length exception"); }
}
extern "C" int64_t hwa_agc_fetch(void* context, const char* sample, const char* contig,
                                 uint64_t start0, uint64_t length, void* destination,
                                 size_t capacity) {
    last_error.clear();
    try {
        const int64_t total = hwa_agc_length(context, sample, contig);
        if (total < 0) return -1;
        if (!destination || length == 0 || capacity < length || start0 > uint64_t(total)
            || length > uint64_t(total) - start0)
            return fail("window outside contig or destination capacity");
        const uint64_t end0_inclusive = start0 + length - 1;
        if (end0_inclusive > uint64_t(std::numeric_limits<int>::max()))
            return fail("window exceeds libagc signed-int coordinate API");
        std::string bases;
        const int rc = static_cast<Handle*>(context)->file.GetCtgSeq(
            sample, contig, int(start0), int(end0_inclusive), bases);
        if (rc != 0 || bases.size() != length) return fail("AGC short or failed decode");
        std::memcpy(destination, bases.data(), bases.size());
        return int64_t(bases.size());
    } catch (const std::exception& e) { return fail(e.what()); }
      catch (...) { return fail("AGC decode exception"); }
}
extern "C" void hwa_agc_close(void* context) {
    // RAII releases the library object, unlike the public C close-only function.
    delete static_cast<Handle*>(context);
}
