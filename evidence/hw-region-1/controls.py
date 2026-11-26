"""Untimed actual-boundary and persistent-cache controls for HW-REGION-1.

The metadata plan is fixed before probes. Counter observations never select a
more convenient boundary. No clock, encoding or native operation runs on import.
"""
import argparse
import os
from pathlib import Path
import struct

import instrument as codec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R = 16384
check, load, sha = codec.require, codec.load, codec.sha


def ref(path):
    path=Path(path).resolve()
    check(path.is_relative_to(HERE),'control reference escaped evidence')
    return dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path))


def source_bindings():
    name=Path(__file__).resolve().relative_to(ROOT).as_posix()
    codec.git('ls-files','--error-unmatch','--',name)
    check(not codec.git('status','--porcelain','--',name).strip(),'controls must be committed before execution')
    return dict(controls_sha256=sha(__file__),instrument_sha256=sha(HERE/'instrument.py'),
                worker_sha256=sha(HERE/'worker.c'),native_build_sha256=sha(HERE/'native/build.json'),
                setup_sha256=sha(HERE/'setup.json'),protocol_sha256=sha(HERE/'PROTOCOL.md'),
                calibration_sha256=sha(HERE/'CALIBRATION.md'))


def stream_geometry(data,is_lit):
    if len(data)<8:
        return dict(size=0,chunk=0,count=0)
    h=struct.unpack_from('<Q',data)[0]
    if is_lit and h&(1<<62):
        size=h&~((1<<62)|(1<<61)|(1<<60))
        chunk=struct.unpack_from('<Q',data,8)[0] if h&(1<<61) else (size+3)//4
        count=(size+chunk-1)//chunk if h&(1<<61) and chunk else 4
        table=16 if h&(1<<61) else 8
    else:
        size=h&((1<<48)-1); field=(h>>48)&0x7fff
        chunk=field*4096 if field else 524288
        count=(size+chunk-1)//chunk; table=8
    check(chunk>0 and table+8*count<=len(data),'invalid actual entropy-stream geometry')
    return dict(size=size,chunk=chunk,count=count)


