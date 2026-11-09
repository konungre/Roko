"""Future explicitly coordinated 16MiB stdin-tar ownership gate. Default only prints plan."""
import argparse
import io
import json
import os
import re
import stat
import subprocess
import tarfile
from pathlib import Path
import probe_image
import source
import tooling

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/disk-root-capability-probe'

def fixture():
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w',format=tarfile.PAX_FORMAT) as tar:
        tar.addfile(source.tar_info('private',stat.S_IFDIR|0o750))
        payload=b'roko-root-tar-probe\n'
        tar.addfile(source.tar_info('private/fixture',stat.S_IFREG|0o640,len(payload)),io.BytesIO(payload))
        tar.addfile(source.tar_info('private/link',stat.S_IFLNK|0o777,link='fixture'))
    return data.getvalue()

def run():
    # This function intentionally is not invoked by preparation/static tests.
    tooling.verify();fd=probe_image.open_image(ROOT,create=True);report={'passed':False,'format_test_started':True}
    try:
        with tooling.descriptors('mke2fs') as (cmd,fds,env,receipt):
            result=subprocess.run(cmd+tooling.format_args(fd,'probe'),input=fixture(),capture_output=True,env=env,pass_fds=(*fds,fd),check=True,timeout=120)
        report['tooling']=receipt;report['format_output']=(result.stdout+result.stderr).decode();os.fsync(fd)
        outputs={}
        with tooling.descriptors('debugfs') as (cmd,fds,env,_):
            for path,kind,mode in [('/','directory','0755'),('/private','directory','0750'),('/private/fixture','regular','0640'),('/private/link','symlink','0777')]:
                result=subprocess.run(cmd+['-R','stat '+path,f'/proc/self/fd/{fd}'],capture_output=True,text=True,env=env,pass_fds=(*fds,fd),check=True,timeout=30)
                text=result.stdout;outputs[path]=text
                if not re.search(r'User:\s+0\s+Group:\s+0\b',text) or not re.search('Type: '+kind+r'\s+Mode:\s+'+mode+r'\b',text):
                    raise ValueError('Tar metadata not preserved: '+path)
            if 'Fast link dest: "fixture"' not in outputs['/private/link']:raise ValueError('Symlink changed')
            result=subprocess.run(cmd+['-R','cat /private/fixture',f'/proc/self/fd/{fd}'],capture_output=True,env=env,pass_fds=(*fds,fd),check=True,timeout=30)
            if result.stdout!=b'roko-root-tar-probe\n':raise ValueError('Fixture bytes differ')
        _,check=tooling.formatter.execute('e2fsck',fd)
        report.update(passed=True,metadata=outputs,fsck=check,stdin_tar_proved=True,root_guest_ownership_proved=True)
    finally:
        os.close(fd)
        with (OUT/'validation.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');a=p.parse_args()
    print(json.dumps(run() if a.run else {'format_started':False,'scope':'Explicit future 16MiB stdin-tar UID/GID/mode/symlink test; resource grant required'},indent=2))
