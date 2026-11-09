"""Finite controller-owned state. Validation never grants action permission."""
from dataclasses import dataclass
from enum import Enum
import hashlib,json,re

class Phase(str,Enum):
 OPEN="open"
 VERIFIED="verified"
 CLOSED="closed"

@dataclass(frozen=True)
class Evidence:
 source: str
 text: str
 sha256: str

def invoice_evidence(text):
 """Strict supported fixture grammar, not a general invoice parser."""
 match=re.fullmatch(r"Invoice ([A-Z0-9]+); total ([0-9]+\.[0-9]{2})\.",text)
 if not match:raise ValueError("Unsupported or ambiguous invoice evidence")
 return {"invoice":match[1],"total":match[2]}

class WorkingState:
 def __init__(self,task_id,goal):
  if not isinstance(task_id,str) or not task_id or len(task_id)>128:raise ValueError("Invalid task ID")
  if not isinstance(goal,str) or not goal or len(goal)>2000:raise ValueError("Invalid goal")
  self.task_id=task_id;self.goal=goal;self.phase=Phase.OPEN
  self._evidence={};self._proposal=None;self._verification=None
 def _open(self):
  if self.phase is not Phase.OPEN:raise ValueError("Task is not open")
 def add_evidence(self,evidence_id,source,text):
  self._open()
  if len(self._evidence)>=16:raise ValueError("Evidence capacity exceeded")
  if not isinstance(evidence_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",evidence_id):raise ValueError("Invalid evidence ID")
  if evidence_id in self._evidence:raise ValueError("Evidence IDs cannot be overwritten")
  if not isinstance(source,str) or not source or len(source)>1000:raise ValueError("Missing bounded provenance")
  if not isinstance(text,str) or not text or len(text)>8000:raise ValueError("Invalid evidence text")
  self._evidence[evidence_id]=Evidence(source,text,hashlib.sha256(text.encode()).hexdigest())
 def clear_proposal(self):
  self._open();self._proposal=None;self._verification=None
 def propose(self,task_id,name,arguments,evidence_ids):
  self._open()
  self._proposal=None;self._verification=None  # Invalid submissions cannot leave a stale candidate.
  if task_id!=self.task_id:raise ValueError("Cross-task proposal")
  schemas={'record_invoice':{'invoice','total'},'record_answer':{'text'}}
  if name not in schemas:raise ValueError("Unsupported inert proposal")
  if type(arguments) is not dict or set(arguments)!=schemas[name]:raise ValueError("Invalid proposal fields")
  if any(type(v) is not str or len(v)>1000 for v in arguments.values()):raise ValueError("Invalid proposal values")
  if type(evidence_ids) is not list or len(evidence_ids)!=1 or type(evidence_ids[0]) is not str or evidence_ids[0] not in self._evidence:raise ValueError("Exactly one existing evidence reference required")
  self._proposal={'name':name,'arguments':dict(arguments),'evidence_ids':list(evidence_ids)}
  self._verification=None
 def verify_invoice(self):
  self._open()
  if self._proposal is None:raise ValueError("No proposal")
  evidence=self._evidence[self._proposal['evidence_ids'][0]]
  try:
   expected=invoice_evidence(evidence.text)
   accepted=self._proposal['name']=='record_invoice' and self._proposal['arguments']==expected
   reason='exact match' if accepted else 'arguments disagree with strict source extraction'
  except ValueError:
   accepted=False;reason='unsupported source grammar'
  self._verification={'accepted':accepted,'reason':reason,'checker':'strict-invoice-v1','source_sha256':evidence.sha256,'authorizes_actions':False}
  if accepted:self.phase=Phase.VERIFIED
  return dict(self._verification)
 def verify_quote(self):
  return self._verify_answer('exact-quote-v1',lambda text:text)
 def verify_arithmetic(self):
  def calculate(text):
   match=re.fullmatch(r"Arithmetic: (-?[0-9]{1,6}) ([+*-]) (-?[0-9]{1,6})\.",text)
   if not match:raise ValueError("Unsupported arithmetic grammar")
   a,b=int(match[1]),int(match[3])
   return str({'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b}[match[2]]())
  return self._verify_answer('integer-arithmetic-v1',calculate)
 def _verify_answer(self,checker,extract):
  self._open()
  if self._proposal is None:raise ValueError("No proposal")
  evidence=self._evidence[self._proposal['evidence_ids'][0]]
  try:
   expected={'text':extract(evidence.text)}
   accepted=self._proposal['name']=='record_answer' and self._proposal['arguments']==expected
   reason='exact match' if accepted else 'arguments disagree with deterministic source check'
  except ValueError:
   accepted=False;reason='unsupported source grammar'
  self._verification={'accepted':accepted,'reason':reason,'checker':checker,'source_sha256':evidence.sha256,'authorizes_actions':False}
  if accepted:self.phase=Phase.VERIFIED
  return dict(self._verification)
 def close(self):
  if self.phase is not Phase.VERIFIED:raise ValueError("Only verified tasks can close")
  self.phase=Phase.CLOSED
 def snapshot(self):
  # Detached JSON data prevents callers mutating internal nested values.
  return json.loads(json.dumps({'task_id':self.task_id,'goal':self.goal,'phase':self.phase.value,'evidence':{k:vars(v) for k,v in self._evidence.items()},'proposal':self._proposal,'verification':self._verification,'executed_actions':0}))
