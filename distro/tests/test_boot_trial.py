import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'update'))
from boot_trial import Journal

GOOD={'slot':'A','sequence':10,'sha256':'a'*64}
NEW={'slot':'B','sequence':11,'sha256':'b'*64}

class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.journal=Journal(self.root);self.addCleanup(lambda:self.journal.close())
        self.journal.initialize(GOOD.copy())

    def apply(self, action, **kwargs):
        return self.journal.transition(action,self.journal.read()['revision'],**kwargs)

    def test_attempt_budget_rolls_back_to_good(self):
        self.apply('arm',candidate=NEW.copy())
        for left in (2,1,0):
            result=self.apply('select')
            self.assertEqual(result['selected'],NEW)
            self.assertEqual(result['state']['good'],GOOD)
            self.assertEqual(result['state']['attempts_left'],left)
            self.assertFalse(result['boot_executed'])
        self.assertEqual(self.apply('select')['selected'],GOOD)
        self.assertIsNone(self.journal.read()['trial'])

    def test_confirmation_requires_current_nonce(self):
        self.apply('arm',candidate=NEW.copy())
        with self.assertRaises(ValueError):self.apply('confirm',nonce='0'*32)
        first=self.apply('select')['state']['active_nonce']
        second=self.apply('select')['state']['active_nonce']
        self.assertNotEqual(first,second)
        with self.assertRaises(ValueError):self.apply('confirm',nonce=first)
        self.apply('confirm',nonce=second)
        self.assertEqual(self.journal.read()['good'],NEW)
        self.assertIsNone(self.journal.read()['trial'])

    def test_wrong_slot_downgrade_and_stale_revision(self):
        for candidate in ({**NEW,'slot':'A'},{**NEW,'sequence':10}):
            with self.assertRaises(ValueError):self.apply('arm',candidate=candidate)
        with self.assertRaises(ValueError):self.journal.transition('select',99)
        self.assertEqual(self.journal.read()['revision'],0)

    def test_exclusive_writer_and_no_reset(self):
        with self.assertRaises(BlockingIOError):Journal(self.root)
        with self.assertRaises(FileExistsError):self.journal.initialize(NEW.copy())

    def test_corruption_fails_closed(self):
        (self.root/'state.json').write_text('{}')
        with self.assertRaises(ValueError):self.journal.read()
        with self.assertRaises(FileExistsError):self.journal.initialize(GOOD.copy())

    def test_interruption_preserves_old_or_complete_new_state(self):
        for point in ('file-durable','state-published','directory-durable'):
            before=self.journal.read()
            def fail(actual):
                if point==actual:raise OSError('injected crash')
            with self.assertRaises(OSError):self.journal.transition('select',before['revision'],checkpoint=fail)
            after=self.journal.read()
            self.assertEqual(after['revision'],before['revision']+(point!='file-durable'))
            self.assertEqual(after['good'],GOOD)

    def test_actual_process_death_consumes_one_attempt(self):
        self.apply('arm',candidate=NEW.copy())
        self.journal.close()
        code="""import os,sys;sys.path.insert(0,sys.argv[1]);from boot_trial import Journal
j=Journal(sys.argv[2]);j.transition('select',1,checkpoint=lambda p:os._exit(93) if p=='state-published' else None)
"""
        try:
            result=subprocess.run([sys.executable,'-c',code,str(Path(__file__).resolve().parents[1]/'update'),str(self.root)],timeout=10)
        finally:self.journal=Journal(self.root)
        self.assertEqual(result.returncode,93)
        self.assertEqual(self.journal.read()['attempts_left'],2)
        self.assertEqual(self.journal.read()['good'],GOOD)
        self.assertEqual(self.apply('select')['state']['attempts_left'],1)
