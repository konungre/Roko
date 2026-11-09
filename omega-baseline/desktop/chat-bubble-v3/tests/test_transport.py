"""Real subprocess/pipe tests; fixture worker is explicitly not native Omega."""
import json,pathlib,sys,threading,time,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'app'))
from omega_transport import OmegaTransport,decode_reply
WORKER='''
import json,sys,time
history=[]
for line in sys.stdin:
 request=json.loads(line);text=request['text'];history.append(text)
 if text=='slow':time.sleep(5)
 if text=='crash':sys.exit(3)
 if text=='overflow':print('x'*70000,flush=True);continue
 if text=='malformed':print('{broken',flush=True);continue
 if text=='noise':print('diagnostic',flush=True)
 print(json.dumps(dict(text=' / '.join(history),context_ids=[],executed_actions=0)),flush=True)
'''
class TransportTests(unittest.TestCase):
 def transport(self,timeout=2):
  t=OmegaTransport([sys.executable,'-u','-c',WORKER],timeout=timeout)
  self.addCleanup(t.close);return t
 def turn(self,t,text):
  event=threading.Event();result=[]
  cancel=t.submit(text,lambda answer,error:(result.append((answer,error)),event.set()))
  self.assertTrue(event.wait(5),'callback missing')
  return result[0]
 def test_two_turn_history_and_literal_text(self):
  t=self.transport();text='Hello "Ω"\n$(touch /tmp/not-a-command)'
  self.assertEqual(self.turn(t,text),(text,None))
  self.assertEqual(self.turn(t,'next'),(text+' / next',None))
 def test_noise(self):self.assertEqual(self.turn(self.transport(),'noise'),('noise',None))
 def test_cancel_and_explicit_reset(self):
  t=self.transport();event=threading.Event();result=[]
  cancel=t.submit('slow',lambda a,e:(result.append((a,e)),event.set()))
  cancel();self.assertTrue(event.wait(5));self.assertIsNotNone(result[0][1]);self.assertIsNone(t.proc)
  with self.assertRaisesRegex(RuntimeError,'New conversation'):t.submit('next',lambda *_:None)
  t.reset();self.assertEqual(self.turn(t,'new'),('new',None))
 def test_busy(self):
  t=self.transport();cancel=t.submit('slow',lambda *_:None)
  with self.assertRaisesRegex(RuntimeError,'already running'):t.submit('other',lambda *_:None)
  cancel()
 def test_timeout(self):
  _,error=self.turn(self.transport(timeout=.15),'slow');self.assertIn('timed out',error)
 def test_crash_bad_json_and_overflow(self):
  for text in ['crash','malformed','overflow']:
   with self.subTest(text=text):
    t=self.transport();answer,error=self.turn(t,text)
    self.assertIsNone(answer);self.assertTrue(error);self.assertTrue(t.failed);self.assertIsNone(t.proc)
 def test_close_reaps_worker(self):
  t=self.transport();self.turn(t,'hello');proc=t.proc;t.close()
  self.assertIsNotNone(proc.poll());self.assertIsNone(t.proc)
 def test_input_contract(self):
  t=self.transport()
  for value in ['', 'x'*4001,None]:
   with self.assertRaises(ValueError):t.submit(value,lambda *_:None)
 def test_reply_contract(self):
  for changes in [dict(executed_actions=True),dict(executed_actions=1),dict(context_ids=['unknown']),dict(text='')]:
   value=dict(text='ok',context_ids=[],executed_actions=0);value.update(changes)
   with self.assertRaises(ValueError):decode_reply(json.dumps(value))
