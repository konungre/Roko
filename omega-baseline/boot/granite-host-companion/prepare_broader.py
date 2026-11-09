#!/usr/bin/env python3
"""Freeze prior cases verbatim; no inference and no prompt optimization."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def fixtures():
    source=ROOT/'integration/granite-expanded-suite.json'
    legacy=ROOT/'boot/granite-guest/profile-host.py'
    old=json.loads(source.read_text());lookup={x['id']:x for x in old}
    nodes=[n for n in ast.walk(ast.parse(legacy.read_text())) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cases' for t in n.targets)]
    cases=ast.literal_eval(nodes[0].value)
    ready=next(x for x in cases if x['id']=='literal-ready')
    selected=[{'id':'legacy-literal-ready','prompt':ready['prompt'],'tool':'record_answer','args':{'text':ready['expected']},
               'evidence':'ready','checker':'quote','request_style':'matched-single-tool','source':str(legacy.relative_to(ROOT))}]
    for name in ['addition','multiplication','literal_copy','literal_marker','instruction_data','invoice_extraction','invoice_leading_zero']:
        original=lookup[name]
        checker='arithmetic' if name in ('addition','multiplication') else ('invoice' if original['tool']=='record_invoice' else 'quote')
        evidence={'addition':'Arithmetic: 2 + 2.','multiplication':'Arithmetic: 7 * 8.'}.get(name)
        if evidence is None:
            evidence=('Invoice '+original['args']['invoice']+'; total '+original['args']['total']+'.') if checker=='invoice' else original['args']['text']
        selected.append(dict(original,evidence=evidence,checker=checker,request_style='expanded-all-three-tools',source=str(source.relative_to(ROOT))))
    return {'status':'fixed-before-evaluation','cases':selected,'source_sha256':{str(source.relative_to(ROOT)):sha(source),str(legacy.relative_to(ROOT)):sha(legacy)},
            'direct_requests':8,'bridge_requests':8,'max_output_tokens':64,'native_input_token_cap':512,
            'historical_differences':'Expanded historical host suite used 128 output tokens, two threads and different runtime/context. Fixed prompt/system/tool text are preserved; this bounded portable candidate uses 64 output tokens, one thread, context1024, microbatch32. Bridge adds its actual existing CLI template/evidence text.',
            'known_failures_preserved':{'legacy-literal-ready':'Earlier portable Granite emitted Ready to assist! / Ready. instead of ready.',
                'invoice_extraction':'Earlier constrained/unconstrained Granite emitted invoice=Invoice A17 instead of A17.',
                'qwen':'Earlier Qwen candidate copied arithmetic expressions and returned Invoice A12 instead of A12; not substituted here.'},
            'grammar_contains_expected_answers':False,'automatic_retries':False,'external_actions':0}

if __name__=='__main__':
    result=fixtures();path=HERE/'broader-fixtures.json'
    if path.exists():raise ValueError('Never overwrite fixed evaluation cases')
    path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('cases','known_failures_preserved')},indent=2))
