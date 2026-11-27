# SPDX-License-Identifier: Apache-2.0
"""Build TurboBench in CI; list codecs, but never run a benchmark here."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TB = '4aa97c8c37311e399ea3e7782c18c652c5bdb69f'
ACE = 'c53f3a04f3dbac8590e46a1f86c5fded1e69e065'
GO = 'go1.27.4'
FLAGS = '-march=x86-64-v3 -mtune=generic'
PINS = {
    'aceapex': ('https://github.com/yasha1971-coder/aceapex.git', '022af6126de42e63450a45557676ba30bfd6caa9'),
    'brotli': ('https://github.com/google/brotli.git', '717514a67b3f8abf53365d4471a102a60fff8ef5'),
    'kanzi-cpp': ('https://github.com/flanglet/kanzi-cpp.git', '388ca03cf3a13e5456629a6781616c4c96f8fd4a'),
    'libbsc': ('https://github.com/IlyaGrebnov/libbsc.git', '6542faafd0c235975e77e219c77f8227f770fe91'),
    'lz4': ('https://github.com/lz4/lz4.git', '00bf3522fdb94a9d0e69c1d4db7eed77343f7a60'),
    'lzav': ('https://github.com/avaneev/lzav.git', '5a60cfd78e6f6dd8347a905d520b8d03ff5ea2f4'),
    'lzma': ('https://github.com/sisong/lzma.git', '44809544b95bbf2dccec75d954657ff76fc349ff'),
    'minlz': ('https://github.com/minio/minlz.git', 'ede3d8ebed44161c62b50a22491274d182ced777'),
    'misa77': ('https://github.com/welcome-to-the-sunny-side/misa77.git', 'd5293cfa4fd59526d26a8702a42a1139a5d4e0df'),
    'zstd': ('https://github.com/facebook/zstd.git', 'e50cdb0d407f5db512ed377fbee6c9ba473fea8e'),
    'zxc': ('https://github.com/hellobertrand/zxc.git', '69d1fae484b44b7ab612d8a9b1a5a023b9021c1b'),
}
PROFILES = {
    'aceapex_fast': list(range(1, 9)), 'aceapex': [1, 2, 3, 4],
    'misa77': list(range(6)), 'zxc': list(range(1, 8)), 'lz4': [1, 3, 9, 12],
    'lzav': [1, 2], 'minlz': [1, 3, 7], 'zstd': [1, 3, 9, 15, 19, 22],
    'brotli': [4, 6, 9, 11], 'lzma': [9], 'bsc': ['0e0'], 'kanzi': [5, 6, 7, 8],
}
VERSIONS = {'aceapex': '2.6.5', 'misa77': '0.8.1', 'zxc': '1.0.0', 'lz4': '1.11.2',
            'lzav': '7.2', 'minlz_go_module': '1.3.1', 'minlz_registry_literal': '1.3.0',
            'zstd': '1.6.0', 'brotli': '1.2.0', 'lzma': '26.02', 'bsc': '3.4.1', 'kanzi': '1.0.0'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def validate_registry(listing):
    selected = {}
    for line in listing.splitlines():
        parts = line.strip().split(None, 1)
        if parts and parts[0] in PROFILES:
            require(len(parts) == 2 and parts[0] not in selected, 'missing/duplicate codec level specification')
            selected[parts[0]] = parts[1]
    require(set(selected) == set(PROFILES), 'required enabled selector absent from -l1')
    result = {}
    for codec, requested in PROFILES.items():
        spec = selected[codec]
        levels = {int(x) for x in spec.split('/', 1)[0].split(',') if re.fullmatch(r'-?\d+', x)}
        for value in requested:
            match = re.fullmatch(r'(-?\d+)(.*)', str(value))
            require(match is not None and int(match[1]) in levels, 'required level absent: '+codec+','+str(value))
            require(not match[2] or codec == 'bsc' and match[2] == 'e0' and 'e0' in spec,
                    'unsupported codec parameter: '+codec+','+str(value))
        result[codec] = dict(requested=requested, available_levels=sorted(levels), registry_specification=spec)
    return result


class Builder:
    def __init__(self, work, output):
        self.work, self.output = work.resolve(), output.resolve()
        for path in (self.work, self.output):
            require(path.is_relative_to(ROOT) and path != ROOT, 'owned repository subdirectory required')
            require(not path.exists() or not any(path.iterdir()), 'refusing nonempty build/output directory: ' + str(path))
            path.mkdir(parents=True, exist_ok=True)
        (self.output / 'logs').mkdir()
        self.src = self.work / 'TurboBench'
        self.env = dict(os.environ, CC='gcc-14', CXX='g++-14', CG='gcc-14', CCO='gcc-14', CXL='g++-14',
                        CFLAGS=FLAGS, CXXFLAGS=FLAGS, CGO_CFLAGS=FLAGS, CGO_CXXFLAGS=FLAGS,
                        CGO_ENABLED='1', GOAMD64='v3', GOTOOLCHAIN='local')
        self.record = dict(schema='tb-lvl-0-static-build-v1', status='BUILDING',
                           build_only=True, benchmark_calls=0,
                           started_utc=datetime.now(timezone.utc).isoformat(),
                           turbobench_commit=TB, aceapex_override=ACE,
                           declared_versions=VERSIONS, requested_profiles=PROFILES,
                           aceapex_fast_mapping='TurboBench levels 1..8 pass ACEAPEX API levels 11..18',
                           fixed_architecture=FLAGS, environment={k:self.env[k] for k in
                           ('CC','CXX','CG','CCO','CXL','CFLAGS','CXXFLAGS','CGO_CFLAGS','CGO_CXXFLAGS','CGO_ENABLED','GOAMD64','GOTOOLCHAIN')},
                           controller_sha256=digest(__file__),
                           repository_sources={str(p.relative_to(ROOT)):digest(p) for p in
                               [ROOT/'.github/workflows/tb-lvl-0-build.yml',Path(__file__),
                                ROOT/'evidence/tb-lvl-0/CALIBRATION.md']}, commands=[])
        self.save()

    def save(self):
        (self.output / 'build.json').write_bytes(packed(self.record))

    def artifact(self, path):
        path = Path(path)
        return dict(path=str(path.relative_to(self.output)) if path.is_relative_to(self.output) else str(path),
                    bytes=path.stat().st_size, sha256=digest(path))

    def run(self, argv, cwd=None, name=None, allowed=(0,)):
        number = len(self.record['commands']) + 1
        stem = f'{number:03d}-' + (name or Path(argv[0]).name)
        stdout, stderr = self.output / 'logs' / (stem+'.stdout'), self.output / 'logs' / (stem+'.stderr')
        with stdout.open('wb') as out, stderr.open('wb') as err:
            result = subprocess.run([str(x) for x in argv], cwd=cwd or ROOT, env=self.env, stdout=out, stderr=err)
        self.record['commands'].append(dict(argv=[str(x) for x in argv], cwd=str(cwd or ROOT),
            returncode=result.returncode, stdout=self.artifact(stdout), stderr=self.artifact(stderr)))
        self.save()
        require(result.returncode in allowed, f'command failed ({result.returncode}): {stem}; inspect retained logs')
        return stdout.read_text(encoding='utf-8', errors='strict')

    def git(self, *args, cwd=None):
        return self.run(['git', *args], cwd=cwd or self.src)

    def sources(self):
        self.run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/powturbo/TurboBench.git',self.src])
        self.git('checkout','--detach',TB)
        require(self.git('rev-parse','HEAD').strip() == TB, 'TurboBench pin differs')
        original_links = []
        for line in self.git('ls-tree','HEAD').splitlines():
            left, path = line.split('\t', 1)
            mode, kind, commit = left.split()
            if mode == '160000':
                original_links.append(dict(path=path, commit=commit))
        known = {r['path']:r['commit'] for r in original_links}
        require(all(known.get(path) == commit for path, (_,commit) in PINS.items()), 'pinned gitlinks differ')
        self.record['upstream_top_level_gitlinks'] = original_links
        self.git('submodule','update','--init','--recursive','--depth','1','--',*PINS)
        for path, (url, commit) in PINS.items():
            require(self.git('rev-parse','HEAD',cwd=self.src/path).strip() == commit, 'submodule pin differs: '+path)
        self.git('fetch','--depth','1','origin',ACE,cwd=self.src/'aceapex')
        self.git('checkout','--detach',ACE,cwd=self.src/'aceapex')
        require(self.git('rev-parse','HEAD',cwd=self.src/'aceapex').strip() == ACE, 'ACE override differs')
        # An uninitialised empty submodule directory would activate wildcard
        # codec detection. Keep their exact upstream index entries, explicitly
        # mark only unused gitlinks sparse, then remove empty placeholders.
        unused = sorted(set(known) - set(PINS))
        for name in unused:
            path = self.src / name
            require(path.resolve().is_relative_to(self.src.resolve()) and not path.is_symlink()
                    and (not path.exists() or path.is_dir() and not any(path.iterdir())),
                    'unselected gitlink was populated: '+name)
        self.git('update-index','--skip-worktree','--',*unused)
        self.record['unselected_sparse_gitlinks'] = unused
        removed = []
        for item in original_links:
            path = self.src / item['path']
            if item['path'] not in PINS and path.is_dir():
                require(path.resolve().is_relative_to(self.src.resolve()) and not any(path.iterdir()),
                        'unexpected populated unselected submodule: '+item['path'])
                path.rmdir()
                removed.append(item['path'])
        self.record['unselected_empty_placeholders_removed'] = removed
        modules = self.git('submodule','status','--recursive')
        (self.output/'submodules.txt').write_text(modules,encoding='utf-8',newline='\n')
        self.record['submodules'] = self.artifact(self.output/'submodules.txt')
        self.record['selected_sources'] = {path:dict(url=url,upstream_gitlink=pin,commit=ACE if path=='aceapex' else pin)
                                           for path,(url,pin) in PINS.items()}
        self.check_clean()

    def check_clean(self):
        known = {r['path']:r['commit'] for r in self.record['upstream_top_level_gitlinks']}
        unused = sorted(set(known) - set(PINS))
        require(self.record['unselected_sparse_gitlinks'] == unused, 'sparse selection changed')
        for name in unused:
            path = self.src / name
            require(not path.exists() and not path.is_symlink(), 'unselected gitlink acquired source: '+name)
        # Skip-worktree is never allowed to hide a selected source or an index
        # change. Every unused entry remains mode160000/stage0 at its HEAD pin.
        self.git('diff','--cached','--exit-code','HEAD','--')
        entries = {}
        for line in self.git('ls-files','--stage','--',*known).splitlines():
            metadata,path = line.split('\t',1)
            mode,commit,stage = metadata.split()
            entries[path] = dict(mode=mode,commit=commit,stage=stage)
        require(entries == {name:dict(mode='160000',commit=pin,stage='0') for name,pin in known.items()},
                'gitlink index no longer equals upstream HEAD')
        flags = {line[2:]:line[0] for line in self.git('ls-files','-v').splitlines()}
        require({name for name,flag in flags.items() if flag.upper() == 'S'} == set(unused)
                and all(flag.isupper() for flag in flags.values()), 'unexpected hidden source/index flags')
        selection = self.output/'source-selection.json'
        selection.write_bytes(packed(dict(unselected_absent=unused,index_gitlinks=entries,index_flags=flags)))
        self.record['source_selection'] = self.artifact(selection)
        changed = self.git('diff','--name-only','--ignore-submodules=none').splitlines()
        require(changed == ['aceapex'], 'only explicit ACE gitlink override permitted: '+repr(changed))
        diff = self.git('diff','--submodule=short')
        expected = '-Subproject commit '+PINS['aceapex'][1]+'\n+Subproject commit '+ACE
        require(expected in diff, 'unexpected source patch')
        (self.output/'aceapex-gitlink.patch').write_text(diff,encoding='utf-8',newline='\n')
        self.record['source_git_diff'] = self.artifact(self.output/'aceapex-gitlink.patch')
        for line in self.git('submodule','status','--recursive').splitlines():
            if not line.startswith('-'):
                fields=line[1:].split()
                self.git('diff','--exit-code','HEAD','--',cwd=self.src/fields[1])
        self.save()

    def configure(self):
        cmake = ['cmake','-DCMAKE_C_COMPILER=gcc-14','-DCMAKE_CXX_COMPILER=g++-14',
                 '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_VERBOSE_MAKEFILE=ON','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON']
        configs = {
            'brotli':['-DBUILD_SHARED_LIBS=OFF','-DBROTLI_BUILD_TOOLS=OFF','-DBROTLI_BUNDLED_MODE=ON'],
            'kanzi-cpp':['-DKANZI_ENABLE_NATIVE_OPTIMIZATIONS=OFF'],
            'misa77':['-DMISA77_BUILD_TESTS=OFF','-DMISA77_BUILD_CLI=OFF'],
            'zxc':['-DZXC_NATIVE_ARCH=OFF','-DBUILD_SHARED_LIBS=OFF','-DZXC_BUILD_TESTS=OFF','-DZXC_BUILD_CLI=OFF','-DZXC_INSTALL=OFF'],
        }
        for name, options in configs.items():
            self.run(cmake+['-S',name,'-B','build/'+name]+options,cwd=self.src,name='configure-'+name)
        wrapper = self.src/'turbobench_/minlz'
        before = digest(wrapper/'go.mod')
        require(self.run(['go','env','GOVERSION']).strip() == GO, 'exact Go toolchain required')
        self.run(['go','mod','download','-json'],cwd=wrapper,name='go-download')
        require(digest(wrapper/'go.mod') == before, 'Go dependency resolution changed the pinned manifest')
        mods = self.run(['go','list','-m','-json','all'],cwd=wrapper,name='go-modules')
        require('"Path": "github.com/minio/minlz"' in mods and '"Version": "v1.3.1"' in mods,
                'unexpected minlz module version')
        for name in ('go.mod','go.sum'):
            require((wrapper/name).is_file(), 'Go dependency hash list missing')
            shutil.copyfile(wrapper/name,self.output/name)
        self.run(['go','build','-mod=readonly','-buildmode=c-archive','-o','libmlz.a','.'],cwd=wrapper,name='go-static-archive')
        require(digest(wrapper/'go.mod') == before, 'Go build changed pinned manifest')
        self.record['go'] = dict(version=GO,go_mod=self.artifact(self.output/'go.mod'),go_sum=self.artifact(self.output/'go.sum'),
                                 static_archive_sha256=digest(wrapper/'libmlz.a'),
                                 note='Actual module v1.3.1; upstream TurboBench registry literal says v1.3.0.')

    def build(self):
        make = ['make','-j2','STATIC=1','OPENMP=0','CC=gcc-14','CXX=g++-14','CG=gcc-14','CCO=gcc-14','CXL=g++-14',
                'MARCH='+FLAGS,'--assume-old=turbobench_/minlz/libmlz.a','turbobench']
        self.record['make_argv'] = make
        self.run(make,cwd=self.src,name='make-static')
        self.check_clean()
        binary = self.output/'turbobench'
        shutil.copy2(self.src/'turbobench',binary)
        proof = {}
        for name, args in [('file',['file',binary]),('readelf-header',['readelf','-h',binary]),
                           ('readelf-programs',['readelf','-lW',binary]),('readelf-dynamic',['readelf','-dW',binary])]:
            proof[name] = self.run(args,name=name)
        require('ELF 64-bit' in proof['file'] and 'x86-64' in proof['file'] and 'statically linked' in proof['file'],
                'not a statically linked x86-64 ELF')
        require(not re.search(r'\bINTERP\b',proof['readelf-programs']) and '(NEEDED)' not in proof['readelf-dynamic'],
                'ELF has an interpreter or dynamic library dependency')
        listing = self.run([binary,'-l1'],cwd=self.output,name='codec-selectors-levels')
        self.record['validated_profiles'] = validate_registry(listing)
        self.run([binary,'-l2'],cwd=self.output,name='codec-versions')
        self.record['binary'] = self.artifact(binary)
        self.record['static_elf_verified'] = True
        self.record['codec_registry_command'] = ['turbobench','-l1']
        self.record['codec_versions_command'] = ['turbobench','-l2']
        self.record['codec_registry_only_no_benchmark'] = True
        snapshots = []
        for path in sorted((self.src/'build').rglob('*')):
            if path.is_file() and path.name in ('CMakeCache.txt','compile_commands.json'):
                target = self.output/'configuration'/path.relative_to(self.src/'build')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
                snapshots.append(self.artifact(target))
        self.record['cmake_configuration'] = snapshots
        # Check full retained command lines, including nested CMake invocations.
        for path in (self.output/'logs').glob('*.stdout'):
            require('-march=native' not in path.read_text(encoding='utf-8'), 'host-native ISA flag in build log: '+path.name)
        self.record['status'] = 'PASS'
        self.record['completed_utc'] = datetime.now(timezone.utc).isoformat()
        self.save()
        (self.output/'SHA256SUMS').write_text(digest(binary)+'  turbobench\n'+digest(self.output/'build.json')+'  build.json\n',encoding='ascii')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,default=ROOT/'.work/tb-lvl-0-ci')
    parser.add_argument('--output',type=Path,default=ROOT/'out/tb-lvl-0-static')
    args=parser.parse_args()
    builder=None
    try:
        builder=Builder(args.work,args.output)
        for command in (['gcc-14','--version'],['g++-14','--version'],['make','--version'],['cmake','--version'],['go','version'],['git','--version']):
            builder.run(command)
        builder.record['tool_binaries']={name:builder.artifact(Path(shutil.which(name)).resolve()) for name in
                                        ('gcc-14','g++-14','make','cmake','go','git','ar','readelf','file')}
        builder.record['repository_commit']=builder.run(['git','rev-parse','HEAD']).strip()
        builder.sources();builder.configure();builder.build()
        print(json.dumps(dict(status='PASS',binary=builder.record['binary'],provenance=str(builder.output/'build.json'),benchmark_calls=0),sort_keys=True))
        return 0
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        if builder is not None:
            builder.record.update(status='FAIL',reason=str(error));builder.save()
        print(json.dumps(dict(status='FAIL',reason=str(error))),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
