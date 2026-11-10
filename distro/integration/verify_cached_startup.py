"""Cached source/receipt consistency only; never replay or grant readiness."""
import argparse,hashlib,json,re
from pathlib import Path
COSMIC={'offline-startup.nix','cosmic-session-ordering.nix','cosmic_session_report.py'}
NETWORK={'session-network-policy.nix','offline-startup.nix'}
def verify(repository,cosmic,network):
 repository=Path(repository);seen={}
 for receipt,names in ((cosmic,COSMIC),(network,NETWORK)):
  if not isinstance(receipt,dict) or receipt.get('passed') is not True or set(receipt.get('source_hashes',{}))!=names:raise ValueError('expected successful narrow receipt required')
  for name,expected in receipt['source_hashes'].items():
   if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('source digest')
   actual=hashlib.sha256((repository/'distro/nix'/name).read_bytes()).hexdigest()
   if actual!=expected or (name in seen and seen[name]!=expected):raise ValueError('cached source changed: '+name)
   seen[name]=actual
 if network.get('nixpkgs_pin')!=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text()):raise ValueError('source pin changed')
 fragment=cosmic.get('session_fragment',{})
 if fragment.get('wantedBy')!=['cosmic-session.target'] or fragment.get('after')!=['cosmic-session.target'] or fragment.get('partOf')!=['cosmic-session.target'] or fragment.get('unitConfig',{}).get('DefaultDependencies') is not False or fragment.get('serviceConfig',{}).get('Restart')!='no':raise ValueError('unexpected cached session ordering')
 if any(fragment.get(key,[]) for key in ('requires','requisite','wants','bindsTo','before')) or set(fragment.get('unitConfig',{}))!={'DefaultDependencies'}:raise ValueError('unexpected diagnostic dependency or failure hook')
 if any(key in fragment.get('serviceConfig',{}) for key in ('ExecStartPre','ExecStartPost','ExecStopPost')):raise ValueError('unexpected cached execution hook')
 rows=network.get('cases',[])
 if not isinstance(rows,list) or len(rows)!=4 or {r.get('case') for r in rows}!={'offline','managed','managed-user-disables-discovery','offline-conflicting-force'} or any(r.get('passed') is not True for r in rows):raise ValueError('network cases')
 for row in rows:
  if row['case']=='offline-conflicting-force':
   if row.get('returncode')==0 or row.get('evaluation') is not None:raise ValueError('missing force-conflict rejection')
   continue
  value=row.get('evaluation',{});disabled=row['case']!='managed'
  if row.get('returncode')!=0 or value.get('services',{}).get('avahi',{}).get('enable') is not (not disabled) or value.get('services',{}).get('geoclue2',{}).get('enable') is not (not disabled):raise ValueError('cached discovery policy mismatch')
 return {'cached_fragment_source_hashes_match':True,'matching_source_files':sorted(seen),'pin_document_matches':True,'receipt_semantics_consistent':True,'native_evidence_authenticated':False,'commands_replayed':False,'full_nixos_evaluated':False,'runtime_dependencies_verified':False,'image_ready':False,'execution_authorized':False,'unbound_critical_inputs':['system-eval.nix','live-image-eval.nix','startup_report.py','memory_budget.py','complete upstream module/package closure','runtime kernel/user-session state'],'scope':'narrow cached file correspondence and self-report consistency only; not current full configuration evaluation'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('cosmic_receipt');p.add_argument('network_receipt');a=p.parse_args();print(json.dumps(verify(a.repository,json.loads(Path(a.cosmic_receipt).read_text()),json.loads(Path(a.network_receipt).read_text())),indent=2))
