#!/usr/bin/env python3
import datetime,hashlib,json,pathlib,subprocess,shutil,re
S=pathlib.Path(__file__).resolve().parent;R=S.parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();T=R/'build-src/cosmic-comp-stage/target/debug';(S/'artifacts/bin').mkdir(parents=True,exist_ok=True)
for component,binary,src in [('files','cosmic-files',R/'build-src/cosmic-desktop-stage/sources/cosmic-files'),('files-applet','cosmic-files-applet',R/'build-src/cosmic-desktop-stage/sources/cosmic-files'),('portal','xdg-desktop-portal-cosmic',S/'sources/xdg-desktop-portal-cosmic')]:
 if shutil.disk_usage(S).free<4*1024**3:raise RuntimeError('Less than4GiB free; halt before next component')
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();log=S/'logs'/f'{component}-build.log';print('START',component,start,flush=True)
 with log.open('w') as f:result=subprocess.run(['bash',str(S/'build-one.sh'),component,'--build'],stdout=f,stderr=subprocess.STDOUT)
 record={'component':component,'binary':binary,'started_utc':start,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':result.returncode,'source_commit':subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip(),'cargo_lock_sha256':sha(src/'Cargo.lock'),'build_recipe_sha256':sha(S/'build-one.sh'),'command':(S/'logs'/f'{component}-build-command.txt').read_text(),'log_sha256':sha(log),'generic_cpu':'x86-64','jobs':1,'offline':True,'network_sockets_denied':True,'guest_tested':False}
 if result.returncode==0:
  dest=S/'artifacts/bin'/binary;shutil.copy2(T/binary,dest);elf=subprocess.check_output(['readelf','-d',str(dest)],text=True);record['artifact']={'path':str(dest.relative_to(R)),'bytes':dest.stat().st_size,'sha256':sha(dest),'needed':re.findall(r'\(NEEDED\).*\[([^]]+)\]',elf),'rpath_or_runpath':bool(re.search(r'\((RPATH|RUNPATH)\)',elf))};assert not record['artifact']['rpath_or_runpath']
 (S/'artifacts'/f'{component}.json').write_text(json.dumps(record,indent=2)+'\n');print('FINISH',component,result.returncode,record.get('artifact'),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
