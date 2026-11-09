import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
"""Runnable console walkthrough with synthetic callbacks and zero real transport."""
import argparse
from console_harness import ConsoleHarness
REQ=dict(api_version=2,op='turn',session_id='demo',request_id='r',expected_revision=0,text='Tell me what changed.',context=[],max_output_tokens=32)
def snapshot(pending=None,committed=False):return dict(api_version=2,status='snapshot',session_id='demo',revision=int(committed),pending=pending,history=[dict(role='user',content=REQ['text']),dict(role='assistant',content='A saved reply.')] if committed else [])
def inspect(h,packet):h.action('inspect',confirmed=True);assert h.snapshot(h.wire[-1]['ticket'],packet)
def show(label,h,elapsed=0):print('\n'+label+'\n'+h.render(elapsed))
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scenario',choices=('recovery-loss','commit-wins'),required=True);args=p.parse_args()
print('Console prototype: synthetic events; no endpoint, model or signal execution.')
h=ConsoleHarness(REQ['text']);h.action('send',confirmed=True,request=REQ,owned_worker='local-demo');h.edit('My next unsent thought.');show('After Send',h)
show('After 65 seconds; no automatic request',h,65);h.action('stop',confirmed=True);show('After explicit Stop proposal',h,66)
if args.scenario=='recovery-loss':
 h.stopped(h.stops[-1]);inspect(h,snapshot('r'));h.action('recover',confirmed=True);h.loss();show('Recovery reply is withheld',h,67)
 h.action('reconcile',confirmed=True);show('Early reconciliation is blocked',h,68)
 inspect(h,snapshot());h.action('reconcile',confirmed=True);show('Fresh inspection; explicit reconciliation',h,69)
 h.action('release',confirmed=True);show('After explicit review',h)
else:
 stop=h.stops[-1];h.reply(dict(api_version=2,status='completed',session_id='demo',request_id='r',revision=1,text='A saved reply.',executed_actions=0));assert not h.ui.can_execute_cancel(stop,current_binding=h.registry['local-demo'])
 h.ui.cancel_not_executed(stop);show('Committed reply suppresses the queued stop',h,67)
 inspect(h,snapshot(committed=True));h.action('release',confirmed=True);show('After saved-session review',h)
print('\nRecorded proposals: '+str(len(h.wire))+' wire, '+str(len(h.stops))+' local stop. Actual executions: 0.')
