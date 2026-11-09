"""Versioned evidence facts; proposals never carry executor authority."""
from dataclasses import dataclass,asdict
from enum import Enum
import hashlib,json,re
class Stage(str,Enum):
 DESIRED='desired';RESOLVED='resolved';BUILT='built';ACTIVATED='activated';RUNNING='running';OBSERVED='observed';HEALTH='health'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
@dataclass(frozen=True)
class Fact:
 machine:str
 backend:str
 revision:int
 stage:Stage
 generation:str
 evidence_sha256:str
 predecessor:str
 def __post_init__(self):
  if self.backend not in ('nix','guix'):raise ValueError('backend')
  if type(self.revision)!=int or self.revision<1:raise ValueError('revision')
  if not isinstance(self.stage,Stage):raise ValueError('stage')
  for s in (self.machine,self.generation):
   if not re.fullmatch('[a-zA-Z0-9._-]{1,128}',s):raise ValueError('identity')
  for s in (self.evidence_sha256,self.predecessor):
   if not re.fullmatch('[0-9a-f]{64}',s):raise ValueError('digest')
 def document(self):return {**asdict(self),'stage':self.stage.value,'schema':'roko-os-fact-v1'}
 def atom(self):
  # Strict symbols and hexadecimal provenance; no executable user expressions.
  return '(roko-os-fact v1 %s %s %d %s %s %s %s)'%(self.machine,self.backend,self.revision,self.stage.value,self.generation,'h'+self.evidence_sha256,'h'+self.predecessor)
@dataclass(frozen=True)
class Proposal:
 operation:str
 expected_revision:int
 generation:str
 evidence_sha256:str
class Executor:
 """A trusted caller supplies review policy outside AtomSpace/serialized facts."""
 def __init__(self,review,handlers):self.review=review;self.handlers=handlers
 def execute(self,proposal,current_revision):
  if not isinstance(proposal,Proposal):raise ValueError('typed proposal required')
  if proposal.operation not in ('build','stage','activate','rollback'):raise ValueError('operation')
  if type(proposal.expected_revision)!=int or proposal.expected_revision!=current_revision:raise ValueError('stale revision')
  if not re.fullmatch('[a-zA-Z0-9._-]{1,128}',proposal.generation) or not re.fullmatch('[0-9a-f]{64}',proposal.evidence_sha256):raise ValueError('identity')
  if self.review(proposal) is not True:raise PermissionError('explicit external review required')
  return self.handlers[proposal.operation](proposal)
