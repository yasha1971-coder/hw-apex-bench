import hashlib,importlib.util,json,os,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
n=mod('native_readers',Path('review/axis3/native_readers.py'));w=mod('window',Path('tools/axis3_window_engine.py'));cal=mod('cal',Path('review/axis3/calibration.py'))
class S2Synthetic(unittest.TestCase):
 def fasta(self,td):
  p=Path(td)/'a.fa';p.write_bytes(b'>chr1\nacgt\nACGT\n>chr2\nNNaa\n');return p
 def test_registry_exact(self): self.assertEqual(len(n.VARIANTS),10);self.assertEqual(len(set(n.VARIANTS)),10)
 def test_raw_fasta_canonical(self):
  with tempfile.TemporaryDirectory() as td:
   r=n.RawFastaReader({'asm':self.fasta(td)});self.assertEqual(r.fetch('asm','chr1',0,8),b'ACGTACGT')
 def test_half_open_rejects_empty(self):
  with tempfile.TemporaryDirectory() as td:
   r=n.RawFastaReader({'asm':self.fasta(td)});self.assertRaises(ValueError,r.fetch,'asm','chr1',1,1)
 def test_window_engine_zero_based(self):
  with tempfile.TemporaryDirectory() as td:
   r=n.RawFastaReader({'asm':self.fasta(td)});coords=[(0,'asm','chr1',0,1)];req=w.freeze_windows(coords,r);ticks=iter([0,1000]);s,rows=w.run_windows(r,req,expected_count=1,calibration=True,clock=lambda:next(ticks));self.assertEqual(s['status'],'PASS');self.assertEqual(rows[0]['canonical']['start0'],0)
 def test_map_requires_prefix(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'m.json';p.write_text(json.dumps({'canonical_bytes':4,'contigs':[{'assembly_id':'a','contig_id':'c','prefix':1,'length':4}]}));self.assertRaises(ValueError,n.load_map,p)
 def test_agc_translation(self):
  class I:
   def contig_length(self,a,c):return 10
   def fetch(self,a,c,s,l):return b'A'*l
  r=n.AgcReaderAdapter(I());q=w.Window(0,'a','c',2,5,'0'*64);self.assertEqual(r.translated(q)['end'],4);self.assertEqual(r.fetch('a','c',2,5),b'AAA')
 def test_bgzf_translation(self):
  class I:
   def contig_length(self,c):return 10
   def fetch(self,c,s,l):return b'C'*l
  r=n.BgzfReaderAdapter(I(),'a');q=w.Window(0,'a','c',2,5,'0'*64);self.assertEqual(r.translated(q)['end'],4);self.assertEqual(r.fetch('a','c',2,5),b'CCC')
 def test_dq_and_negative_c0(self):
  with tempfile.TemporaryDirectory() as td:
   r=n.RawFastaReader({'a':self.fasta(td)});ticks=iter([0,1000]);x=cal.run_dq(r,12,clock=lambda:next(ticks));self.assertGreater(x['D_Q_bytes_per_second'],0);self.assertEqual(cal.compute_c0(1,1e6,4096)['status'],'FAIL')
class NativeAvailability(unittest.TestCase):
 def need(self,key,symbols):
  import ctypes
  value=os.environ.get(key)
  if not value:self.skipTest(f'{key} not set: native tool/library unavailable in this environment')
  self.assertTrue(Path(value).exists(),f'{key} points to missing path')
  lib=ctypes.CDLL(str(Path(value).resolve()))
  for symbol in symbols:self.assertTrue(hasattr(lib,symbol),f'{key} missing native symbol {symbol}')
  return lib
 def test_native_refrel3_q4k(self):self.need('HWAPEX_REFREL3_SO',['hwa_rr3_open','hwa_rr3_fetch','hwa_rr3_close'])
 def test_native_refrel3_q16k(self):self.need('HWAPEX_REFREL3_SO',['hwa_rr3_open','hwa_rr3_fetch','hwa_rr3_close'])
 def test_native_bgzf_default(self):self.need('HWAPEX_BGZF_SO',['hwa_bgzf_open','hwa_bgzf_fetch','hwa_bgzf_close'])
 def test_native_bgzf_matched(self):self.need('HWAPEX_BGZF_SO',['hwa_bgzf_open','hwa_bgzf_fetch','hwa_bgzf_close'])
 def test_native_zstd_seekable(self):self.need('HWAPEX_ZSTD_SEEKABLE_SO',['hc_abi','hc_open','hc_region','hc_decode','hc_close'])
 def test_native_lz4_indexed(self):self.need('HWAPEX_LZ4_SO',['hwa_lz4_block','hwa_lz4_version'])
 def test_native_ozseg_openzl(self):self.need('HWAPEX_OPENZL_SO',['hwa_openzl_decode'])
 def test_native_agc_t2t(self):self.need('HWAPEX_AGC_SO',['hwa_agc_open','hwa_agc_fetch','hwa_agc_close'])
 def test_native_agc_noref(self):self.need('HWAPEX_AGC_SO',['hwa_agc_open','hwa_agc_fetch','hwa_agc_close'])
 def test_native_fasta_faidx(self):self.need('HWAPEX_HTSLIB_SO',['hwa_bgzf_open','hwa_bgzf_fetch','hwa_bgzf_close'])
if __name__=='__main__':unittest.main()
