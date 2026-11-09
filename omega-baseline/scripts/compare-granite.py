#!/usr/bin/env python3
"""Compare two runs of the same authored fixtures; never infer general quality."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
reports={m:json.loads((ROOT/f'results/granite-{m}-evaluation.json').read_text()) for m in ('unconstrained','constrained')}
if [r['id'] for r in reports['unconstrained']['results']] != [r['id'] for r in reports['constrained']['results']]:
 raise SystemExit('Different case sets cannot be paired')
out={'interpretation':'GBNF enforces syntax, not correctness. Small authored suite, shared CPU host; not a general benchmark. No actions executed.','runs':{},'changes':[]}
for mode,report in reports.items():
 rows=report['results']
 out['runs'][mode]={k:report[k] for k in ('cases','format_passed','accuracy_passed','elapsed_seconds','peak_native_rss_kib','median_request_seconds','median_decode_tokens_per_second')}
 out['runs'][mode]['original_12']={'format':sum(r['format_valid'] for r in rows[:12]),'exact':sum(r['exact_correct'] for r in rows[:12])}
 out['runs'][mode]['added_6']={'format':sum(r['format_valid'] for r in rows[12:]),'exact':sum(r['exact_correct'] for r in rows[12:])}
for a,b in zip(reports['unconstrained']['results'],reports['constrained']['results']):
 if (a['format_valid'],a['exact_correct'],a['calls']) != (b['format_valid'],b['exact_correct'],b['calls']):
  out['changes'].append({'id':a['id'],'unconstrained':{k:a[k] for k in ('format_valid','exact_correct','calls')},'constrained':{k:b[k] for k in ('format_valid','exact_correct','calls')}})
(ROOT/'results/granite-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
