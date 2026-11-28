# SPDX-License-Identifier: Apache-2.0
"""Replay the accepted TB-LVL-0 public evidence using stdlib and saved bytes.

Only the unchanged original audit.py, analysis.py and audit.py are executed in
an isolated temporary tree. No runner, build script, codec or corpus is used.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

SOURCE='25f9459c87485a1d47950ebea031e39ec441942a'
PREFIX='evidence/tb-lvl-0/'
EXTERNAL={'.github/workflows/tb-lvl-0-build.yml','evidence/hw-region-2/casefix/audit.py','evidence/hw-region-2/casefix/ovh_bench.py'}
ACCEPTED={'audit.json':'ab9755b1c5bb5cff3fc320a5d0273139463b1ea30b7ebe735694d1b3a165186b',
 'analysis.json':'7eae0ddc10e9322e40930acf2c093d5651a7f61d194e9909d8da3f42b56f33bd',
 'RESULTS.md':'e25d72e3e484d3606e4d47f4d5935b994f7492f878d06043ffb9fad8e4af6495'}
MAX_BYTES=200*1024*1024
MAX_FILES=5000
FILE_COUNT=3245
TOTAL_BYTES=100401327
EXTRA=dict(path='evidence/tb-lvl-0/adapters/turbobench-plugin.cc',bytes=221439,
 sha256='f4e89305920013c61de3fdbe1ce220b2b0851b0ea86c5c8d6b40e8bb813e4ba2',
 git_oid='b9c30832f73e4997f24d8e2c55ab086a6ddc1a18',repository='powturbo/TurboBench',
 commit='4aa97c8c37311e399ea3e7782c18c652c5bdb69f',path_in_repo='plugin.cc')
MIRRORS={PREFIX+name:PREFIX+name for name in (
 'CALIBRATION.md','PROTOCOL.md','GRID_AMENDMENT.md','RESULTS.md','analysis.json','audit.json',
 'runner.py','build_static.py','analysis.py','audit.py','build/build.json','build/go.mod')}
ADAPTER_MIRRORS={PREFIX+'adapters/telemetry_audit.py':'evidence/hw-region-2/casefix/audit.py',
                 PREFIX+'adapters/ovh_bench.py':'evidence/hw-region-2/casefix/ovh_bench.py'}
MIRRORS.update(ADAPTER_MIRRORS)


def require(ok,reason):
    if not ok:raise ValueError(reason)


def unique(pairs):
    out={}
    for key,value in pairs:
        require(key not in out,'duplicate JSON key: '+key);out[key]=value
    return out


def load(path):return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def packed(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def git_oid(kind,raw):return hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def integer(value):return type(value) is int and value>=0
def oid(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{40}',value) is not None


def safe_name(name):
    require(isinstance(name,str) and name and '\\' not in name and ':' not in name and '\0' not in name,'unsafe path')
    parts=name.split('/')
    require(not name.startswith('/') and all(p not in ('','.','..') and not p.endswith((' ','.')) for p in parts),'unsafe path components: '+name)
    reserved={'CON','PRN','AUX','NUL'}|{x+str(i) for x in ('COM','LPT') for i in range(1,10)}
    require(all(p.split('.')[0].upper() not in reserved for p in parts),'Windows-reserved path: '+name)
    require(PurePosixPath(name).as_posix()==name,'noncanonical POSIX path')
    return parts


def under(root,name):
    parts=safe_name(name);root=Path(root).resolve();path=root.joinpath(*parts)
    require(path.resolve().is_relative_to(root),'path escaped root')
    # Loose mirrors must not redirect reads through a symlink either.
    current=root
    for part in parts:
        current=current/part;require(not current.is_symlink(),'symlink path component: '+name)
    return path


def file_map(records):
    require(isinstance(records,list) and 0<len(records)<=MAX_FILES,'file count bound')
    out={};folded=set();total=0
    for row in records:
        name=row['path'];safe_name(name)
        require(name.startswith(PREFIX) or name in EXTERNAL,'source path outside frozen closure: '+name)
        require(name not in out and name.casefold() not in folded,'duplicate/case-alias source path')
        require(row['mode'] in ('100644','100755') and integer(row['bytes']) and oid(row['git_oid'])
                and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'invalid file identity')
        out[name]=row;folded.add(name.casefold());total+=row['bytes']
    require(total<=MAX_BYTES,'source byte bound exceeded')
    return out


def parse_tree(raw):
    entries={};pos=0
    while pos<len(raw):
        space=raw.index(b' ',pos);zero=raw.index(b'\0',space+1)
        mode=raw[pos:space].decode('ascii');name=raw[space+1:zero].decode('utf-8')
        require('/' not in name,'slash in Git tree entry');safe_name(name)
        require(mode in ('40000','100644','100755','120000','160000') and zero+21<=len(raw),'malformed Git tree')
        require(name not in entries,'duplicate Git tree name')
        entries[name]=(mode,raw[zero+1:zero+21].hex());pos=zero+21
    return entries


def verify_git(bundle,files):
    raw=base64.b64decode(bundle['git']['commit_base64'],validate=True)
    require(git_oid('commit',raw)==SOURCE==bundle['source_commit'],'source commit object differs')
    first=raw.split(b'\n',1)[0];require(re.fullmatch(rb'tree [0-9a-f]{40}',first) is not None,'source commit tree missing')
    root=first[5:].decode();trees={};used=set()
    require(len(bundle['git']['trees'])<=MAX_FILES,'tree count bound')
    for item in bundle['git']['trees']:
        data=base64.b64decode(item['base64'],validate=True)
        require(oid(item['oid']) and git_oid('tree',data)==item['oid'] and item['oid'] not in trees,'Git tree object hash/duplicate differs')
        trees[item['oid']]=parse_tree(data)
    def tree(ident):
        require(ident in trees,'missing required Git tree object: '+ident);used.add(ident);return trees[ident]
    def resolve(path):
        ident=root;parts=safe_name(path)
        for i,part in enumerate(parts):
            entries=tree(ident);require(part in entries,'file absent from source tree: '+path)
            mode,ident=entries[part]
            if i<len(parts)-1:require(mode=='40000','source ancestor is not a directory')
        return mode,ident
    mode,tb=resolve(PREFIX.rstrip('/'));require(mode=='40000','TB closure is not a tree')
    leaves={}
    def walk(ident,prefix,ancestors):
        require(ident not in ancestors,'cyclic Git tree')
        for name,(mode,child) in tree(ident).items():
            path=prefix+name
            if mode=='40000':walk(child,path+'/',ancestors|{ident})
            else:
                require(mode in ('100644','100755'),'nonregular original TB entry')
                leaves[path]=(mode,child)
    walk(tb,PREFIX,set())
    for name in EXTERNAL:leaves[name]=resolve(name)
    require(set(leaves)==set(files),'manifest omits/adds an original source leaf')
    for name,row in files.items():require(leaves[name]==(row['mode'],row['git_oid']),'manifest Git membership differs: '+name)
    require(used==set(trees),'unrelated Git tree objects included')
    return dict(commit=SOURCE,root_tree=root,verified_trees=len(trees),verified_leaves=len(leaves))


def safe_extract(archive,records,destination):
    files=file_map(records);seen=set();total=0
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            name=member.name;safe_name(name)
            require(name in files and name not in seen,'unexpected/duplicate archive member: '+name)
            require(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE) and not member.linkname
                    and not member.pax_headers and member.sparse is None,'only regular non-PAX archive members are allowed')
            row=files[name];require(member.mode==int(row['mode'],8)&0o777 and member.size==row['bytes'],'archive mode/length differs')
            total+=member.size;require(total<=MAX_BYTES and len(seen)<MAX_FILES,'archive expansion bound')
            stream=tar.extractfile(member);require(stream is not None,'archive member has no data')
            path=under(destination,name);path.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256();g=hashlib.sha1(b'blob '+str(member.size).encode()+b'\0');count=0
            with path.open('xb') as out:
                while True:
                    block=stream.read(1<<20)
                    if not block:break
                    count+=len(block);require(count<=member.size,'member exceeds declared size');h.update(block);g.update(block);out.write(block)
            require(count==row['bytes'] and h.hexdigest()==row['sha256'] and g.hexdigest()==row['git_oid'],'archive member content differs: '+name)
            if os.name!='nt':path.chmod(int(row['mode'],8)&0o777)
            seen.add(name)
    require(seen==set(files),'archive omits source members')
    return total


def validate_mirror_map(records,expected):
    require(isinstance(records,list) and len(records)==len(expected),'required mirror set differs')
    actual={}
    for row in records:
        require(isinstance(row,dict) and set(row)=={'path','source_path'},'mirror fields differ')
        safe_name(row['path']);safe_name(row['source_path'])
        require(row['path'] not in actual,'duplicate loose mirror')
        actual[row['path']]=row['source_path']
    require(actual==expected,'frozen mirror mapping differs')


def verify_adapter_sources(root):
    name=PREFIX+'adapters/SOURCES.json';path=under(root,name);raw=path.read_bytes()
    value=json.loads(raw,object_pairs_hook=unique)
    require(isinstance(value,dict) and set(value)=={'schema','source_commit','mirrors','upstream'}
            and value['schema']=='tb-lvl-0-adapter-sources-v1' and value['source_commit']==SOURCE,
            'adapter SOURCES schema/source differs')
    validate_mirror_map(value['mirrors'],ADAPTER_MIRRORS)
    require(value['upstream']==[EXTRA],'adapter SOURCES upstream pin differs')
    return dict(path=name,bytes=len(raw),sha256=digest(raw))


def verify_mirrors(root,extracted,mirrors):
    validate_mirror_map(mirrors,MIRRORS)
    seen=set()
    for row in mirrors:
        require(row['path'] not in seen,'duplicate loose mirror');seen.add(row['path'])
        outer=under(root,row['path']);source=under(extracted,row['source_path'])
        require(source.is_file() and outer.is_file() and outer.read_bytes()==source.read_bytes(),'loose mirror differs: '+row['path'])
    return sorted(seen)


def verify_extras(root,records):
    require(records==[EXTRA],'extra source pin/identity differs')
    for row in records:
        path=under(root,row['path']);raw=path.read_bytes()
        require(len(raw)==row['bytes'] and digest(raw)==row['sha256'] and git_oid('blob',raw)==row['git_oid'],'extra source snapshot differs')


def accepted_bytes(stage):
    return {name:(stage/name).read_bytes() for name in ACCEPTED}


def check_accepted(data):
    require(set(data)==set(ACCEPTED),'accepted output set differs')
    for name,raw in data.items():require(digest(raw)==ACCEPTED[name],'accepted output bytes differ: '+name)


def replay(root):
    root=Path(root).resolve();stage=under(root,PREFIX.rstrip('/'));manifest_path=under(root,PREFIX+'BUNDLE.json')
    require(manifest_path.stat().st_size<=MAX_BYTES,'bundle metadata bound exceeded')
    manifest_raw=manifest_path.read_bytes();bundle=json.loads(manifest_raw,object_pairs_hook=unique)
    require(bundle['schema']=='tb-lvl-0-source-bundle-v1' and bundle['source_commit']==SOURCE and bundle['source_pr']==98,'wrong source bundle')
    require(bundle['accepted']==ACCEPTED and bundle['source_file_count']==FILE_COUNT and bundle['source_total_bytes']==TOTAL_BYTES,'frozen source/output anchors differ')
    files=file_map(bundle['files']);require(len(files)==FILE_COUNT and sum(r['bytes'] for r in files.values())==TOTAL_BYTES,'source inventory totals differ')
    git=verify_git(bundle,files)
    archive_record=bundle['archive'];require(archive_record['path']=='evidence.tar.gz' and integer(archive_record['bytes']) and archive_record['bytes']<=MAX_BYTES,'wrong archive path/size')
    archive=under(stage,archive_record['path'])
    require(archive.stat().st_size==archive_record['bytes'] and sha(archive)==archive_record['sha256'],'archive SHA/length differs')
    verify_extras(root,bundle['extra_sources'])
    # The full packaging contract is frozen independently of the editable
    # manifest; regenerating the proof cannot waive any source/adapter mirror.
    validate_mirror_map(bundle['mirrors'],MIRRORS)
    adapter_sources=verify_adapter_sources(root)
    work=root/'.work';require(not work.is_symlink(),'temporary parent must not be a symlink');work.mkdir(exist_ok=True)
    require(work.resolve().is_relative_to(root),'temporary parent escaped root')
    with tempfile.TemporaryDirectory(prefix='tb-lvl-0-replay-',dir=work) as folder:
        temporary=Path(folder);total=safe_extract(archive,bundle['files'],temporary)
        mirrors=verify_mirrors(root,temporary,bundle['mirrors']);original=accepted_bytes(temporary/PREFIX);check_accepted(original)
        commands=[]
        for script in ('audit.py','analysis.py','audit.py'):
            path=temporary/PREFIX/script
            argv=[sys.executable,'-X','utf8','-B',str(path)]
            environment=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
            environment.pop('PYTHONPATH',None);environment.pop('PYTHONHOME',None)
            result=subprocess.run(argv,cwd=temporary,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
            require(result.returncode==0,'original '+script+' failed: '+(result.stderr+result.stdout).decode('utf-8',errors='replace')[-3000:])
            commands.append(dict(script=PREFIX+script,python_flags=['-X','utf8','-B'],returncode=0))
            if script=='audit.py':require((temporary/PREFIX/'audit.json').read_bytes()==original['audit.json'],'original audit is not byte-stable')
        rebuilt=accepted_bytes(temporary/PREFIX);check_accepted(rebuilt)
        require(rebuilt==original,'replay changed accepted output bytes')
        # Audit/analysis may only replace their three expected generated files.
        for name,row in files.items():require(sha(temporary/name)==row['sha256'],'original replay changed archival input: '+name)
        audit=json.loads(rebuilt['audit.json'],object_pairs_hook=unique);analysis=json.loads(rebuilt['analysis.json'],object_pairs_hook=unique)
        require(audit['status']=='PASS' and audit['completion']=='COMPLETE' and analysis['status']=='COMPLETE','accepted completion differs')
        require(audit['counts']['accepted_main_roundtrips']==150 and audit['counts']['actual_attempts']==152
                and audit['counts']['loaded_attempts']==1 and audit['counts']['retaken_units']==1
                and analysis['completed_configurations']==50,'accepted replay counts differ')
    return dict(schema='tb-lvl-0-rebuild-audit-v1',status='PASS',source_commit=SOURCE,source_pr=98,
        saved_data_only=True,no_native_calls=True,no_codecs=True,no_git=True,no_network=True,corpus_required=False,
        verifier_sha256=sha(Path(__file__)),
        bundle_sha256=digest(manifest_raw),archive=archive_record,source_file_count=len(files),source_total_bytes=total,
        git=git,mirrors=mirrors,adapter_sources=adapter_sources,extra_sources=bundle['extra_sources'],commands=commands,accepted=ACCEPTED,
        counts=dict(configurations=50,main_roundtrips=150,actual_attempts=152,loaded_attempts=1,retaken_units=1))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--check',action='store_true');mode.add_argument('--write-proof',action='store_true')
    args=parser.parse_args();root=args.root.resolve();value=replay(root);raw=packed(value)
    proof=under(root,PREFIX+'rebuild-audit.json')
    if args.write_proof:proof.write_bytes(raw)
    else:require(proof.is_file() and proof.read_bytes()==raw,'rebuild-audit.json missing/different; generate the deterministic proof with --write-proof')
    print(json.dumps(dict(status='PASS',source_commit=SOURCE,files=FILE_COUNT,accepted=ACCEPTED),sort_keys=True))


if __name__=='__main__':main()
