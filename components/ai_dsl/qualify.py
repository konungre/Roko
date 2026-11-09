"""Run real bounded upstream composition cases; no service invocation occurs."""
import argparse
import json
from pathlib import Path
import time
from gateway import prepare,run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--guard-manifest',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    profile=prepare(args.guard_manifest,args.output/'cases')
    (args.output/'profile.json').write_text(json.dumps(profile,sort_keys=True)+'\n')
    cases=[('speech_to_text',0,1,0),('bytes_to_text',1,0,0),('bytes_to_text',2,1,0),
           ('speech_emotion',3,0,1),('speech_emotion',4,1,1),('speech_emotion',4,1,1)]
    rows=[];started=time.monotonic()
    for goal,depth,accepted,rejected in cases:
        result,receipt=run({'version':1,'goal':goal,'depth':depth},profile)
        if len(result['accepted'])!=accepted or len(result['rejected'])!=rejected:
            raise ValueError('Native proof count differs from independent fixture expectation')
        if goal=='speech_emotion' and accepted:
            if result['accepted'][0]['pipeline']!=['speech2text-en.s2t','speech2text-en.Text.text','text-emotions.MkInput','text-emotions.recognize']:
                raise ValueError('Unexpected admitted speech/emotion pipeline')
        rows.append({'request':receipt['request'],'result':result,'evidence_directory':receipt['evidence_directory']})
    if rows[-1]['result']!=rows[-2]['result']:
        raise ValueError('Fresh native process reset differs')
    summary={'status':'passed','cases':rows,'seconds':time.monotonic()-started,
             'executed_services':0,'executed_actions':0,
             'scope':'Actual upstream AI-DSL type-composition search; no ASR or emotion recognition executed'}
    (args.output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'status':summary['status'],'cases':len(rows),'seconds':summary['seconds'],'executed_services':0}))


if __name__=='__main__':main()
