"""Fixture freshness decisions, not production authentication or user approval."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from fixture_restart_choice import FixtureChoices,Choice
class FixtureChoiceTests(unittest.TestCase):
 def test_keep_stopped_never_calls_start_and_consumes_choice(self):
  gate=FixtureChoices();calls=[];choice=gate.choose('keep-stopped');self.assertIsNone(gate.apply(choice,lambda:calls.append(1)));self.assertEqual(calls,[])
  with self.assertRaises(ValueError):gate.apply(choice,lambda:calls.append(1))
  self.assertEqual(calls,[])
 def test_failure_consumes_choice_until_new_explicit_choice(self):
  gate=FixtureChoices();choice=gate.choose('restart');calls=[]
  def failed():calls.append(1);raise RuntimeError('controlled fixture launch failure')
  with self.assertRaises(RuntimeError):gate.apply(choice,failed)
  with self.assertRaises(ValueError):gate.apply(choice,failed)
  self.assertEqual(calls,[1]);self.assertEqual(gate.apply(gate.choose('restart'),lambda:'fresh'), 'fresh')
 def test_stale_epoch_revision_and_invalid_action_rejected_before_start(self):
  gate=FixtureChoices();choice=gate.choose('restart');gate.changed(new_desktop=True);calls=[]
  for invalid in (choice,Choice('restart',gate.epoch,True),Choice('execute-output',gate.epoch,gate.revision),{'action':'restart'}):
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):gate.apply(invalid,lambda:calls.append(1))
  self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
