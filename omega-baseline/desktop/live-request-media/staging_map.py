"""Resolve/hash only. New regular-media derivative, never native execution."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORKSPACE=ROOT.parent
INSTALL='/opt/roko/desktop/live-request'
MODEL='/run/roko-guest-cognition/model'
BASE=ROOT/'recovery/guest-cognition/model-runtime-plan/component-002'

def measured(path,destination,mode):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Missing or redirected source: '+str(path))
    raw=path.read_bytes()
    return {'source':str(path),'destination':destination,'mode':mode,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def build():
    original=json.loads((BASE/'granite-portable-runtime.lock.json').read_text())
    lock=json.loads(json.dumps(original))
    lock['files'].pop('adapters/raw_transport.py')
    lock['files'].pop('granite-raw-transport.lock.json')
    for name in ('media_transport.py','runtime_select.py'):
        lock['files']['adapters/'+name]=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    lock.update(status='source-pinned-live-media-runtime-v1',
        admission_scope='Source-pinned live-media derivative; actual native and guest execution review still required',
        new_guest_runtime_tested=False,runtime_grant_required=True,
        model_transport={'kind':'readonly-regular-live-media-v1',
            'path':'/run/roko-live-media/roko/model/granite-4.0-h-tiny-Q4_K_M.gguf',
            'bytes':4230976352,'sha256':'5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd',
            'readonly_mount_required':True,'readonly_descriptor_required':True,
            'sector_padding_required':False},
        historical_runtime_lock_sha256=hashlib.sha256((BASE/'granite-portable-runtime.lock.json').read_bytes()).hexdigest())
    # This is authored source metadata, not evidence of runtime admission.
    lock_path=HERE/'granite-portable-runtime.lock.json'
    lock_path.write_text(json.dumps(lock,sort_keys=True,separators=(',',':'))+'\n')
    component=json.loads((BASE/'component.json').read_text());entries=[]
    for name,pin in sorted(component['files'].items()):
        if name in ('adapters/raw_transport.py','granite-raw-transport.lock.json'):continue
        if name=='adapters/runtime_select.py':
            path=HERE/'runtime_select.py'
        elif name=='granite-portable-runtime.lock.json':path=lock_path
        else:
            path=Path(pin['source_realpath'])
            if not path.is_file():path=WORKSPACE/'recovery-second/runtime/packages/payload'/path.relative_to(WORKSPACE)
        row=measured(path,MODEL+'/'+name,pin['mode'])
        if name not in ('adapters/runtime_select.py','granite-portable-runtime.lock.json') and (row['sha256']!=pin['sha256'] or row['bytes']!=pin['bytes']):
            raise ValueError('Recovered runtime differs: '+name)
        entries.append(row)
    entries.append(measured(HERE/'media_transport.py',MODEL+'/adapters/media_transport.py',0o444))
    for name in ('cli.py','live_controller.py','live_contract.py'):
        entries.append(measured(HERE/name,INSTALL+'/'+name,0o444))
    for name in ('state_store.py','working_state.py'):
        entries.append(measured(ROOT/'adapters'/name,INSTALL+'/'+name,0o444))
    return {'schema':'basilisk-live-media-stage-map-v1','source_only':True,
        'native_executed':False,'model_executed':False,'guest_tested':False,
        'entries':entries,'payload_bytes':sum(x['bytes'] for x in entries),
        'entry_argv':['/usr/bin/python3.13','-I','-B',INSTALL+'/cli.py'],
        'create_private_directories':[{'path':'/var/lib/roko/live-requests','mode':0o700}],
        'state_storage':'Private ephemeral tmpfs; reboot persistence is not supported by this prototype.',
        'model_transport':lock['model_transport'],'media_label':'ROKO_SHOWCASE',
        'mountpoint':'/run/roko-live-media','bootstrap_owns_media_label_discovery':True,
        'runtime_limit_seconds':1200,'ui_limit_seconds':1260,
        'activation':'Source candidate only; no native/model/guest test or execution admission implied.',
        'historical_raw_source_preserved':'desktop/live-request',
        'limits':['No raw virtio serial, loop model device or sector padding is required by this model transport.',
                  'No user-controlled model path, writable-model fallback or host regular-file fallback.',
                  'Exact fixed path, readonly mount/filesystem/descriptor, held FD and pre/post hash required.',
                  'No ECAN/MeTTa, general chat, external action or autonomy in this subset.']}

if __name__=='__main__':print(json.dumps(build(),indent=2,sort_keys=True))
