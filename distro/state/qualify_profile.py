#!/usr/bin/env python3
"""Explicit local qualification: private profiles only, never host activation."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from facts import Fact,Stage,digest
from ledger import Ledger
from profile_switch import Profiles
from projection import latest_atom

def qualify(base,symbolic,output):
 base,symbolic,output=map(lambda p:Path(p).resolve(),(base,symbolic,output))
 output.mkdir(mode=0o700)
 env={**os.environ,'LD_LIBRARY_PATH':str(base/'root/usr/lib/x86_64-linux-gnu')}
 uri='local?store='+str(base/'direct-store')+'&state='+str(base/'direct-state')+'&log='+str(base/'direct-log')
 p=Profiles(output/'profiles',str(base/'root/usr/bin/nix'),uri,env)
 receipts=[]
 for revision in (1,2):
  raw=p.run('--option','build-users-group','','--option','sandbox','false','build','--impure','--file',str(base/f'profile-{revision}.nix'),'--no-link','--json')
  build=json.loads(raw);path=build[0]['outputs']['out']
  if (Path(path)/'share/roko-generation').read_text()!=str(revision):raise ValueError('build payload')
  before=p.current();switch=p.switch({'roko':path},before,True)
  receipts.append({'operation':'build-and-profile-switch','build':build,'switch':switch,'payload':str(revision)})
 old=receipts[0]['switch']['after']['target'];current=p.current();failures={}
 for kind in ('unauthorized','stale'):
  try:p.rollback(old,current if kind=='unauthorized' else 'stale',kind!='unauthorized')
  except (PermissionError,ValueError):failures[kind]=p.current()==current
  else:failures[kind]=False
 if not all(failures.values()):raise ValueError('failure gate')
 rollback=p.rollback(old,current,True)
 if (p.root/'active/share/roko-generation').read_text()!='1':raise ValueError('rollback payload')
 receipts.append({'operation':'rollback','receipt':rollback})
 try:p.switch({'roko':receipts[0]['build'][0]['outputs']['out']},receipts[0]['switch']['after'],True)
 except ValueError:failures['aba_replay']=True
 else:failures['aba_replay']=False
 (output/'native-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 ledger=Ledger(output/'facts.sqlite');previous='0'*64;facts=[]
 for i,r in enumerate(receipts,1):
  fact=Fact('private-profile-gate','nix',i,Stage.OBSERVED,'profile-operation-'+str(i),digest(r),previous)
  previous=ledger.append(fact,i-1);facts.append(fact)
 try:ledger.append(facts[-1],2)
 except ValueError:failures['stale_fact']=True
 else:failures['stale_fact']=False
 ledger.close();atom=latest_atom(output/'facts.sqlite','private-profile-gate','nix')
 if atom!=facts[-1].atom():raise ValueError('durable projection changed')
 (output/'facts.json').write_text(json.dumps([f.document() for f in facts],indent=2)+'\n')
 def metta(s):return 'process_metta_string('+json.dumps(s)+',_)'
 goals=["consult("+repr(str(symbolic/'petta/src/metta.pl'))+")",'assertz(working_dir('+repr(str(symbolic/'omega'))+'))','process_metta_string("!(import! &self src/utils.py)",[true])','process_metta_string("!(import! &self src/providers.metta)",[true])']
 for fact in facts:
  goals.append(metta('!(add-atom &self '+fact.atom()+')'))
  goals.append('process_metta_string('+json.dumps('!(match &self '+fact.atom()+' ok)')+',[ok])')
 goals+= ["writeln('ROKO_NATIVE_PROFILE_OMEGA_PASS')",'halt(0)']
 pl=output/'ingest.pl';pl.write_text(':- initialization(main,main).\nmain :- '+',\n'.join(goals)+'.\n')
 result=subprocess.run(['/bin/bash','-c','. "$1"; exec "$2" -q -s "$3"','profile-gate',str(symbolic/'runtime-env.sh'),str(symbolic/'swipl/bin/swipl'),str(pl)],env=os.environ.copy(),capture_output=True,text=True,timeout=60)
 (output/'ingest.stdout').write_text(result.stdout);(output/'ingest.stderr').write_text(result.stderr)
 passed=result.returncode==0 and 'ROKO_NATIVE_PROFILE_OMEGA_PASS' in result.stdout and all(failures.values())
 report={'passed':passed,'native_operations':3,'facts_reopened_and_matched':3 if passed else 0,'failure_gates':failures,'scope':'disposable Nix private-profile operations ingested into PeTTa with Omega imports','host_activation':False,'system_generation_tested':False,'runtime_returncode':result.returncode}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('base','symbolic','output'):p.add_argument(n)
 a=p.parse_args();r=qualify(a.base,a.symbolic,a.output);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
