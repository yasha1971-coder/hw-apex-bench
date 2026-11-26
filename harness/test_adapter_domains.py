"""Metadata-only discovery tests: never build, encode or time an adapter."""
from pathlib import Path
import unittest
from unittest.mock import patch
import resident_probe as probe


class AdapterDomains(unittest.TestCase):
    def test_default_discovery_retains_byte_adapters_and_reports_sequence_skip(self):
        byte,sequence=Path('external-byte.sh'),Path('external-sequence.sh')
        configs={byte:{'level':3},sequence:{'input_domain':'fasta-sequence','coordinate_domain':'base'}}
        reasons={axis:'n/a — sequence domain' for axis in probe.AXES}
        with patch.object(probe,'adapter_configuration',side_effect=lambda p,env:configs[p]):
            with patch.object(probe,'capabilities',return_value=reasons) as axes:
                included,skipped=probe.discover_byte_adapters([byte,sequence])
        self.assertEqual(included,[byte]);self.assertEqual(len(skipped),1)
        self.assertIn('fasta-sequence',skipped[0]['reason']);self.assertIn('base',skipped[0]['reason'])
        axes.assert_called_once_with(sequence,None)
        with self.assertRaisesRegex(ValueError,'generic byte'):
            probe.require_byte_domain(configs[sequence])

    def test_nonbyte_domain_cannot_advertise_generic_byte_support(self):
        with patch.object(probe,'adapter_configuration',return_value={'input_domain':'fasta-sequence','coordinate_domain':'base'}):
            with patch.object(probe,'capabilities',return_value={'region':'available'}):
                with self.assertRaisesRegex(ValueError,'advertises a generic axis'):
                    probe.discover_byte_adapters([Path('not-a-codec-name.sh')])

    def test_malformed_domain_is_not_silently_skipped(self):
        for config in (None,{'coordinate_domain':None},{'input_domain':''},{'coordinate_domain':'base'}):
            with patch.object(probe,'adapter_configuration',return_value=config):
                with self.assertRaises(ValueError):probe.discover_byte_adapters([Path('broken.sh')])


if __name__=='__main__':unittest.main()
