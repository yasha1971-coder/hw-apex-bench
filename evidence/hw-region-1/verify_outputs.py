"""Independent GNU dd+cmp proof of every retained region capture.

No experiment imports, codecs, clocks, Git or network. Reuses verified expected
traces across formats/g and replays finished dd work without running it again.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATE=ROOT/'.work/hw-region-1'
WORK=STATE/'independent-outputs'
R=16384


def require(ok,why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def load(path): return json.loads(Path(path).read_bytes())


def save(path,value):
    path=Path(path);raw=packed(value);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): require(path.read_bytes()==raw,'retained proof changed: '+str(path))
    else:
        with path.open('xb') as stream: stream.write(raw)


def owned(path):
    path=Path(path).resolve();require(path.is_relative_to(STATE.resolve()) and path.is_file(),'private file escaped owned state')
    return path


def expected(source,offsets,repeats):
    trace=hashlib.sha256(b''.join(struct.pack('<Q',off) for off in offsets)).hexdigest()
    identity=dict(input_sha256=source['sha256'],offsets=offsets,offsets_sha256=trace,request_bytes=R)
    key=hashlib.sha256(packed(identity)).hexdigest();folder=WORK/'expected';folder.mkdir(parents=True,exist_ok=True)
    base=folder/(key+'.bin');receipt=folder/(key+'.json')
    if receipt.exists():
        evidence=load(receipt);require(evidence['identity']==identity and sha(base)==evidence['sha256'],'cached dd expectation changed')
    else:
        require(not base.exists(),'incomplete dd output retained; inspect rather than overwrite')
        errors=hashlib.sha256();codes=[]
        with base.open('xb') as stream:
            for off in offsets:
                command=['dd','if='+source['path'],'bs=1M','iflag=skip_bytes,count_bytes','skip='+str(off),'count='+str(R),'status=none']
                result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE)
                codes.append(result.returncode);errors.update(result.stderr);result.check_returncode()
        require(base.stat().st_size==R*len(offsets),'dd returned an incomplete source trace')
        evidence=dict(identity=identity,path=str(base),bytes=base.stat().st_size,sha256=sha(base),dd_exitcodes=codes,
                      dd_command_template=['dd','if=SOURCE','bs=1M','iflag=skip_bytes,count_bytes','skip=OFFSET','count=16384','status=none'],
                      dd_stderr_sha256=errors.hexdigest())
        save(receipt,evidence)
    if repeats==1: return base,evidence
    require(repeats==2,'only two identical AA passes may reuse a base expectation')
    doubled=folder/(key+'-x2.bin');double_receipt=folder/(key+'-x2.json')
    if double_receipt.exists():
        value=load(double_receipt);require(value['base_sha256']==evidence['sha256'] and sha(doubled)==value['sha256'],'cached repeated expectation changed')
    else:
        require(not doubled.exists(),'incomplete repeated expectation retained')
        with doubled.open('xb') as out:
            for _ in range(2):
                with base.open('rb') as stream: shutil.copyfileobj(stream,out)
        value=dict(path=str(doubled),bytes=doubled.stat().st_size,sha256=sha(doubled),base_sha256=evidence['sha256'],repetitions=2)
        save(double_receipt,value)
    return doubled,value


def compare(left,right):
    identity=dict(expected_sha256=sha(left),actual_sha256=sha(right))
    key=hashlib.sha256(packed(identity)).hexdigest();receipt=WORK/'comparisons'/(key+'.json')
    if receipt.exists():
        value=load(receipt);require(value['identity']==identity and value['exitcode']==0,'cached cmp proof changed')
        return value
    command=['cmp','--',str(left),str(right)]
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    result.check_returncode()
    value=dict(identity=identity,command=command,exitcode=result.returncode,
               stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
    save(receipt,value);return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('primary','all'),required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();output=args.output or HERE/('audit/outputs-primary.json' if args.stage=='primary' else 'audit/outputs-final.json')
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'),'independent dd+cmp work runs outside the benchmark lock')
    setup_path=HERE/'setup.json';setup=load(setup_path)
    require((STATE/'setup.json').read_bytes()==setup_path.read_bytes(),'public/private setup differs')
    sources={};input_paths={}
    for corpus,item in setup['inputs'].items():
        path=owned(item['path']);require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'staged source identity differs')
        sources[item['sha256']]=item;input_paths[corpus]=path
    versions={tool:subprocess.check_output([tool,'--version']).decode().splitlines()[0] for tool in ('dd','cmp')}
    require('coreutils' in versions['dd'] and 'GNU' in versions['cmp'],'GNU dd and cmp required')
    documents={};captures=[];expectations={};comparisons={};codecs=set()
    schemas={'hw-region-1-observation-v1','hw-region-1-selfcheck-v1'}
    for path in sorted(HERE.rglob('*.json')):
        if path.is_relative_to(HERE/'audit'): continue
        value=load(path)
        if value.get('schema') not in schemas or 'returned' not in value: continue
        if args.stage=='primary' and (value['case_id']!='chr1-g16384' or value['mode'] not in ('check','probe')): continue
        require(value['status']=='PASS' and value['input_sha256'] in sources,'observation does not bind a staged source')
        source=sources[value['input_sha256']];rows=value['rows'];require(rows,'empty retained observation')
        offsets=[row['offset'] for row in rows]
        require(all(type(off)is int and 0<=off<=source['bytes']-R for off in offsets)
                and all(row['verified'] is True and row['requested_bytes']==R for row in rows),'invalid region bounds/verification')
        repeats=1
        if value['passes']==2:
            require(len(rows)==2000 and offsets[:1000]==offsets[1000:]
                    and all(row['pass']==i//1000 for i,row in enumerate(rows)),'AA output is not two identical ordered traces')
            offsets=offsets[:1000];repeats=2
        target=owned(value['returned']['path']);actual=sha(target)
        require(target.stat().st_size==value['returned']['bytes']==R*len(rows) and actual==value['returned']['sha256'],'captured output identity differs')
        expect,evidence=expected(source,offsets,repeats);cmp_proof=compare(expect,target)
        require(cmp_proof['identity']['actual_sha256']==actual,'cmp compared another capture')
        name=path.relative_to(HERE).as_posix();documents[name]=sha(path);codecs.add(value['codec'])
        expectations[evidence['sha256']]=evidence;comparisons[(evidence['sha256'],actual)]=cmp_proof
        captures.append(dict(document=name,sha256=actual,bytes=target.stat().st_size,rows=len(rows),expected_sha256=evidence['sha256']))
    require(captures and (args.stage!='primary' or codecs=={'aceapex','zstd_seekable','bgzip'}),'required region captures are incomplete')
    full=[]
    for path in sorted((HERE/'archives').glob('*.json')):
        case=load(path)
        if args.stage=='primary' and case['case_id']!='chr1-g16384': continue
        source=case['input'];require(source['sha256'] in sources,'archive restore source differs')
        for codec,archive in case['formats'].items():
            restored=Path(archive['path']).parent/(codec+'.restored')
            if restored.exists():
                restored=owned(restored);require(restored.stat().st_size==source['bytes'] and sha(restored)==source['sha256'],'full restored archive identity differs')
                full.append(dict(case_id=case['case_id'],codec=codec,proof=compare(owned(source['path']),restored)))
    result=dict(schema='hw-region-1-output-verification-v1',status='PASS',stage=args.stage,no_codecs=True,no_clocks=True,
                source_sha256=sha(__file__),setup_sha256=sha(setup_path),gnu_versions=versions,documents_sha256=documents,
                observation_references=len(captures),returned_regions=sum(c['rows'] for c in captures),captures=captures,
                unique_expected=len(expectations),expected=list(expectations.values()),unique_region_comparisons=len(comparisons),
                comparisons=list(comparisons.values()),optional_full_restores=full)
    save(output,result);print('OUTPUTS_PASS',args.stage,sha(output),len(captures),flush=True)


if __name__=='__main__': main()
