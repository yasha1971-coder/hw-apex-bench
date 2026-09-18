#!/usr/bin/env python3
"""Build unchanged pinned native readers and separate counters; no encodes."""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ACE='4915321bf118e564ef3883e58927992c7f9d8dc3'

def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();o=a.out.resolve();o.mkdir(exist_ok=False)
 pins={'aceapex-source':ACE,'zstd':'f8745da6ff1ad1e7bab384bd1f9d742439278e99','htslib':'8f7231035d0409d525767c66d9f49f1f967ee1df','libdeflate':'dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f'}
 commands=[]
 def run(*cmd):
  cmd=list(map(str,cmd));commands.append(cmd);subprocess.run(cmd,check=True)
 for name,sha in pins.items():
  assert subprocess.check_output(['git','-C',str(b/name),'rev-parse','HEAD'],text=True).strip()==sha
  assert not subprocess.check_output(['git','-C',str(b/name),'status','--porcelain','--untracked-files=no'])
 stage=o/'wrappers';(stage/'codecs/native').mkdir(parents=True);(stage/'harness').mkdir()
 shutil.copy2(ROOT/'harness/resident_context.h',stage/'harness/resident_context.h')
 for codec in ['aceapex','bgzip','zstd_seekable']:
  text=(ROOT/f'codecs/native/{codec}.c').read_text()
  if codec=='aceapex':
   old='1b13df34ac8e839dd3232b59bc59560d689a435a';assert text.count(old)==1;text=text.replace(old,ACE)
  (stage/f'codecs/native/{codec}.c').write_text(text)
 # Same libdeflate source, PIC needed for a resident shared object.
 run('cmake','-S',b/'libdeflate','-B',o/'libdeflate-build','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POSITION_INDEPENDENT_CODE=ON','-DLIBDEFLATE_BUILD_SHARED_LIB=OFF','-DLIBDEFLATE_BUILD_GZIP=OFF','-DLIBDEFLATE_BUILD_TESTS=OFF')
 run('cmake','--build',o/'libdeflate-build','--parallel','2')
 z=b/'zstd';inc=['-I'+str(stage/'harness')]
 for codec in ['aceapex','bgzip','zstd_seekable']:
  w=o/codec;(w/'deps').mkdir(parents=True)
  for src,name in [('aceapex-source','aceapex'),('zstd','zstd'),('htslib','htslib'),('libdeflate','libdeflate')]: (w/'deps'/name).symlink_to(b/src,target_is_directory=True)
  (w/'libdeflate-build').symlink_to(o/'libdeflate-build',target_is_directory=True)
  wrapper=stage/f'codecs/native/{codec}.c';target=w/'context.so'
  if codec=='aceapex':
   run('gcc','-O3','-fPIC',*inc,'-I'+str(b/'aceapex-source/src'),'-c',wrapper,'-o',w/'wrapper.o')
   run('g++','-O3','-std=c++17','-fPIC','-shared','-pthread','-I'+str(b/'aceapex-source/src'),'-I'+str(z/'lib'),w/'wrapper.o',b/'aceapex-source/src/aceapex_api.cpp',z/'lib/libzstd.a','-o',target)
  elif codec=='bgzip':
   run('gcc','-O3','-fPIC','-shared',*inc,'-I'+str(b/'htslib'),wrapper,b/'htslib/libhts.a',o/'libdeflate-build/libdeflate.a','-lz','-lm','-pthread','-o',target)
  else:
   run('gcc','-O3','-fPIC','-shared',*inc,'-DXXH_NAMESPACE=ZSTD_','-I'+str(z/'lib'),'-I'+str(z/'lib/common'),'-I'+str(z/'contrib/seekable_format'),wrapper,z/'contrib/seekable_format/zstdseek_decompress.c',z/'lib/libzstd.a','-pthread','-o',target)
  spec=importlib.util.spec_from_file_location('hwb_counters',ROOT/'codecs/counters.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=stage;m.build(codec,w)
 run('gcc','-O3','-std=c11','-I'+str(ROOT/'harness'),ROOT/'harness/native_measure.c','-ldl','-o',o/'native_measure')
 for name,sha in pins.items(): assert not subprocess.check_output(['git','-C',str(b/name),'status','--porcelain','--untracked-files=no'])
 files=[p for p in o.rglob('*') if p.is_file() and not p.is_symlink() and (p.suffix in {'.so','.c','.json'} or p.name=='native_measure')]
 (o/'build-receipt.json').write_text(json.dumps({'pins':pins,'commands':commands,'files':{str(p.relative_to(o)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2)+'\n')
 print('PASS: native and separate counter libraries built; pinned sources clean')
if __name__=='__main__':main()
