#!/usr/bin/env python3
"""Two independent workspace rescue builds; no VM, device or host activation."""
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def qualify(repository,output):
 repository,output=map(lambda x:Path(x).resolve(),(repository,output));output.mkdir(mode=0o700)
 source=repository/'omega-baseline/boot';inputs={n:sha(source/n) for n in ('build.py','init.c')};builds=[]
 for label,timezone,epoch in [('first','UTC','1'),('second','Pacific/Apia','2000000000')]:
  work=output/label;boot=work/'boot';boot.mkdir(parents=True)
  for name in inputs:shutil.copyfile(source/name,boot/name)
  # Deliberately perturb filesystem timestamps, path and environment metadata.
  for name in inputs:os.utime(boot/name,(int(epoch),int(epoch)))
  env={**os.environ,'TZ':timezone,'SOURCE_DATE_EPOCH':epoch,'LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}
  p=subprocess.run([sys.executable,'-B',str(boot/'build.py'),'--minimal','--output',str(work/'out')],cwd=work,env=env,capture_output=True,text=True,timeout=60)
  (work/'stdout.log').write_text(p.stdout);(work/'stderr.log').write_text(p.stderr)
  if p.returncode:raise RuntimeError('Build failed; evidence retained: '+label)
  manifest=json.loads((work/'out/build-manifest.json').read_text())
  builds.append({'label':label,'environment':{'TZ':timezone,'SOURCE_DATE_EPOCH':epoch},'compiler':manifest['compiler'],'build_id':manifest['build_id'],'init_sha256':sha(work/'out/init'),'initramfs_sha256':sha(work/'out/roko-initramfs.cpio.gz'),'manifest':manifest})
 equal=all(builds[0][k]==builds[1][k] for k in ('compiler','build_id','init_sha256','initramfs_sha256','manifest'))
 archive=output/'first/out/roko-initramfs.cpio.gz';raw=archive.read_bytes()
 fixed_gzip_time=raw[4:8]==b'\0'*4
 fixed_entries=all(row['mtime']==0 and row['uid']==0 and row['gid']==0 for row in builds[0]['manifest']['entries'].values())
 unchanged=inputs=={n:sha(source/n) for n in inputs}
 report={'schema':'roko-local-rescue-repro-v1','passed':equal and fixed_gzip_time and fixed_entries and unchanged,'builds':builds,'source_sha256':inputs,'source_unchanged':unchanged,'equal_bytes_and_manifests':equal,'fixed_gzip_time':fixed_gzip_time,'fixed_archive_metadata':fixed_entries,'kernel_built':False,'vm_booted':False,'nixos_or_guix_system_built':False,'host_activation':False,'scope':'same-host/toolchain minimal rescue compilation under varied source paths, timestamps and environment; not hermetic cross-host reproduction'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('repository');p.add_argument('output');a=p.parse_args();r=qualify(a.repository,a.output);print(json.dumps({'passed':r['passed'],'equal_bytes':r['equal_bytes_and_manifests']}));sys.exit(0 if r['passed'] else 1)
