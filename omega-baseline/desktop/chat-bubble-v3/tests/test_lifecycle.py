import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'app'))
from conversation_state import ConversationState
from input_mask import opaque_intersection

class TurnTests(unittest.TestCase):
 def test_late_and_duplicate_results(self):
  s=ConversationState();old=s.begin('hello');s.stop();new=s.begin('again')
  self.assertFalse(s.finish(old,'stale'))
  self.assertTrue(s.pending)
  self.assertTrue(s.finish(new,'current'))
  self.assertFalse(s.finish(new,'duplicate'))
  self.assertEqual(s.turns[-1],('Roko','current'))
 def test_busy_and_close(self):
  s=ConversationState();token=s.begin('hello');calls=[]
  s.attach_cancel(token,lambda:calls.append('cancel'))
  self.assertIsNone(s.begin('overlap'))
  s.stop(close=True);s.stop(close=True)
  self.assertEqual(calls,['cancel'])
  self.assertFalse(s.finish(token,'late'))
  self.assertIsNone(s.begin('closed'))
 def test_cancel_failure(self):
  s=ConversationState();token=s.begin('hello')
  def fail():raise RuntimeError('transport')
  s.attach_cancel(token,fail);s.stop()
  self.assertFalse(s.pending)
  self.assertIn('could not confirm',s.turns[-1][1])
 def test_finish_before_cancel_attached(self):
  s=ConversationState();token=s.begin('hello');s.finish(token,'done')
  s.attach_cancel(token,lambda:None)
  self.assertIsNone(s.cancel)
 def test_errors_and_blank_results(self):
  for answer,error in ((None,'offline'),('',None),(None,None)):
   s=ConversationState();token=s.begin('hello');self.assertTrue(s.finish(token,answer,error))
   self.assertFalse(s.pending);self.assertIsInstance(s.turns[-1][1],str)

class InputTests(unittest.TestCase):
 def test_near_opaque_artwork_body_is_clickable(self):
  self.assertEqual(opaque_intersection([(0,239,240,252,253,255)],6,1),((2,0,4,1),))
 def test_soft_crossfade_edges_still_pass_through(self):
  self.assertEqual(opaque_intersection([(253,253,253),(253,239,0)],3,1),((0,0,1,1),))
 def test_crossfade_intersection(self):
  self.assertEqual(opaque_intersection([(0,255,255,0),(255,255,0,0)],4,1),((1,0,1,1),))
 def test_empty_and_malformed(self):
  self.assertEqual(opaque_intersection([],4,1),())
  with self.assertRaises(ValueError):opaque_intersection([(255,)],4,1)
 def test_rows_not_joined(self):
  self.assertEqual(opaque_intersection([(255,255,255,255)],2,2),((0,0,2,1),(0,1,2,1)))

from chat_bubble import ChatBubble
class Widget:
 def __init__(self,text=''):self.text=text;self.sensitive=True
 def get_text(self):return self.text
 def set_text(self,text):self.text=text
 def set_sensitive(self,value):self.sensitive=value
 def grab_focus(self):pass
 def has_focus(self):return True
class Queue:
 def __init__(self):self.calls=[]
 def idle_add(self,fn):self.calls.append(fn)
 def drain(self):
  while self.calls:self.calls.pop(0)()
class BubbleTests(unittest.TestCase):
 def test_enter_submits_focused_composer_once(self):
  from types import SimpleNamespace
  calls=[];b=self.bubble(lambda text,done:calls.append(text))
  b.Gdk=SimpleNamespace(KEY_Escape=65307,KEY_Return=65293,KEY_KP_Enter=65421)
  self.assertTrue(b.key(None,SimpleNamespace(keyval=65293)))
  b.key(None,SimpleNamespace(keyval=65421))
  self.assertEqual(calls,['hello'])
 def bubble(self,submit):
  b=ChatBubble.__new__(ChatBubble);b.state=ConversationState();b.submit=submit;b.resetting=False
  b.entry=Widget('hello');b.reply=Widget();b.status=Widget();b.GLib=Queue()
  return b
 def test_synchronous_transport_failure(self):
  def fail(text,done):raise RuntimeError('offline')
  b=self.bubble(fail);b.send(None);b.GLib.drain()
  self.assertFalse(b.state.pending);self.assertTrue(b.entry.sensitive)
  self.assertIn('offline',b.reply.text)
 def test_no_fabricated_service(self):
  b=self.bubble(None);b.send(None)
  self.assertEqual(b.state.turns,[]);self.assertIn('not connected',b.status.text)
 def test_async_completion_and_duplicate(self):
  callbacks=[];b=self.bubble(lambda text,done:callbacks.append(done))
  b.send(None);self.assertFalse(b.entry.sensitive)
  callbacks[0]('answer');callbacks[0]('duplicate');b.GLib.drain()
  self.assertIn('answer',b.reply.text);self.assertNotIn('duplicate',b.reply.text)
 def test_destroyed_before_delivery(self):
  callbacks=[];b=self.bubble(lambda text,done:callbacks.append(done))
  b.send(None);b.state.stop(close=True);before=b.reply.text
  callbacks[0]('late');b.GLib.drain();self.assertEqual(b.reply.text,before)
