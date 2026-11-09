import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sys,pathlib,unittest,copy
from desktop_draft import DesktopDraft
from waiting_view import waiting_view
REQ=dict(api_version=2,op='turn',session_id='s',request_id='r',expected_revision=0,text='original input',context=[])
def captured():
 d=DesktopDraft('original input');d.begin(REQ,confirmed=True);return d
class WaitingTests(unittest.TestCase):
 def test_elapsed_never_implies_failure_or_authorizes_retry(self):
  d=captured()
  for elapsed in (0,31,150,3600):
   v=waiting_view(d,elapsed);self.assertEqual(v['request_outcome'],'not_confirmed');self.assertIsNone(v['progress_fraction'])
   for key in ('send_enabled','replay_enabled','recover_enabled','automatic_requests','automatic_timeout'):self.assertFalse(v[key])
 def test_loss_preserves_captured_request_and_edited_draft(self):
  d=captured();d.edit('next unsent input');before=copy.deepcopy(d.view());v=waiting_view(d,75,connection_lost=True)
  self.assertEqual(v['request_outcome'],'unknown');self.assertEqual(v['draft'],'next unsent input');self.assertEqual(d.view(),before)
 def test_plain_text_and_defensive_history(self):
  d=captured();d.receive_snapshot(dict(api_version=2,status='snapshot',session_id='s',revision=1,pending=None,history=[dict(role='user',content='<script>literal</script>'),dict(role='assistant',content='saved reply')]))
  v=waiting_view(d,5);self.assertTrue(v['render_as_plain_text']);self.assertEqual(v['transcript'][0]['content'],'<script>literal</script>');v['transcript'].clear();self.assertEqual(len(d.view()['active']['transcript']),2)
 def test_invalid_time_is_not_rendered_as_progress(self):
  d=captured()
  for value in (-1,True,float('nan'),float('inf'),'10'):
   with self.assertRaises(ValueError):waiting_view(d,value)
 def test_idle_draft_cannot_claim_request_waiting(self):
  with self.assertRaises(ValueError):waiting_view(DesktopDraft('unsent only'),0)
if __name__=='__main__':unittest.main()
