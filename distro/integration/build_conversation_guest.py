#!/usr/bin/env python3
"""Extend the verified symbolic guest with a real bounded conversation test.

Creates new regular-file disks, never installs or opens a host device.
"""
import argparse,gzip,hashlib,json,lzma,os,shutil,stat,subprocess,sys,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from build_probe import baseline,FLAGS
MODEL_SHA='5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd'
WORK_UUID='726f6b6f-776f-426b-8000-000000000001'
MODEL_UUID='726f6b6f-6d6f-4465-8000-000000000001'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def build(symbolic,model,kernelroot,tools,output):
    symbolic,model,kernelroot,tools,output=map(Path,(symbolic,model,kernelroot,tools,output))
    previous=json.loads((symbolic/'manifest.json').read_text())
    if sha(symbolic/'initramfs.cpio.gz')!=previous['initramfs_sha256']:raise ValueError('Symbolic capsule changed')
    if sha(model/'model.gguf')!=MODEL_SHA:raise ValueError('Model changed')
    output.mkdir(mode=0o700);stage=output/'root'
    shutil.copytree(symbolic/'root',stage,symlinks=False)
    # Validate staged bytes against their previously measured archive inventory.
    for name,row in previous['entries'].items():
        if stat.S_ISREG(row['mode']) and sha(stage/name)!=row['sha256']:raise ValueError('Symbolic root changed: '+name)
    app=stage/'opt/roko'
    shutil.copytree(model/'portable',app/'inference',symlinks=False)
    # Resolve the trusted new inference executable's host dependencies.
    import re
    listing=subprocess.check_output(['ldd',str(model/'portable/infer')],text=True)
    if 'not found' in listing:raise ValueError('Missing inference library')
    for name in re.findall(r'(?:=>\s+)?(/\S+)\s+\(',listing):
        src=Path(name)
        if not src.is_relative_to(model):shutil.copy2(src,stage/'usr/lib/x86_64-linux-gnu'/src.name)
    shutil.copy2(HERE/'guest_conversation_driver.py',app/'guest_driver.py')
    for name in ('models','workspace'):(app/name).mkdir()
    modroot=next((kernelroot/'usr/lib/modules').iterdir())
    rows={line.split(':')[0]:line.split(':')[1].split() for line in (modroot/'modules.dep').read_text().splitlines()};order=[]
    def visit(name):
        if name in order:return
        for child in rows[name]:visit(child)
        order.append(name)
    for wanted in ('virtio_blk','crc32c_generic','ext4'):
        found=[n for n in rows if Path(n).name.split('.ko')[0]==wanted]
        if len(found)!=1:raise ValueError('Missing kernel module')
        visit(found[0])
    (stage/'modules').mkdir()
    for i,name in enumerate(order):(stage/'modules'/f'{i}.ko').write_bytes(lzma.decompress((modroot/name).read_bytes()))
    workspace=output/'workspace-files';(workspace/'components').mkdir(parents=True)
    shutil.copytree(HERE.parents[1]/'components/conversation',workspace/'components/conversation',ignore=shutil.ignore_patterns('__pycache__','tests'))
    (workspace/'omega-baseline/scripts').mkdir(parents=True);shutil.copy2(app/'no-network.py',workspace/'omega-baseline/scripts/no-network.py')
    for p in workspace.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o444)
    profile={'kind':'roko-fresh-host-v1','python':'/opt/roko/python/bin/python3.12','swipl':'/opt/roko/swipl/bin/swipl','petta':'/opt/roko/petta','omega':'/opt/roko/omega','infer':'/opt/roko/inference/infer','model':'/opt/roko/models/model.gguf','runtime_env':{'PYTHONHOME':'/opt/roko/python','PYTHONPATH':'/opt/roko/site-packages:/opt/roko/omega/src','LD_LIBRARY_PATH':'/usr/lib/x86_64-linux-gnu:/opt/roko/python/lib:/opt/roko/swipl/lib/swipl/lib/x86_64-linux','SWI_HOME_DIR':'/opt/roko/swipl/lib/swipl','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'},'qualification':'New guest binding; awaiting real test','files':{}}
    for p in app.rglob('*'):
        if p.is_file():profile['files']['/'+str(p.relative_to(stage))]=sha(p)
    for p in workspace.rglob('*'):
        if p.is_file():profile['files']['/opt/roko/workspace/'+str(p.relative_to(workspace))]=sha(p)
    profile['files']['/opt/roko/models/model.gguf']=MODEL_SHA
    (workspace/'profile.json').write_text(json.dumps(profile,indent=2)+'\n');(workspace/'profile.json').chmod(0o444)
    modelfiles=output/'model-files';modelfiles.mkdir();os.link(model/'model.gguf',modelfiles/'model.gguf');(modelfiles/'model.gguf').chmod(0o444)
    env={**os.environ,'LD_LIBRARY_PATH':str(tools/'usr/lib/x86_64-linux-gnu'),'MKE2FS_CONFIG':str(tools/'etc/mke2fs.conf')}
    for name,size,files,ident in [('workspace',8*1024**3,workspace,WORK_UUID),('model',5*1024**3,modelfiles,MODEL_UUID)]:
        disk=output/(name+'.img')
        with disk.open('xb') as f:f.truncate(size)
        disk.chmod(0o600)
        subprocess.run([str(tools/'usr/sbin/mke2fs'),'-t','ext4','-F','-q','-m','0','-U',ident,'-d',str(files),str(disk)],env=env,check=True,timeout=120)
    source=(HERE/'symbolic_init.c').read_text()
    setup='''
static int mount_disk(const char *dev,const char *target,const unsigned char *id){
 long fd=-1;struct {long sec,nsec;} pause={0,100000000};
 for(int i=0;i<200 && fd<0;i++){fd=sc(2,(long)dev,0,0,0,0,0);if(fd<0)sc(35,(long)&pause,0,0,0,0,0);}
 if(fd<0)return -1;unsigned char magic[2],actual[16];
 if(sc(17,fd,(long)magic,2,1080,0,0)!=2||sc(17,fd,(long)actual,16,1128,0,0)!=16)return -1;
 sc(3,fd,0,0,0,0,0);if(magic[0]!=0x53||magic[1]!=0xef)return -1;
 for(int i=0;i<16;i++)if(actual[i]!=id[i])return -1;
 return sc(165,(long)dev,(long)target,(long)"ext4",15,0,0);
}
'''
    source=source.replace('__attribute__((noreturn)) void _start',setup+'\n__attribute__((noreturn)) void _start')
    before=' if(sc(165,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",0,0,0)<0){say(1,"ROKO_MODEL_GUEST_FAILED devtmpfs\\n");stop();}\n'
    for i in range(len(order)):before+=f' {{long fd=sc(2,(long)"/modules/{i}.ko",0,0,0,0,0);if(fd<0||sc(313,fd,(long)"",0,0,0,0)<0){{say(1,"ROKO_MODEL_GUEST_FAILED module-{i}\\n");stop();}}sc(3,fd,0,0,0,0,0);}}\n'
    for dev,target,ident in [('vda','workspace',WORK_UUID),('vdb','models',MODEL_UUID)]:
        values=','.join(str(x) for x in uuid.UUID(ident).bytes)
        before+=f' {{unsigned char id[16]={{{values}}};if(mount_disk("/dev/{dev}","/opt/roko/{target}",id)<0){{say(1,"ROKO_MODEL_GUEST_FAILED mount-{target}\\n");stop();}}}}\n'
    source=source.replace(' long child=sc(57,',before+' long child=sc(57,')
    source=source.replace('"/opt/roko/swipl/bin/swipl","-q","-s","/opt/roko/probe.pl"','"/opt/roko/python/bin/python3.12","/opt/roko/guest_driver.py"')
    (output/'init.c').write_text(source);identity=hashlib.sha256(source.encode()+(workspace/'profile.json').read_bytes()).hexdigest()
    subprocess.run(['gcc',*FLAGS,'-DROKO_BUILD_ID="'+identity+'"',str(output/'init.c'),'-o',str(output/'init')],check=True,timeout=60)
    shutil.copy2(output/'init',stage/'init')
    records=[]
    for i,p in enumerate(sorted(stage.rglob('*')),1):
        name=str(p.relative_to(stage));mode=(stat.S_IFDIR|0o755) if p.is_dir() else (stat.S_IFREG|(0o555 if p.stat().st_mode&0o111 else 0o444))
        if name=='tmp':mode=stat.S_IFDIR|0o1777
        if name=='home/roko':mode=stat.S_IFDIR|0o700
        record=baseline.entry(name,b'' if p.is_dir() else p.read_bytes(),mode,i)
        if name=='home/roko':record=record[:22]+b'000003e8000003e8'+record[38:]
        records.append(record)
    records.append(baseline.entry('dev/console',b'',stat.S_IFCHR|0o600,len(records)+1,5,1))
    records.append(baseline.entry('TRAILER!!!',b'',0,len(records)+1));raw=b''.join(records);raw+=b'\0'*(-len(raw)%512)
    baseline.inspect(raw);(output/'initramfs.cpio.gz').write_bytes(gzip.compress(raw,compresslevel=6,mtime=0))
    report={'schema':'roko-model-guest-build-v1','build_id':identity,'initramfs_sha256':sha(output/'initramfs.cpio.gz'),'workspace_sha256':sha(output/'workspace.img'),'model_disk_sha256':sha(output/'model.img'),'model_sha256':MODEL_SHA,'kernel_modules':order,'source_sha256':sha(output/'init.c'),'profile_sha256':sha(workspace/'profile.json'),'guest_tested':False}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('symbolic','model','kernelroot','tools','output'):p.add_argument(n,type=Path)
    a=p.parse_args();print(json.dumps(build(a.symbolic,a.model,a.kernelroot,a.tools,a.output),indent=2))
