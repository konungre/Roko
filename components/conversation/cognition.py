"""A narrow, explicit user-assertion bridge into actual NAL-1 inference.

It does not infer unstated facts, parse arbitrary prose as code, or learn a world.
The accepted grammar is intentionally small; other conversation remains ordinary.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.nars_hyperon.source.contract import canonical
from components.nars_hyperon.source.runtime import run_native
if __package__:
    from .assertions import extract,parse_assertions
else:
    from assertions import extract,parse_assertions


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
        parsed=parse_assertions(text,len(history)//2+1)
        if parsed is None:return []
        request=parsed.request
        response,receipt=self.run(request,manifest=self.manifest,admission=self.admission,
            evidence_directory=self.evidence_root/request['task_id'])
        if canonical({'text':text,'history':history})!=snapshot:raise ValueError('Conversation changed during inference')
        # Runtime verifies the native rows independently. Keep their full evidence
        # while giving the LLM a compact, explicitly uncertain prompt projection.
        conclusion=next(c for c in response['conclusions'] if c['rule']=='deduction')
        self.receipts.append({'snapshot_sha256':hashlib.sha256(snapshot).hexdigest(),
            'request':request,'response':response,'receipt':receipt})
        self.receipts[-1]['term_labels']=parsed.labels
        text=(f"MeTTa-NARS NAL-1 derived {parsed.labels[conclusion['subject']]} -> {parsed.labels[conclusion['predicate']]} "
              f"from the two {parsed.mode} premises (frequency={conclusion['frequency']:.6g}, "
              f"confidence={conclusion['confidence']:.6g}). Uncertain derived belief. "
              "Premise values f=1,c=0.9 are controller policy, not measured probabilities "
              "or verified facts. No action is authorized.")
        self.receipts[-1]['prompt_context']={'id':'nars_'+request['task_id'],'text':text}
        return [{'id':'nars_'+request['task_id'],'text':text}]
