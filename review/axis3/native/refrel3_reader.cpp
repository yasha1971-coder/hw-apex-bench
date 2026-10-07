// Built against frozen refrel3v1.cpp @ 5b6d5cec0f5962a561ac48822a1b5c48793a5b47.
// This TU intentionally includes upstream implementation so static open_v1/block_v1 are used unchanged.
#include "refrel3v1.cpp"
#include <memory>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <mutex>

// Same decoder initialization as the retained dq_refrel3.cpp reference harness.
static std::once_flag hwa_rr3_comp_initialized;
static void hwa_rr3_initialize() {
    std::call_once(hwa_rr3_comp_initialized, [] {
        for (int c = 0; c < 256; ++c) COMP[c] = rr_comp(static_cast<uint8_t>(c));
    });
}
struct H { Ref ref; std::vector<uint8_t> arc; V1 x; std::vector<RrOp> ops; std::vector<uint8_t> lit,blk; H(const char*r,const char*a):ref(load_ref(r,1,false)),arc(slurp(a)),ops(RR_MAXOPS){} };
extern "C" void* hwa_rr3_open(const char* ref,const char* arc){try{hwa_rr3_initialize();auto h=std::make_unique<H>(ref,arc);std::string why;if(open_v1(h->arc.data(),h->arc.size(),h->ref,h->x,why))return nullptr;h->lit.resize(h->x.Q);h->blk.resize(h->x.Q);return h.release();}catch(...){return nullptr;}}
extern "C" long long hwa_rr3_length(void*p,const char*name){if(!p||!name)return-1;auto&x=((H*)p)->x;for(auto&r:x.rec)if(r.hdr.substr(0,r.hdr.find_first_of(" \t"))==name)return(long long)r.len;return-1;}
extern "C" long long hwa_rr3_fetch(void*p,const char*name,unsigned long long s,unsigned long long e,void*dst,size_t cap){if(!p||!name||!dst||s>=e||e-s>cap)return-1;H&h=*(H*)p;size_t ri=0;while(ri<h.x.rec.size()&&h.x.rec[ri].hdr.substr(0,h.x.rec[ri].hdr.find_first_of(" \t"))!=name)ri++;if(ri==h.x.rec.size()||e>h.x.rec[ri].len)return-1;const Rec&R=h.x.rec[ri];uint64_t lo=R.boff+s,hi=R.boff+e;auto*out=(uint8_t*)dst;size_t n=0;for(uint64_t b=lo/h.x.Q;b<=(hi-1)/h.x.Q;b++){if(block_v1(h.x,h.ref,b,h.blk.data(),h.ops,h.lit,true))return-2;uint64_t bs=b*h.x.Q,x0=std::max(lo,bs),x1=std::min<uint64_t>(hi,bs+h.x.Q);memcpy(out+n,h.blk.data()+x0-bs,x1-x0);n+=x1-x0;}return(long long)n;}
extern "C" unsigned hwa_rr3_q(void*p){return p?((H*)p)->x.Q:0;}
extern "C" void hwa_rr3_close(void*p){delete(H*)p;}

// B: whole-assembly canonical sequential decode. Reuse the frozen block decoder,
// hashes and the persistent handle. No reference load, worker thread or FASTA
// formatting is hidden in this call. Caller allocates destination before timing.
extern "C" unsigned long long hwa_rr3_size(void* context) {
    return context ? static_cast<H*>(context)->x.nbases : 0;
}
extern "C" long long hwa_rr3_decode(void* context, void* destination, size_t capacity) {
    if (!context || !destination) return -1;
    H& h = *static_cast<H*>(context);
    if (h.x.nbases > capacity || h.x.nbases > static_cast<uint64_t>(INT64_MAX)) return -1;
    try {
        auto* out = static_cast<uint8_t*>(destination);
        for (uint64_t b = 0; b < h.x.nb; ++b) {
            if (block_v1(h.x, h.ref, b, h.blk.data(), h.ops, h.lit, true)) return -2;
            const size_t n = static_cast<size_t>(std::min<uint64_t>(h.x.Q, h.x.nbases - b * h.x.Q));
            std::memcpy(out + b * h.x.Q, h.blk.data(), n);
        }
        return static_cast<long long>(h.x.nbases);
    } catch (...) { return -3; }
}
