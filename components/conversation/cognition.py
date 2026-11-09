"""A narrow, explicit user-assertion bridge into actual NAL-1 inference.

It does not infer unstated facts, parse arbitrary prose as code, or learn a world.
The accepted grammar is intentionally small; other conversation remains ordinary.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.nars_hyperon.source.contract import canonical,make_premise
from components.nars_hyperon.source.runtime import run_native
if __package__:
    from .assertions import extract,parse_assertions
else:
    from assertions import extract,parse_assertions


def bind_request(request,binding):
    """Carry the complete durable identity digest into native premise provenance."""
    if binding is None:return request
    digest=hashlib.sha256(canonical(binding)).hexdigest()
    result=dict(request,task_id='req_'+digest[:28])
    result['premises']=[make_premise(p['id'],p['source']+';turn:'+digest,
        p['subject'],p['predicate'],p['frequency_milli'],p['confidence_milli']) for p in request['premises']]
    return result


def write_record(path,record):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(canonical(record)+b'\n');stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


class NarsCognition:
    def __init__(self,manifest_path,admission,evidence_root,*,run=run_native):
        self.manifest=json.loads(Path(manifest_path).read_bytes())
        self.admission=admission
        root=Path(evidence_root)
        if not root.is_absolute():raise ValueError('Trusted absolute evidence root required')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.evidence_root=Path(tempfile.mkdtemp(prefix='session-',dir=root))
        self.run=run;self.receipts=[]

    def __call__(self,text,history):
        return self._reason(text,history,None)

    def reason_turn(self,text,history,binding):
        """Bind v2 evidence to the already claimed durable request identity."""
        if type(binding) is not dict or set(binding)!={'session_id','request_id','revision'}:
            raise ValueError('Cognitive turn binding schema')
        for key in ('session_id','request_id'):
            if type(binding[key]) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',binding[key]) is None:
                raise ValueError('Cognitive turn binding identifier')
        if type(binding['revision']) is not int or binding['revision']!=len(history)//2:
            raise ValueError('Cognitive turn binding revision')
        return self._reason(text,history,dict(binding))

    def _reason(self,text,history,binding):
        snapshot=canonical({'text':text,'history':history})
        parsed=parse_assertions(text,len(history)//2+1)
        if parsed is None:return []
        request=bind_request(parsed.request,binding)
        identity=hashlib.sha256(canonical(binding)).hexdigest() if binding is not None else request['task_id']
        directory=self.evidence_root/(identity+'-'+uuid.uuid4().hex)
        directory.mkdir(mode=0o700)
        fd=os.open(directory.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        provenance={'turn_binding':binding,'binding_sha256':identity,
            'snapshot_sha256':hashlib.sha256(snapshot).hexdigest(),
            'native_request_sha256':hashlib.sha256(canonical(request)).hexdigest()}
        write_record(directory/'turn-start.json',dict(provenance,request=request,phase='prepared'))
        response,receipt=self.run(request,manifest=self.manifest,admission=self.admission,
            evidence_directory=directory/'native')
        if canonical({'text':text,'history':history})!=snapshot:raise ValueError('Conversation changed during inference')
        # Runtime verifies the native rows independently. Keep their full evidence
        # while giving the LLM a compact, explicitly uncertain prompt projection.
        conclusion=next(c for c in response['conclusions'] if c['rule']=='deduction')
        provenance['native_response_sha256']=hashlib.sha256(canonical(response)).hexdigest()
        write_record(directory/'turn-binding.json',provenance)
        self.receipts.append({**provenance,'request':request,'response':response,'receipt':receipt,
            'term_labels':parsed.labels,'premise_mode':parsed.mode,'evidence_directory':str(directory)})
        text=(f"MeTTa-NARS NAL-1 derived {parsed.labels[conclusion['subject']]} -> {parsed.labels[conclusion['predicate']]} "
              f"from the two {parsed.mode} premises (frequency={conclusion['frequency']:.6g}, "
              f"confidence={conclusion['confidence']:.6g}). Uncertain derived belief. "
              "Premise values f=1,c=0.9 are controller policy, not measured probabilities "
              "or verified facts. No action is authorized.")
        self.receipts[-1]['prompt_context']={'id':'nars_'+identity,'text':text}
        return [{'id':'nars_'+identity,'text':text}]
