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
def parse_model_delay(data,expected_bytes):
 lines=data.decode(errors='replace').replace('\r','').splitlines();prefix='ROKO_MODEL_DELAY_PHASE '
 rows=[json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
 if [r.get('phase') for r in rows]!=['absent-after-startup','available-after-startup','removed-again','asset-recovery'] or lines.count('ROKO_MODEL_DELAY_FIXTURE_PASS')!=1:raise ValueError('delayed model phases')
 for row in (rows[0],rows[2]):
  if row.get('system_ready') is not False:raise ValueError('absent model false readiness')
 for row in (rows[1],rows[3]):
  asset=row.get('asset',{})
  if asset.get('status')!='asset-observed-not-inference-qualified' or asset.get('bytes')!=expected_bytes or type(asset.get('writer_uid')) is not int or asset['writer_uid']==0:raise ValueError('model asset contract')
  if any(asset.get(key) is not False for key in ('inference_qualified','system_ready','execution_authorized','model_sha256_verified_in_guest')):raise ValueError('model asset false qualification')
  if row.get('read_only_mount') is not True or not type(row.get('asset_started_usec')) is int or not type(row.get('startup_exit_usec')) is int or not row['asset_started_usec']>row['startup_exit_usec']>0:raise ValueError('model ordering or read-only contract')
 return {'serial_contract_passed':True,'phases':rows,'inference_qualified':False,'scope':'delayed asset serial consistency, not native model inference'}