def ace_plan(data,source_bytes):
    check(data[:8]==b'ACEPX2\0\0' and struct.unpack_from('<I',data,8)[0]==2,'primary ACE is not four-stream version2')
    size,g,n=struct.unpack_from('<QII',data,12)
    check(size==source_bytes and g==R and n==(size+g-1)//g,'primary ACE header geometry differs')
    lengths=struct.unpack_from('<QQQQ',data,36); start=68+64*n
    check(start+sum(lengths)<=len(data),'ACE stream extents outside archive')
    streams=[]
    for i,length in enumerate(lengths):
        streams.append(stream_geometry(data[start:start+length],i==0));start+=length

    def block(index):
        fields=struct.unpack_from('<8Q',data,68+64*index)
        selected=[]
        for stream,offset,length in zip(streams,fields[:4],fields[4:]):
            check(offset+length<=stream['size'],'ACE block stream slice outside decoded extent')
            selected.append(set(range(offset//stream['chunk'],(offset+length-1)//stream['chunk']+1)) if length else set())
        return selected

    # The first source block whose next block introduces an actual entropy
    # chunk is a deterministic archive-metadata rule, independent of counters.
    for b in range(n-1):
        aligned=b*g
        if aligned+2*R>source_bytes:
            break
        before,after=block(b),block(b+1)
        added=[sorted(y-x) for x,y in zip(before,after)]
        if any(added):
            return dict(codec='aceapex',rule='first adjacent outer blocks adding an actual decoded entropy chunk',
                        block_index=b,boundary=(b+1)*g,aligned_offset=aligned,crossing_offset=aligned+1,
                        next_miss_offset=(b+1)*g,streams=streams,
                        aligned_chunks=[sorted(x) for x in before],next_block_chunks=[sorted(x) for x in after],
                        new_chunks=added,request_bytes=R)
    raise ValueError('no valid actual ACE entropy-boundary negative control')


def seek_plan(data,source_bytes):
    count,descriptor,magic=struct.unpack('<IBI',data[-9:])
    check(count>1 and magic==0x8f92eab1 and descriptor==128,'invalid seekable footer/checksums')
    table=len(data)-17-12*count
    check(table>=0 and struct.unpack_from('<II',data,table)==(0x184d2a5e,12*count+9),'invalid actual seek table')
    offset=compressed=0
    for index in range(count-1):
        cn,dn,_=struct.unpack_from('<III',data,table+8+12*index)
        check(cn>0 and compressed+cn<=table,'seekable frame extent differs')
        boundary=offset+dn
        next_dn=struct.unpack_from('<I',data,table+8+12*(index+1)+4)[0]
        if dn>=R and next_dn>0 and boundary+1<=source_bytes:
            return dict(codec='zstd_seekable',rule='first native frame boundary with an R-byte preceding span',
                        unit_index=index,boundary=boundary,aligned_offset=boundary-R,crossing_offset=boundary-R+1,
                        preceding_decoded_bytes=dn,next_decoded_bytes=next_dn,request_bytes=R)
        offset=boundary;compressed+=cn
    raise ValueError('no valid native zstd-frame boundary control')


def bgzf_plan(data,source_bytes):
    p=offset=0; blocks=[]
    while p<len(data):
        check(len(data)-p>=26 and data[p:p+4]==b'\x1f\x8b\x08\x04','invalid BGZF block')
        cn=struct.unpack_from('<H',data,p+16)[0]+1
        check(cn>=26 and p+cn<=len(data),'BGZF compressed block extent differs')
        dn=struct.unpack_from('<I',data,p+cn-4)[0]
        blocks.append((offset,dn,cn));offset+=dn;p+=cn
    check(offset==source_bytes and p==len(data) and blocks[-1][1]==0,'BGZF full geometry/EOF differs')
    for index,((start,dn,_),(_,next_dn,_)) in enumerate(zip(blocks,blocks[1:])):
        if dn>=R and next_dn>0:
            boundary=start+dn
            return dict(codec='bgzip',rule='first actual BGZF boundary with an R-byte preceding span',
                        unit_index=index,boundary=boundary,aligned_offset=boundary-R,crossing_offset=boundary-R+1,
                        preceding_decoded_bytes=dn,next_decoded_bytes=next_dn,request_bytes=R)
    raise ValueError('no valid native BGZF boundary control')


def retained_probe(request,offsets,path):
    if path.exists():
        value=load(path);codec.validate_request(request)
        check(value['status']=='PASS' and value['request_sha256']==codec.digest(codec.packed(request))
              and value['clock_calls']==0 and value['measurements_of_time'] is False
              and [r['offset'] for r in value['rows']]==offsets
              and sha(value['returned']['path'])==value['returned']['sha256'],'saved boundary/cache probe changed')
        return value
    value=codec.counter_probe(request,offsets,path)
    check(value['clock_calls']==0 and value['measurements_of_time'] is False,'control read a timing clock')
    return value


def make_request(name):
    value=codec.request(HERE/'archives/chr1-g16384.json',name)
    path=HERE/'requests/chr1-g16384'/(name+'.json');codec.save(path,value)
    selfcheck_path=HERE/'selfchecks/chr1-g16384'/(name+'.json')
    checked=codec.untimed_selfcheck(value,selfcheck_path)
    check(checked['status']=='PASS' and checked['clock_calls']==0,'primary untimed selfcheck failed')
    return value,dict(request=ref(path),selfcheck=ref(selfcheck_path))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'controls.json')
    args=parser.parse_args()
    check(not os.environ.get('OVH_BENCH_LOCK_HELD'),'untimed controls run outside OVH benchmark lock')
    check(args.output.resolve().is_relative_to(HERE),'control output escaped evidence')
    identity=source_bindings()
    if args.output.exists():
        saved=load(args.output)
        check(saved['status']=='PASS' and saved['identity']==identity,'saved controls source cohort changed')
        for item in saved['evidence_refs']:
            path=HERE/item['path'];check(sha(path)==item['sha256'],'saved method evidence changed')
            value=load(path)
            if 'returned' in value: check(sha(value['returned']['path'])==value['returned']['sha256'],'saved returned control bytes changed')
        print('METHOD_CONTROLS_REPLAY',sha(args.output),flush=True);return
    results={};evidence=[]
    for name in codec.CODECS:
        request,record=make_request(name)
        evidence.extend((record['request'],record['selfcheck']))
        data=Path(request['archive']['path']).read_bytes()
        planner={'aceapex':ace_plan,'zstd_seekable':seek_plan,'bgzip':bgzf_plan}[name]
        plan=planner(data,request['input']['bytes'])
        plan_path=HERE/'controls'/(name+'-boundary-plan.json');codec.save(plan_path,plan);evidence.append(ref(plan_path))
        aligned_path=HERE/'controls'/(name+'-aligned.json');crossing_path=HERE/'controls'/(name+'-crossing.json')
        aligned=retained_probe(request,[plan['aligned_offset']],aligned_path)
        crossing=retained_probe(request,[plan['crossing_offset']],crossing_path)
        a,b=aligned['rows'][0],crossing['rows'][0]
        check(a['materialized_bytes']>0 and b['materialized_bytes']>a['materialized_bytes'],
              'actual boundary does not increase measured amplification: '+name)
        check(a['requested_bytes']==b['requested_bytes']==R,'boundary control request size differs')
        evidence.extend((ref(aligned_path),ref(crossing_path)))
        record.update(boundary_plan=ref(plan_path),aligned=ref(aligned_path),crossing=ref(crossing_path),
                      aligned_materialized_bytes=a['materialized_bytes'],crossing_materialized_bytes=b['materialized_bytes'],
                      amplification_increased=True,request_bytes=R)
        if name=='aceapex':
            hit_path=HERE/'controls/ace-cache-hit.json';miss_path=HERE/'controls/ace-two-misses.json'
            hit=retained_probe(request,[plan['aligned_offset']]*2,hit_path)
            misses=retained_probe(request,[plan['aligned_offset'],plan['next_miss_offset']],miss_path)
            check(hit['rows'][0]['materialized_bytes']>0 and hit['rows'][1]['materialized_bytes']==0
                  and hit['rows'][1]['zstd_calls']==hit['rows'][1]['zstd_bytes']==0,'ACE repeated-read cache known answer failed')
            check(all(row['materialized_bytes']>0 for row in misses['rows']),'ACE two distinct misses were not observed')
            check(all(row['oneshot_calls']==row['stream_calls']==0 and row['zstd_calls']==row['dctx_calls']
                      for value in (aligned,crossing,hit,misses) for row in value['rows']),'ACE API family differs from reused-DCtx constants')
            record.update(cache_hit=ref(hit_path),two_misses=ref(miss_path));evidence.extend((ref(hit_path),ref(miss_path)))
        results[name]=record
    known=codec.counter_known_answer();check(known['status']=='PASS' and known['clock_calls']==0,'actual zstd counter known answer failed')
    known_ref=ref(HERE/'controls/counter-known.json');evidence.append(known_ref)
    value=dict(schema='hw-region-1-controls-v1',status='PASS',clock_calls=0,measurements_of_time=False,
               identity=identity,**identity,case_id='chr1-g16384',codecs=results,counter_known=known_ref,evidence_refs=evidence)
    codec.save(args.output,value);print('METHOD_CONTROLS_PASS',sha(args.output),flush=True)


if __name__=='__main__':
    main()
