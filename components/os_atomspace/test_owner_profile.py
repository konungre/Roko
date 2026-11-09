"""Canonical OS-owner wrapper-chain adapter, using synthetic receipt documents."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.os_atomspace.owner_profile import owner_digest,import_profile_history


def fixture():
    receipts=[{'operation':'build-and-profile-switch','build':[],
               'switch':{'receipt':{'scope':'private-user-profile'}},'payload':'synthetic'},
              {'operation':'rollback','receipt':{'scope':'private-user-profile-rollback'}}]
    facts=[];previous='0'*64
    for i,receipt in enumerate(receipts,1):
        fact={'schema':'roko-os-fact-v1','machine':'fixture','backend':'nix','revision':i,'stage':'observed',
              'generation':'operation-'+str(i),'evidence_sha256':owner_digest(receipt),'predecessor':previous}
        facts.append(fact);previous=owner_digest({'fact':fact,'mode':'observed'})
    return facts,receipts


class OwnerProfileTests(unittest.TestCase):
    def read(self,facts,receipts):
        return import_profile_history(json.dumps(facts).encode(),json.dumps(receipts).encode(),'a'*40)

    def test_latest_observation_replaces_old_and_remains_unverified(self):
        facts,receipts=fixture();packet=self.read(facts,receipts)
        self.assertEqual(len(packet['facts']),1);row=packet['facts'][0]
        self.assertEqual(row['phase'],'observed');self.assertEqual(row['generation'],'operation-2')
        self.assertEqual(row['value']['source_ledger_head_sha256'],owner_digest({'fact':facts[-1],'mode':'observed'}))
        self.assertFalse(row['value']['system_activation_observed'])

    def test_changed_receipt_cannot_match_history(self):
        facts,receipts=fixture();receipts[0]['payload']='changed'
        with self.assertRaises(ValueError):self.read(facts,receipts)

    def test_predecessor_is_wrapper_digest_not_raw_fact_digest(self):
        facts,receipts=fixture();facts[1]['predecessor']=owner_digest(facts[0])
        with self.assertRaises(ValueError):self.read(facts,receipts)

    def test_private_profile_cannot_be_promoted_to_running(self):
        facts,receipts=fixture();facts[-1]['stage']='running'
        with self.assertRaises(ValueError):self.read(facts,receipts)

    def test_incomplete_or_reordered_history_rejected(self):
        facts,receipts=fixture()
        with self.assertRaises(ValueError):self.read(facts[1:],receipts[1:])
        with self.assertRaises(ValueError):self.read(list(reversed(facts)),receipts)


if __name__=='__main__':unittest.main()
