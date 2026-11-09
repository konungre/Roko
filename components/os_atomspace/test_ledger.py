"""Real SQLite CAS/restart checks using explicitly synthetic Nix-shaped receipts."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.os_atomspace.ledger import Ledger,LedgerError
from components.os_atomspace.contract import digest


def fixture(revision=1,predecessor='0'*64,generation='generation-one'):
    receipt=json.dumps([{'drvPath':'/workspace/test/example.drv','outputs':{'out':'/workspace/test/'+generation},
                         'startTime':10,'stopTime':11}]).encode()
    fact={'schema':'roko-os-fact-v1','machine':'fixture','backend':'nix','revision':revision,'stage':'built',
          'generation':generation,'evidence_sha256':hashlib.sha256(receipt).hexdigest(),'predecessor':predecessor}
    return json.dumps(fact).encode(),receipt


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'ledger.sqlite'
        self.ledger=Ledger(self.path)
    def tearDown(self):self.ledger.close();self.temp.cleanup()

    def test_restart_replays_exact_fact_and_preserves_built_only(self):
        fact,receipt=fixture();saved=self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        before=self.ledger.snapshot('fixture','nix');self.ledger.close();self.ledger=Ledger(self.path)
        replay=self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        self.assertEqual(replay['status'],'replayed');self.assertEqual(replay['fact_sha256'],saved['fact_sha256'])
        self.assertEqual(self.ledger.snapshot('fixture','nix'),before)
        self.assertEqual([r['phase'] for r in before['packet']['facts']],['built'])

    def test_second_writer_cannot_commit_from_stale_revision(self):
        other=Ledger(self.path)
        try:
            fact,receipt=fixture();self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
            next_fact,next_receipt=fixture(2,digest(json.loads(fact)),generation='generation-two')
            with self.assertRaises(LedgerError):other.ingest_built(next_fact,next_receipt,'a'*40,expected_revision=0)
            self.assertEqual(other.snapshot('fixture','nix')['revision'],1)
            other.ingest_built(next_fact,next_receipt,'a'*40,expected_revision=1)
            self.assertEqual(self.ledger.snapshot('fixture','nix')['revision'],2)
        finally:other.close()

    def test_wrong_predecessor_cannot_advance(self):
        fact,receipt=fixture();self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        fact,receipt=fixture(2,'f'*64,generation='generation-two')
        with self.assertRaises(LedgerError):self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=1)
        self.assertEqual(self.ledger.snapshot('fixture','nix')['revision'],1)

    def test_revision_cannot_be_rebound_to_other_generation(self):
        fact,receipt=fixture();self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        fact,receipt=fixture(generation='changed')
        with self.assertRaises(LedgerError):self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)

    def test_changed_stored_receipt_is_rejected_before_query_publication(self):
        fact,receipt=fixture();self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        self.ledger.db.execute("UPDATE facts SET receipt_hex='00'")
        with self.assertRaises((ValueError,UnicodeError)):
            self.ledger.snapshot('fixture','nix')

    def test_two_concurrent_connections_have_one_revision_winner(self):
        barrier=threading.Barrier(2);results=[]
        def writer(generation):
            ledger=Ledger(self.path)
            try:
                fact,receipt=fixture(generation=generation);barrier.wait(timeout=5)
                try:
                    ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
                    results.append('committed')
                except LedgerError:results.append('rejected')
            finally:ledger.close()
        threads=[threading.Thread(target=writer,args=(name,)) for name in ('generation-a','generation-b')]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=12)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sorted(results),['committed','rejected'])
        self.assertEqual(self.ledger.snapshot('fixture','nix')['revision'],1)

    def test_actual_commit_survives_abrupt_process_exit(self):
        fact,receipt=fixture()
        program='''import json,os,sys
sys.path.insert(0,sys.argv[2])
from components.os_atomspace.ledger import Ledger
data=json.load(sys.stdin)
ledger=Ledger(sys.argv[1])
ledger.ingest_built(bytes.fromhex(data['fact']),bytes.fromhex(data['receipt']),'a'*40,expected_revision=0)
os._exit(0)
'''
        result=subprocess.run([sys.executable,'-B','-c',program,str(self.path),str(Path(__file__).resolve().parents[2])],
            input=json.dumps({'fact':fact.hex(),'receipt':receipt.hex()}).encode(),capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.ledger.snapshot('fixture','nix')['revision'],1)

    def test_changed_metadata_cannot_replay_success(self):
        fact,receipt=fixture();self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)
        self.ledger.db.execute("UPDATE facts SET generation='changed'")
        with self.assertRaises(LedgerError):self.ledger.ingest_built(fact,receipt,'a'*40,expected_revision=0)


if __name__=='__main__':unittest.main()
