"""Untimed adapter fixture checks; optional casefix-DSO integration is explicit."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('twobit_sequence_adapter',ROOT/'codecs/twobit.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)


class SequenceAdapter(unittest.TestCase):
    def test_streaming_digest_spans_multiple_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'source';raw=b'ACGTn'*(1<<19);path.write_bytes(raw)
            self.assertEqual(adapter.sha(path),hashlib.sha256(raw).hexdigest())

    def test_seq_build_keeps_case_and_rejects_nonsequence_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);source=folder/'source.fa';source.write_bytes(b'>fixture\r\nTCAGtcag\r\nNNnnACTG\r\n')
            result=adapter.seq_build(source,folder/'built')
            sequence=b'TCAGtcagNNnnACTG'
            self.assertEqual(result['sequence']['sha256'],hashlib.sha256(sequence).hexdigest())
            self.assertEqual(result['tables']['n_blocks'],[[8,4]])
            self.assertEqual(result['tables']['mask_blocks'],[[4,4],[10,2]])
            self.assertEqual(result['configuration']['input_domain'],'fasta-sequence')
            self.assertFalse(result['configuration']['generic_byte_qualification'])
            source.write_bytes(b'>bad\nACGTX\n')
            with self.assertRaisesRegex(ValueError,'unsupported base'):
                adapter.seq_build(source,folder/'bad')
            self.assertFalse((folder/'bad/sequence.2bit').exists())

    @unittest.skipUnless(os.environ.get('HB_TWOBIT_NATIVE_BUILD'),'set HB_TWOBIT_NATIVE_BUILD to the pinned casefix build receipt')
    def test_seq_fetch_casefix_preserves_lowercase_n(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);sequence=b'TCAGtcagNNnnACTG'*2049
            source=folder/'source.fa';source.write_bytes(b'>fixture\n'+sequence+b'\n')
            adapter.seq_build(source,folder/'built')
            for start in (0,1,8192):
                output=folder/('fetch-'+str(start));result=adapter.seq_fetch(folder/'built/sequence.2bit','fixture',start,16384,output,os.environ['HB_TWOBIT_NATIVE_BUILD'])
                self.assertEqual(output.read_bytes(),sequence[start:start+16384]);self.assertFalse(result['timings_collected'])


if __name__=='__main__':unittest.main()
