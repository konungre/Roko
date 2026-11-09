"""Closed conversation request and fault receipts, with explicit process doubles."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.os_atomspace.conversation_contract import validate
from components.os_atomspace import conversation_gateway as gateway
from components.os_atomspace.qualify import fixture


class ConversationGatewayTests(unittest.TestCase):
    def test_runtime_selector_cannot_point_outside_qualified_source_pins(self):
        profile={'schema':'roko.os-atomspace.conversation-profile.v1',
            'runtime':{'python':'/runtime/python','swipl':'/runtime/swipl','petta':'/unqualified/petta',
                       'omega':'/runtime/omega','runtime_env':{}},
            'facts_path':'/source/facts.json','receipts_path':'/source/receipts.json','source_commit':'a'*40,
            'files':{path:'f'*64 for path in ('/runtime/python','/runtime/swipl','/runtime/old-petta/src/metta.pl')}}
        with patch.object(gateway,'sha',return_value='f'*64),patch.object(gateway,'source_packet') as source:
            with self.assertRaisesRegex(ValueError,'runtime entrypoint'):gateway.verify_profile(profile)
            source.assert_not_called()

    def test_no_request_can_supply_a_path_or_mutation(self):
        self.assertEqual(validate({'version':1,'operation':'query_imported_profile'}),
                         {'version':1,'operation':'query_imported_profile'})
        for row in ({'version':1,'operation':'activate'},
                    {'version':True,'operation':'query_imported_profile'},
                    {'version':1,'operation':'query_imported_profile','path':'/anywhere'}):
            with self.assertRaises(ValueError):validate(row)

    def test_primary_cancellation_survives_cleanup_and_retains_disk_receipt(self):
        primary=KeyboardInterrupt('synthetic cancellation');primary.output=b'partial\xff'
        proc=SimpleNamespace(returncode=None,poll=Mock(return_value=None),
            terminate=Mock(side_effect=OSError('terminate fault')),kill=Mock(),wait=Mock(),
            stdin=Mock(),stdout=Mock(),stderr=Mock(),
            communicate=Mock(side_effect=[primary,(b'partial\xff',b'error'),(b'partial\xff final',b'error')]))
        profile={'runtime':{'python':sys.executable,'swipl':'/synthetic/swipl','petta':'/synthetic/petta','omega':'/synthetic/omega'}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(gateway,'verify_profile',return_value=fixture(0,['observed'])), \
             patch.object(gateway.subprocess,'Popen',return_value=proc),self.assertRaises(KeyboardInterrupt) as caught:
            directory=Path(tmp)/'native'
            try:
                gateway.run({'version':1,'operation':'query_imported_profile'},profile,directory)
            finally:
                self.assertEqual(json.loads((directory/'receipt.json').read_bytes()),primary.receipt)
        self.assertIs(caught.exception,primary)
        self.assertEqual(primary.receipt['status'],'failed')
        self.assertEqual(bytes.fromhex(primary.receipt['stdout_hex']),b'partial\xff final')
        self.assertIn('terminate',[r['stage'] for r in primary.receipt['finalization_errors']])
        proc.kill.assert_called_once();proc.wait.assert_called_once()
