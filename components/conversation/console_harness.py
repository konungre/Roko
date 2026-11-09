"""Console behavior prototype; records proposals, never executes transport/signals."""
import copy,json,time
if __package__:
    from .cancellation_ux import CancellationUX
else:
    from cancellation_ux import CancellationUX
TITLES={'idle':'Ready','waiting':'Waiting for reply','stop_requested':'Stop requested',
 'worker_stopped_inspect_required':'Worker stopped; inspect session','outcome_unknown':'Request result unknown',
 'recovery_outcome_uncertain':'Recovery result unknown','recovery_reconciled_review_required':'Session inspected; choose next step',
 'recovery_recorded_inspect_required':'Recovery recorded; inspect session','reply_received_review_required':'Reply received; review session',
 'error_review_required':'Service status received'}
BLOCKED={'send':'Send was not accepted. Review the draft and current request state.',
 'stop':'Stop is unavailable for this request or worker binding.',
 'recover':'Recovery needs a confirmed worker stop and fresh session inspection.',
 'reconcile':'Inspect the session after recovery response loss before reconciling.',
 'replay':'Inspect the session before replaying the original request.',
 'release':'Review a fresh snapshot with no pending claim before continuing.',
 'inspect':'Choose session inspection explicitly.'}
class ConsoleHarness:
 def __init__(self,text='',*,clock=time.monotonic):
  self._clock=clock;self._sent_at=None;self.ui=CancellationUX(text);self.registry={};self.wire=[];self.stops=[];self.decisions=[];self.feedback='';self.session=None;self.snapshots={}
 def edit(self,text):self.ui.edit(text)
 def action(self,name,*,confirmed=False,request=None,owned_worker=None):
  if type(name) is not str or name not in BLOCKED:self.feedback='Unknown local action ignored.';return False
  if confirmed is not True:self.feedback='Choose this action explicitly before it can proceed.';return False
  try:
   if name=='send':
    packet=self.ui.begin(request,confirmed=True,owned_worker=owned_worker);self.session=packet['session_id'];self._sent_at=self._clock()
    if owned_worker is not None:self.registry[owned_worker]=self.ui.worker_binding()
    self.wire.append(dict(packet=packet,kind='turn'))
   elif name=='inspect':self.wire.append(dict(kind='snapshot',**self.ui.inspect(confirmed=True)))
   elif name=='stop':
    binding=self.ui.worker_binding()
    if binding is None or self.registry.get(binding['worker_handle'])!=binding:raise ValueError('Ownership changed')
    proposal=self.ui.request_cancel(confirmed=True)
    if not self.ui.can_execute_cancel(proposal,current_binding=self.registry.get(proposal['worker_handle'])):raise ValueError('Ownership changed')
    self.stops.append(proposal)
   elif name=='recover':
    packet=self.ui.recover(confirmed=True);self.wire.append(dict(kind='recover',packet=packet,ticket=self.ui.recovery_ticket()))
   elif name=='reconcile':self.decisions.append(dict(action=name,**self.ui.reconcile_recovery(confirmed=True)))
   elif name=='replay':self.wire.append(dict(kind='replay',packet=self.ui.replay(confirmed=True)))
   else:self.ui.review_and_release(confirmed=True);self.decisions.append(dict(action='release'))
  except ValueError:self.feedback=BLOCKED[name];return False
  self.feedback='';return True
 def snapshot(self,ticket,packet):
  try:
   if type(packet) is not dict or type(packet.get('revision')) is not int or type(packet.get('history')) is not list or type(packet.get('session_id')) is not str:raise ValueError('Invalid snapshot')
   prior=self.snapshots.get(packet.get('session_id'))
   if prior and (packet['revision']<prior['revision'] or packet['history'][:len(prior['history'])]!=prior['history']):raise ValueError('Transcript regressed')
   self.ui.receive_snapshot(ticket,packet)
  except ValueError:self.feedback='Snapshot rejected. The saved transcript is retained.';return False
  self.snapshots[packet['session_id']]=copy.deepcopy(packet);self.feedback='';return True
 def reply(self,packet):
  try:self.ui.receive_reply(packet)
  except ValueError:self.feedback='Reply rejected. Inspect the session before continuing.';return False
  self.feedback='';return True
 def error(self,packet):
  try:self.ui.receive_error(packet)
  except ValueError:self.feedback='Service status rejected. Inspect the session before continuing.';return False
  binding=self.ui.worker_binding()
  if binding is not None and self.registry.get(binding['worker_handle'])==binding:self.registry.pop(binding['worker_handle'])
  code=self.ui.view()['last_turn_error']
  self.feedback={'context_limit':'This request exceeds the active model input limit. Your draft is retained.',
                 'context_projection_limit':'The selected context policy cannot fit this request. Your draft is retained.',
                 'pending':'The original request is still pending. Inspect before deciding what to do.',
                 'busy':'The session has pending work. Inspect before deciding what to do.'}.get(code,'Service status received. Inspect the session before continuing.')
  return True
 def stopped(self,proposal):
  try:self.ui.worker_stopped(proposal)
  except ValueError:self.feedback='Outdated worker status ignored. Your draft is retained.';return False
  self.feedback='';return True
 def loss(self):
  try:self.ui.transport_lost()
  except ValueError:self.feedback='Outdated connection status ignored. Your draft is retained.';return False
  self.feedback='';return True
 def recovery_reply(self,packet,ticket):
  try:self.ui.receive_recovery_reply(packet,ticket=ticket)
  except ValueError:self.feedback='Outdated recovery response ignored. Inspect the session before continuing.';return False
  self.feedback='';return True
 def render(self,elapsed=None):
  if elapsed is None:elapsed=0 if self._sent_at is None else self._clock()-self._sent_at
  state=self.ui.view(elapsed);snapshot=self.snapshots.get(self.session);history=snapshot['history'] if snapshot is not None else None
  lines=[TITLES.get(state['phase'],'Review session'),state.get('message','Your draft is retained.'),
         'Draft: '+json.dumps(state['draft'],ensure_ascii=True),'Saved messages: '+(str(len(history)) if history is not None else 'not yet inspected')]
  if state.get('received_reply'):lines.append('Reply: '+json.dumps(state['received_reply']['text'],ensure_ascii=True))
  if state['phase']!='idle':lines.append('Elapsed: '+str(state['elapsed_seconds'])+' s')
  if self.feedback:lines.append(self.feedback)
  return '\n'.join(lines)
