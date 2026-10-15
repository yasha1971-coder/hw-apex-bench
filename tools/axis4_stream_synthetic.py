#!/usr/bin/env python3
"""Offline A11 gzip-only truth acceptance. Unit fixture by default; native optional."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from unittest import mock

from review.axis3.verdict_data import checked_file, file_ref, load_json, write_json
from tools import axis4, axis4_evidence_verify, axis4_stream


class UnitReader:
    scope = 'cpu-in-process'
    decoder_threads = 1
    build = {'kind': 'synthetic-unit-fixture', 'not_native': True}
    def __init__(self, sequences):
        self.sequences = sequences
    def fetch(self, assembly, contig, start, end):
        return self.sequences[assembly][contig][start:end]
    def translated(self, w):
        return {'assembly_id': w.assembly, 'contig_id': w.contig, 'start0': w.start0,
                'end0': w.end0, 'convention': '0-based-half-open'}
    def close(self):
        pass


def run_case(out, *, native_root=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        if native_root is not None:
            source = Path(native_root).resolve(strict=True)
            manifest = load_json(source/'cohort.json')
            if (manifest.get('evidence_kind') != 'synthetic' or
                    sum(a['fasta']['bytes'] for a in manifest['assemblies']) > 8*1024*1024):
                raise ValueError('bounded retained synthetic sources required')
            reader = load_json(source/'plan.json')['reader']
            if reader['family'] != 'zstd-seekable':
                raise ValueError('native acceptance needs retained zstd-seekable fixture')
            for ref in axis4.unique_refs(axis4.collect_refs(reader)):
                p = checked_file(source, ref)
                target = out/ref['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
            shutil.copyfile(source/'groups.json', out/'groups.json')
            raw = {a['assembly_id']: checked_file(source, a['fasta']).read_bytes()
                   for a in manifest['assemblies']}
            reader_context = None
        else:
            seq = (b'acgTNryS'*10000)
            raw = {'a': b'>c description\r\n'+seq+b'\r\n>tail\nACGTN'}
            manifest = {'schema':'axis4-corpus-v1.1','evidence_kind':'synthetic',
                        'assemblies':[{'assembly_id':'a','source_url':'synthetic:A11-unit'}]}
            groups = [{'a':{'assembly_id':'a','contig_id':'c','start0':i*100,'end0':i*100+37}}
                      for i in range(40)]
            write_json(out/'groups.json', groups)
            (out/'unit.so').write_bytes(b'Synthetic unit only, never dlopen')
            write_json(out/'unit-build.json', UnitReader.build)
            reader = {'family':'unit-fixture','variant':'not-native',
                      'library':file_ref(out,out/'unit.so'),
                      'build_receipt':file_ref(out,out/'unit-build.json'), 'archives': []}
            reader_context = lambda: mock.patch.object(axis4,'open_reader',return_value=UnitReader({'a':{'c':seq,'tail':b'ACGTN'}}))
        manifest['schema'] = 'axis4-corpus-v1.1'
        manifest['evidence_kind'] = 'synthetic'
        for a in manifest['assemblies']:
            p = out/(a['assembly_id']+'.fa.gz')
            p.write_bytes(gzip.compress(raw[a['assembly_id']], mtime=0))
            a['fasta'] = file_ref(out,p)
        write_json(out/'cohort.json', manifest)
        prepared = axis4.prepare(out,'cohort.json','groups.json','prepared')
        frozen = load_json(out/prepared['path'])
        if reader_context is not None:
            reader['archives'] = [{'assembly_id':a['assembly_id'],'archive':a['fasta']}
                                  for a in frozen['assemblies']]
        write_json(out/'plan.json', {'schema':'axis4-plan-v1','prepared':prepared,'reader':reader})
        if reader_context is not None:
            with reader_context():
                result = axis4.run(out,'plan.json','run')
        else:
            result = axis4.run(out,'plan.json','run')
        if result['status'] != 'PASS':
            raise ValueError(result['error'])
        verified = axis4_evidence_verify.verify(out/'run/evidence.json',out,prepared['sha256'])
        if list(out.rglob('*.fa')) or list(out.rglob('*.fasta')):
            raise ValueError('unexpected on-disk uncompressed FASTA')
        # Check every query against separately retained small source bytes.
        import io
        sequences = {}
        for aid, blob in raw.items():
            current = None
            sequences[aid] = {}
            for line in io.BytesIO(blob):
                if line.startswith(b'>'):
                    current = line[1:].split()[0].decode()
                    sequences[aid][current] = bytearray()
                else:
                    sequences[aid][current].extend(line.rstrip(b'\r\n').upper())
        for row in result['rows']:
            q=row['canonical']
            expected=sequences[q['assembly_id']][q['contig_id']][q['start0']:q['end0']]
            if hashlib.sha256(expected).hexdigest()!=row['observed_sha256']:
                raise ValueError('synthetic source response SHA mismatch')
        write_json(out/'leaderboard-input.json',{'schema':'leaderboard-input-v1','records':[
            {'evidence':file_ref(out,out/'run/evidence.json'),'input_root':'.',
             'prepared_sha256':prepared['sha256']} ]})
        receipt = {**verified, 'native_execution': native_root is not None,
            'reader':reader['family'], 'truth_schema':result['schema'],
            'uncompressed_FASTA_files':0, 'all_response_hashes':'MATCH_SOURCE',
            'sources':result['truth_sources'], 'performance_valid':False}
        write_json(out/'acceptance.json',receipt)
        return receipt
    except Exception:
        shutil.rmtree(out)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--native-root',type=Path)
    args=parser.parse_args()
    print(json.dumps(run_case(args.out,native_root=args.native_root),sort_keys=True))


if __name__=='__main__':
    main()
