"""Serial-contract parsing only. Native execution must be bound by the VM runner."""
import json,re
def parse(data):
 lines=data.decode(errors='replace').replace('\r','').splitlines()
 rows=[]
 for line in lines:
  if line.startswith('ROKO_MANAGER_PHASE '):rows.append(json.loads(line.split(' ',1)[1]))
 if [row.get('phase') for row in rows]!=['missing-model-network-unavailable','invalid-policy','recovery']:raise ValueError('fixture phases missing or reordered')
 if lines.count('ROKO_MANAGER_FIXTURE_BEGIN')!=1 or lines.count('ROKO_MANAGER_FIXTURE_PASS')!=1 or 'ROKO_MANAGER_FIXTURE_FAIL' in lines:raise ValueError('fixture markers')
 reports=[row['report'] for row in rows]
 if [r.get('status') for r in reports]!=['unqualified','failed','unqualified']:raise ValueError('report status contract')
 if any(r.get('system_ready') is not False or r.get('execution_authorized') is not False for r in reports):raise ValueError('false readiness or authority')
 if rows[0].get('network_unavailable') is not True or 'model-not-qualified' not in reports[0].get('issues',[]):raise ValueError('missing model/network contract')
 if not reports[0].get('boot_id') or reports[0]['boot_id']!=reports[2].get('boot_id'):raise ValueError('recovery boot identity')
 uids=[int(match.group(1)) for line in lines if (match:=re.search(r'^roko-startup-report.service: User lookup succeeded: uid=(\d+) gid=\d+',line))]
 if not uids or any(uid==0 for uid in uids):raise ValueError('non-root service identity missing')
 return {'serial_contract_passed':True,'phases':rows,'observed_service_uids':uids,'scope':'serial consistency only; caller must bind runtime/image/process evidence'}
