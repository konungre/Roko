"""Content-binding checks with synthetic Nix receipt bytes; native import is separate."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.os_atomspace.os_fact_v1 import import_built_fact


class OSFactV1Tests(unittest.TestCase):
    def source(self):
        raw=json.dumps([{'drvPath':'/workspace/test/example.drv','outputs':{'out':'/workspace/test/generation-one'},
                         'startTime':10,'stopTime':11}]).encode()
        fact={'schema':'roko-os-fact-v1','machine':'fixture','backend':'nix','revision':1,'stage':'built',
              'generation':'generation-one','evidence_sha256':hashlib.sha256(raw).hexdigest(),'predecessor':'0'*64}
        return fact,raw

    def test_preserves_source_fact_and_only_built_phase(self):
        fact,raw=self.source();packet=import_built_fact(json.dumps(fact).encode(),raw,'a'*40)
        self.assertEqual([r['phase'] for r in packet['facts']],['built'])
        value=packet['facts'][0]['value'];self.assertEqual(value['source_fact'],fact)
        self.assertTrue(value['receipt_binding_verified'])
        self.assertFalse(value['native_execution_requalified_here']);self.assertFalse(value['producer_authenticated'])

    def test_changed_receipt_bytes_rejected(self):
        fact,raw=self.source()
        with self.assertRaises(ValueError):import_built_fact(json.dumps(fact).encode(),raw+b'\n','a'*40)

    def test_changed_generation_rejected_even_with_valid_receipt_hash(self):
        fact,raw=self.source();fact['generation']='another-generation'
        with self.assertRaises(ValueError):import_built_fact(json.dumps(fact).encode(),raw,'a'*40)

    def test_built_receipt_cannot_establish_activation_or_running(self):
        for stage in ('activated','running','health'):
            fact,raw=self.source();fact['stage']=stage
            with self.assertRaises(ValueError):import_built_fact(json.dumps(fact).encode(),raw,'a'*40)

    def test_duplicate_fact_keys_rejected(self):
        fact,raw=self.source();encoded=json.dumps(fact).encode()
        encoded=encoded[:-1]+b',"revision":2}'
        with self.assertRaises(ValueError):import_built_fact(encoded,raw,'a'*40)


if __name__=='__main__':unittest.main()
