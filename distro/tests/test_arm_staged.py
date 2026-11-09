from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'update'))
import test_signed_release as signatures
import stage_release
from boot_trial import Journal
from arm_staged import arm


class ArmTests(unittest.TestCase):
    sign=signatures.SignatureTests.sign
    def setUp(self):
        signatures.SignatureTests.setUp(self)
        self.root.chmod(0o700)
        self.staged=self.root/'staged'
        stage_release.stage(self.bundle,self.metadata,self.signature,self.key,5,self.staged)
        self.directory=self.root/'journal';self.directory.mkdir(mode=0o700)
        journal=Journal(self.directory)
        try:journal.initialize({'slot':'A','sequence':4,'sha256':'a'*64})
        finally:journal.close()

    def test_actual_signed_candidate_arms_inactive_slot_only(self):
        result=arm(self.directory,self.staged,self.key,0)
        self.assertTrue(result['signature_verified'])
        self.assertEqual(result['state']['trial']['slot'],'B')
        self.assertEqual(result['state']['trial']['sha256'],self.value['sha256'])
        self.assertEqual(result['state']['good']['sequence'],4)
        self.assertFalse(result['slot_written'])
        self.assertFalse(result['boot_executed'])

    def test_corruption_cannot_arm(self):
        (self.staged/'bundle.tar').write_bytes(b'X'*self.value['bytes'])
        with self.assertRaises(ValueError):arm(self.directory,self.staged,self.key,0)
        journal=Journal(self.directory)
        try:self.assertEqual(journal.read()['revision'],0)
        finally:journal.close()

    def test_replay_and_pending_trial_refused(self):
        arm(self.directory,self.staged,self.key,0)
        with self.assertRaises(ValueError):arm(self.directory,self.staged,self.key,0)
        with self.assertRaises(ValueError):arm(self.directory,self.staged,self.key,1)
