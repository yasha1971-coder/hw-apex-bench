"""Run from the scratch input directory with paths to built reader and encoder."""
import ctypes as c, hashlib, json, os, random, resource, struct, subprocess, sys
from pathlib import Path

def digest(data): return hashlib.sha256(data).hexdigest()

def worker(src,g,n,rep):
    arc=Path(src+'.zst').read_bytes()
    frames,flag,magic=struct.unpack_from('<IBI',arc,len(arc)-9)
    assert magic==0x8f92eab1 and flag==128
    table=len(arc)-9-12*frames
    sizes=[struct.unpack_from('<III',arc,table+12*i)[:2] for i in range(frames)]
    total=os.stat(src).st_size
    assert sum(s for s,d in sizes)==table-8 and sum(d for s,d in sizes)==total
    assert all(d==g for s,d in sizes[:-1]) and 0<sizes[-1][1]<=g
    dll=c.CDLL(os.environ['GIFT_LIB'])
    ptr=c.c_void_p; U=c.c_uint64
    for name,args,res in [('hc_open',[ptr,c.c_size_t,ptr,U],ptr),('hc_close',[ptr],None),('hc_region',[ptr,U,ptr,c.c_size_t],c.c_int64),('pair',[ptr,U,c.c_size_t,ptr,ptr,ptr],c.c_int)]:
        fn=getattr(dll,name); fn.argtypes=args; fn.restype=res
    a,b=(c.create_string_buffer(n) for _ in range(2)); ns=(c.c_int64*2)()
    if rep==-1:
        damaged=b'BAD!'+arc[4:]
        h=dll.hc_open(damaged,len(arc),None,total); assert h
        assert dll.hc_region(h,0,a,n)<0
        dll.hc_close(h)
        return dict(negative='native error',archive_sha256=digest(arc),archive_bytes=len(arc))
    rng=random.Random(2026112400+rep); samples=[]
    with open(src,'rb',buffering=0) as raw:
        for _ in range(1000):
            off=rng.randrange(total-n+1); h=dll.hc_open(arc,len(arc),None,total); assert h
            assert dll.pair(h,off,n,a,b,ns)==0
            dll.hc_close(h); raw.seek(off); expected=raw.read(n)
            assert a.raw==b.raw==expected
            samples.append([off,*ns])
    return dict(samples=samples,peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

if __name__=='__main__':
    os.sched_setaffinity(0,{0}); assert os.sched_getaffinity(0)=={0}
    if len(sys.argv)>1:
        print(json.dumps(worker(sys.argv[1],*map(int,sys.argv[2:])))); sys.exit()
    for src,sha in [('enwik8','2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),('silesia.tar','a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')]:
        assert digest(Path(src).read_bytes())==sha
    for src in ['enwik8','silesia.tar']:
        for level in (3,19):
            for g in (65536,262144,1048576,4194304,16777216,67108864):
                subprocess.run([os.environ['GIFT_ENC'],src,str(g),str(level)],check=True)
                for n in (4096,65536):
                    for rep in range(-1,5):
                        raw=subprocess.check_output([sys.executable,__file__,src,str(g),str(n),str(rep)])
                        row=dict(src=src,level=level,g=g,n=n,rep=rep,**json.loads(raw))
                        print(json.dumps(row,separators=(',',':')),flush=True)
