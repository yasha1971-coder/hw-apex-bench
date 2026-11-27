"""Pure adversarial parser/ELF/exact-math checks; never execute a codec."""
import importlib.util
from pathlib import Path
import struct
import unittest
from fractions import Fraction


def module(name):
    path=Path(__file__).with_name(name+'.py')
    spec=importlib.util.spec_from_file_location('_pure_tb_'+name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


A=module('audit')


def executable(types=(1,), needed=False):
    size=64+56*len(types)+(16 if 2 in types else 0)
    raw=bytearray(size)
    struct.pack_into('<16sHHIQQQIHHHHHH',raw,0,b'\x7fELF\x02\x01\x01'+b'\0'*9,2,62,1,0,64,0,0,64,56,len(types),0,0,0)
    for i,kind in enumerate(types):
        offset=64+56*len(types) if kind==2 else 0
        length=16 if kind==2 else size
        struct.pack_into('<IIQQQQQQ',raw,64+56*i,kind,5,offset,0,0,length,length,4096)
        if kind==2:struct.pack_into('<qQ',raw,offset,1 if needed else 0,0)
    return bytes(raw)


class PureAudit(unittest.TestCase):
    def test_native_seconds_and_column_order(self):
        config=next(c for c in A.grid() if c['id']=='aceapex_fast,1')
        row=dict.fromkeys(A.HEADER,'0')
        row.update(dataset='silesia.ref.tar',size=str(A.N),csize='130490328',ctime='1.000001',dtime='2.000003',
                   codec='aceapex_fast',level='1',param='?',err='')
        raw=('\t'.join(A.HEADER)+'\n'+'\t'.join(row[k] for k in A.HEADER)+'\n').encode()
        value=A.native(raw,config)
        self.assertEqual(value['ctime_seconds'],'1.000001')
        self.assertEqual(value['dtime_seconds'],'2.000003')
        self.assertRaises(ValueError,A.native,raw.replace(b'2.000003',b'2.00'),config)
        self.assertRaises(ValueError,A.native,raw+raw.splitlines()[1]+b'\n',config)
        self.assertRaises(ValueError,A.native,raw.replace(b'130490328',b'0'),config)

    def test_elf_static_proof_is_not_a_manifest_flag(self):
        self.assertFalse(A.elf(executable())['PT_INTERP'])
        self.assertFalse(A.elf(executable((1,2)))['DT_NEEDED'])
        self.assertRaises(ValueError,A.elf,executable((1,3)))
        self.assertRaises(ValueError,A.elf,executable((1,2),True))
        self.assertRaises(ValueError,A.elf,executable()[:-1])

    def test_strict_front_and_density_neighbour_tie(self):
        def row(codec,level,size,c,d):
            return dict(id=codec+','+str(level),codec=codec,level=str(level),api_level=int(level)+10 if codec=='aceapex_fast' else None,
                        input_bytes=A.N,compressed_bytes=size,C_MB_s=str(c),D_MB_s=str(d))
        rows=[row('aceapex',1,100,2,10),row('zstd',1,100,3,20),row('misa77',0,110,3,30),
              row('aceapex_fast',1,120,3,40),row('brotli',4,90,4,11)]
        result=A.mathematics(rows)
        self.assertEqual(result['global_D_dominators']['aceapex,1'],['brotli,4'])
        self.assertEqual(result['global_D_dominators']['zstd,1'],[])
        self.assertEqual(result['nearest_ACE_to_misa77'][0]['ACE'],'aceapex_fast,1')
        self.assertEqual(result['nearest_ACE_to_misa77'][0]['signed_byte_gap'],10)
        self.assertEqual(result['forecasts']['P1']['verdict'],'NOT TESTED')

    def test_exact_density_endpoints_and_pending_literal_grid(self):
        rows=[dict(id='a',codec='zstd',level='1',api_level=None,input_bytes=A.N,compressed_bytes=A.N,C_MB_s='1',D_MB_s='1'),
              dict(id='b',codec='zstd',level='3',api_level=None,input_bytes=A.N,compressed_bytes=A.N+1,C_MB_s='1',D_MB_s='1')]
        result=A.mathematics(rows)
        self.assertEqual(result['density_bands'][19]['configurations'],['a'])
        self.assertEqual(result['density_bands'][20]['configurations'],['b'])
        self.assertEqual(len(A.mathematics([],False)['missing_configurations']),60)

    def test_independent_full_math_matches_published_projection_contract(self):
        analyzer=module('analysis');configs=A.grid();selected={};official=[]
        for index,config in enumerate(configs):
            rounds=[dict(round=r,compressed_bytes=50000000+index*271+r,
                ctime_seconds=f'{1+index%3}.{r:06d}',dtime_seconds=f'{1+index%5}.{4-r:06d}',roundtrip=True) for r in (1,2,3)]
            selected[config['id']]=rounds
            official.append(analyzer.summarize_rounds(config,rounds))
        expected=analyzer.math_projection(analyzer.analyze(official,configs,True))
        own=A.mathematics(A.median_rows(selected,configs))
        self.assertEqual(own,expected)
        self.assertEqual(Fraction(own['rows'][0]['C_MB_s']),Fraction(A.N,1000000)/Fraction('1.000002'))


if __name__=='__main__':unittest.main()
