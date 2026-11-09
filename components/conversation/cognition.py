"""A narrow, explicit user-assertion bridge into actual NAL-1 inference.

It does not infer unstated facts, parse arbitrary prose as code, or learn a world.
The accepted grammar is intentionally small; other conversation remains ordinary.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.nars_hyperon.source.contract import canonical,make_premise
from components.nars_hyperon.source.runtime import run_native

ASSERTION=re.compile(r'(?:^|(?<=[.!?])\s+)(?:a |an )?([a-z][a-z0-9_]{0,31}) is (?:a |an )?([a-z][a-z0-9_]{0,31})\.',re.I)


def extract(text,revision):
    """Only two whole affirmative sentences, forming one distinct-symbol chain."""
    matches=list(ASSERTION.finditer(text))
    if len(matches)!=2:return None
    if matches[0].start()!=0 or matches[1].start()!=matches[0].end():return None
    suffix=text[matches[1].end():].strip()
    if suffix and (not suffix.endswith('?') or any(c in suffix for c in '.!\n')):return None
    a,b=matches[0].group(1).lower(),matches[0].group(2).lower()
    middle,c=matches[1].group(1).lower(),matches[1].group(2).lower()
    if b!=middle or len({a,b,c})!=3:return None
    digest=hashlib.sha256(text.encode()).hexdigest()
    premises=[]
    for index,match in enumerate(matches):
        # Truth numbers are an explicit controller policy for user assertions,
        # never claimed to be measured confidence or independent corroboration.
        provenance=f'user-assertion:sha256:{digest}:span:{match.start()}:{match.end()};policy:f=1,c=0.9'
        premises.append(make_premise('assertion_'+str(index),provenance,
            match.group(1).lower(),match.group(2).lower(),1000,900))
    return {'version':1,'operation':'nal1-chain','task_id':'turn_'+str(revision),
            'revision':revision,'premises':premises}


class NarsCognition:
    def __init__(self,manifest_path,admission,evidence_root,*,run=run_native):
        self.manifest=json.loads(Path(manifest_path).read_bytes())
        self.admission=admission
        root=Path(evidence_root)
        if not root.is_absolute():raise ValueError('Trusted absolute evidence root required')
        root.mkdir(parents=True,exist_ok=True)
        self.evidence_root=Path(tempfile.mkdtemp(prefix='session-',dir=root))
        self.run=run;self.receipts=[]

    def __call__(self,text,history):
        snapshot=canonical({'text':text,'history':history})
        request=extract(text,len(history)//2+1)
        if request is None:return []
        response,receipt=self.run(request,manifest=self.manifest,admission=self.admission,
            evidence_directory=self.evidence_root/request['task_id'])
        if canonical({'text':text,'history':history})!=snapshot:raise ValueError('Conversation changed during inference')
        # Runtime verifies the native rows independently. Keep their full evidence
        # while giving the LLM a compact, explicitly uncertain prompt projection.
        conclusion=next(c for c in response['conclusions'] if c['rule']=='deduction')
        self.receipts.append({'snapshot_sha256':hashlib.sha256(snapshot).hexdigest(),
            'request':request,'response':response,'receipt':receipt})
        text=(f"MeTTa-NARS NAL-1 derived {conclusion['subject']} -> {conclusion['predicate']} "
              f"from the two user assertions (frequency={conclusion['frequency']:.6g}, "
              f"confidence={conclusion['confidence']:.6g}). Uncertain derived belief. "
              "Premise values f=1,c=0.9 are controller policy, not measured probabilities "
              "or verified facts. No action is authorized.")
        self.receipts[-1]['prompt_context']={'id':'nars_'+request['task_id'],'text':text}
        return [{'id':'nars_'+request['task_id'],'text':text}]
