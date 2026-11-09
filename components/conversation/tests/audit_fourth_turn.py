"""Audit captured real fourth-turn and fifth-turn admission evidence."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory
replies=[json.loads(x) for x in (root/'stdout.txt').read_text().splitlines()]
native=next(json.loads(x.split(' ',1)[1]) for x in (root/'stderr.txt').read_text().splitlines() if x.startswith('ROKO_FRESH_CONVERSATION '))
checks={'fourth_completed':replies[0].get('status')=='completed' and replies[0]['revision']==4,
        'recall':all(x in replies[0].get('text','').lower() for x in ('fox','robin')),
        'fifth_rejected':replies[1].get('code')=='history_limit',
        'complete_history_retained':replies[2]['revision']==4 and len(replies[2]['history'])==8 and replies[2]['pending'] is None,
        'only_one_model_call':len(native['native_calls'])==1,
        'model_verified':native['native_calls'][0].get('model_verified_before_history_commit') is True,
        'native_mork_six_messages':len(native['mork_receipts'])==1 and native['mork_receipts'][0]['indexed_messages']==6,
        'two_observations_retained':len(native['cognitive_history'])==2 and native['cognitive_receipts']==[]}
r={'passed':all(checks.values()),'checks':checks,'reply':replies[0],'executed_actions':0}
(root/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 1)
