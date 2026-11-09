import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,copy
from console_harness import ConsoleHarness
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='sent input',context=[],max_output_tokens=32)
def snap(pending=None,committed=False):return dict(api_version=2,status='snapshot',session_id='s',revision=int(committed),pending=pending,history=[dict(role='user',content='sent input'),dict(role='assistant',content='saved reply')] if committed else [])
def inspect(h,packet):
 assert h.action('inspect',confirmed=True);return h.snapshot(h.wire[-1]['ticket'],packet)
def start():
 h=ConsoleHarness('sent input');assert h.action('send',confirmed=True,request=REQ,owned_worker='local');h.edit('next unsent draft');return h
class ConsoleBehaviorTests(unittest.TestCase):
 def test_waiting_ticks_do_not_timeout_retry_or_clear_input(self):
  h=start();before=copy.deepcopy(h.wire)
  for elapsed in (0,31,150,10000):self.assertIn('next unsent draft',h.render(elapsed))
  self.assertEqual(h.wire,before);self.assertEqual(h.stops,[]);self.assertIn('Still waiting',h.render(10000))
 def test_rapid_duplicate_clicks_emit_one_proposal(self):
  h=start();self.assertFalse(h.action('send',confirmed=True,request=REQ));self.assertEqual(len(h.wire),1)
  self.assertTrue(h.action('stop',confirmed=True));self.assertFalse(h.action('stop',confirmed=True));self.assertEqual(len(h.stops),1)
 def test_ownership_advance_blocks_stop_without_effect(self):
  h=start();h.registry['local']=dict(h.registry['local'],request_id='later-work')
  self.assertFalse(h.action('stop',confirmed=True));self.assertEqual(h.stops,[])
 def test_unknown_action_and_missing_confirmation_do_nothing(self):
  h=start();before=copy.deepcopy(h.wire)
  self.assertFalse(h.action('execute_model_text',confirmed=True));self.assertFalse(h.action('stop'));self.assertEqual(h.wire,before);self.assertEqual(h.stops,[])
 def test_terminal_draft_is_escaped_plain_text(self):
  h=start();h.edit('\x1b[2J<script>literal</script>');text=h.render(10)
  self.assertNotIn('\x1b',text);self.assertIn('\\u001b[2J',text);self.assertIn('<script>literal</script>',text)
 def test_lost_recovery_requires_inspect_and_separate_decisions(self):
  h=start();h.action('stop',confirmed=True);h.stopped(h.stops[-1]);inspect(h,snap('r'));h.action('recover',confirmed=True);h.loss();before=len(h.wire)
  self.assertFalse(h.action('reconcile',confirmed=True));self.assertFalse(h.action('release',confirmed=True));self.assertEqual(len(h.wire),before)
  inspect(h,snap());self.assertFalse(h.action('reconcile'));self.assertTrue(h.action('reconcile',confirmed=True));self.assertTrue(h.action('release',confirmed=True));self.assertIn('next unsent draft',h.render())
 def test_stale_snapshot_retains_displayed_history(self):
  h=start();inspect(h,snap(committed=True));before=h.render();h.action('inspect',confirmed=True)
  self.assertFalse(h.snapshot(h.wire[-1]['ticket'],snap()));self.assertIn('Saved messages: 2',h.render());self.assertIn('saved transcript is retained',h.render())
 def test_saved_transcript_is_not_cleared_by_next_capture(self):
  h=start();inspect(h,snap(committed=True));self.assertTrue(h.action('release',confirmed=True))
  self.assertTrue(h.action('send',confirmed=True,request=dict(REQ,request_id='next',expected_revision=1,text='next unsent draft')));self.assertIn('Saved messages: 2',h.render())
 def test_duplicate_worker_callback_is_readable_and_has_no_effect(self):
  h=start();h.action('stop',confirmed=True);self.assertTrue(h.stopped(h.stops[-1]));before=copy.deepcopy(h.ui.view());wire=len(h.wire)
  self.assertFalse(h.stopped(h.stops[-1]));self.assertEqual(h.ui.view(),before);self.assertEqual(len(h.wire),wire);self.assertIn('Outdated worker status ignored',h.render())
 def test_late_recovery_callback_after_reconciliation_is_ignored(self):
  h=start();h.action('stop',confirmed=True);h.stopped(h.stops[-1]);inspect(h,snap('r'));h.action('recover',confirmed=True);old=h.wire[-1]['ticket'];h.loss();inspect(h,snap());h.action('reconcile',confirmed=True);before=copy.deepcopy(h.ui.view());count=len(h.wire)
  self.assertFalse(h.recovery_reply(dict(api_version=2,status='interrupted',session_id='s',request_id='r',revision=0),old));self.assertEqual(h.ui.view(),before);self.assertEqual(len(h.wire),count);self.assertTrue(h.action('release',confirmed=True))
 def test_malformed_snapshot_and_invalid_action_do_not_clear_display(self):
  h=start();inspect(h,snap(committed=True));h.action('inspect',confirmed=True);bad=snap();bad['session_id']=[]
  self.assertFalse(h.snapshot(h.wire[-1]['ticket'],bad));self.assertIn('Saved messages: 2',h.render());self.assertFalse(h.action([],confirmed=True))
 def test_idle_late_connection_notice_is_nonfatal(self):
  h=ConsoleHarness('unsent text');self.assertFalse(h.loss());self.assertIn('Ready',h.render());self.assertIn('unsent text',h.render());self.assertEqual(h.wire,[])

 def test_elapsed_resets_only_for_an_accepted_new_send(self):
  now=[10.0];h=ConsoleHarness('sent input',clock=lambda:now[0]);h.action('send',confirmed=True,request=REQ)
  now[0]=15;self.assertFalse(h.action('send',confirmed=True,request=REQ));self.assertIn('Elapsed: 5 s',h.render())
  inspect(h,snap(committed=True));h.action('release',confirmed=True);h.edit('next draft');now[0]=100
  self.assertTrue(h.action('send',confirmed=True,request=dict(REQ,request_id='next',expected_revision=1,text='next draft')));self.assertIn('Elapsed: 0 s',h.render());now[0]=102;self.assertIn('Elapsed: 2 s',h.render())

 def test_structured_limit_error_keeps_draft_and_retires_worker_binding(self):
  h=start();self.assertTrue(h.error(dict(api_version=2,status='error',session_id='s',request_id='r',code='context_limit')))
  self.assertIn('exceeds the active model input limit',h.render());self.assertIn('next unsent draft',h.render());self.assertFalse(h.action('stop',confirmed=True));self.assertEqual(h.stops,[])

 def test_missing_snapshot_is_not_presented_as_empty_history(self):
  h=start();self.assertIn('Saved messages: not yet inspected',h.render());inspect(h,snap());self.assertIn('Saved messages: 0',h.render())

 def test_invalid_initial_send_does_not_claim_an_active_request(self):
  h=ConsoleHarness('unsent text');self.assertFalse(h.action('send',confirmed=True,request={'text':'bad'}))
  self.assertIn('Ready',h.render());self.assertIn('Send was not accepted',h.render());self.assertEqual(h.wire,[]);self.assertIn('unsent text',h.render())

if __name__=='__main__':unittest.main()
