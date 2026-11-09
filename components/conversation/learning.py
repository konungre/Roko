"""Typed optional v2 learning tasks; runtime paths are trusted profile data only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from cognition import write_record

SOURCE=Path(__file__).resolve().parent
ROOT=SOURCE.parents[1]
COMPONENTS={'metamo':ROOT/'components/metamo_host/source/contract.py',
            'airis':ROOT/'components/airis_host/source/contract.py',
            'nace':ROOT/'components/nace/source/contract.py'}
_CONTRACTS={}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def contract(name):
    if name not in _CONTRACTS:
        spec=importlib.util.spec_from_file_location('_roko_learning_'+name,COMPONENTS[name])
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        spec.loader.exec_module(module);_CONTRACTS[name]=module
    return _CONTRACTS[name]


def validate_tasks(tasks):
    if type(tasks) is not list or len(tasks)>3:raise ValueError('At most three explicit cognitive tasks')
    if len(canonical(tasks))>10000:raise ValueError('Cognitive task byte cap')
    seen=set();result=[]
    for row in tasks:
        if type(row) is not dict or set(row)!={'component','request'}:raise ValueError('Cognitive task schema')
        name=row['component']
        if type(name) is not str or name not in COMPONENTS or name in seen:raise ValueError('Unknown or duplicate cognitive component')
        seen.add(name);module=contract(name)
        if name=='nace':module.parse_request(row['request']);request=json.loads(canonical(row['request']))
        else:request=module.parse_request(canonical(row['request']))
        result.append({'component':name,'request':request})
    return result


def observation(name,response):
    if name=='metamo':
        value={'selected_proposal_id':response['selected_proposal_id'],'scores':response['scores']}
    elif name=='airis':
        values=response['predictions']
        return ('AIRIS native learned scalar predictions at meter='+str(response['query'])+
            ': step='+str(values['learned']['step'])+', hold='+str(values['learned']['hold'])+
            '. Empty knowledge: step='+str(values['empty']['step'])+', hold='+str(values['empty']['hold'])+
            '. Restored knowledge: step='+str(values['restored']['step'])+', hold='+str(values['restored']['hold'])+
            '. These are hypothetical meter values, not counts of actions. No action authorized.')
    else:
        value={'selected_rules':response['selected_rules'],'prediction':response['prediction']}
    text=name.upper()+' native bounded result: '+canonical(value).decode()+'. Advisory hypothetical data; no action executed or authorized.'
    if len(text)>500:
        # Fixed information projection; full native result stays in the receipt.
        if name=='metamo':value={'selected_proposal_id':response['selected_proposal_id']}
        elif name=='nace':value={'predicted_values':response['prediction']['values'],'score_kind':response['prediction']['score_kind']}
        text=name.upper()+' native bounded result: '+canonical(value).decode()+'. Advisory hypothetical data; full details in native receipt. No action authorized.'
    if len(text)>500:raise ValueError('Cognitive projection cap')
    return text


class LearningComponents:
    def __init__(self,profile):
        self.profile=profile;self.receipts=[]
        config=profile['learning_components']
        root=Path(config['evidence_root']);root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root=Path(tempfile.mkdtemp(prefix='learning-',dir=root))

    def run_turn(self,tasks,text,history,binding):
        tasks=validate_tasks(tasks)
        if type(binding) is not dict or set(binding)!={'session_id','request_id','revision'}:
            raise ValueError('Claimed durable binding required')
        snapshot=canonical({'text':text,'history':history,'tasks':tasks,'binding':binding})
        key=hashlib.sha256(snapshot).hexdigest();observations=[];results=[]
        for row in tasks:
            name=row['component'];config=self.profile['learning_components']['components'][name]
            directory=self.root/(name+'-'+key+'-'+uuid.uuid4().hex);directory.mkdir(mode=0o700)
            write_record(directory/'turn-start.json',{'binding':binding,'snapshot_sha256':key,'task':row})
            command=[self.profile['python'],'-B',str(SOURCE/'fresh_supervise.py'),
                '--parent-pid',str(os.getpid()),'--parent-start',Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19],
                '--seconds','30','--',self.profile['python'],'-I','-B',str(SOURCE/'learning_exec.py'),
                name,config['manifest'],config['sha256'],str(directory/'native'),
                self.profile['learning_components']['guard_manifest'],self.profile['learning_components']['guard_admission']]
            proc=None;out=b'';err=b'';failure=None
            try:
                proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},start_new_session=True)
                out,err=proc.communicate(canonical(row['request']),timeout=40)
                if proc.returncode or len(out)>65536 or len(err)>65536 or b'descendants_cleaned=1' not in err:
                    raise RuntimeError('Component execution/finalization failed')
                packet=json.loads(out)
                if packet['component']!=name or packet['request_sha256']!=digest(row['request']) or packet['receipt']['status']!='passed':
                    raise ValueError('Native component identity/result mismatch')
                if canonical({'text':text,'history':history,'tasks':tasks,'binding':binding})!=snapshot:
                    raise ValueError('Cognitive turn changed during execution')
                observed={'id':name+'_'+key,'text':observation(name,packet['response'])}
            except BaseException as exc:
                failure=exc
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:out,err=proc.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill();out,err=proc.communicate(timeout=3)
            record={'component':name,'binding':binding,'snapshot_sha256':key,'request':row['request'],
                'status':'passed' if failure is None else 'failed','stdout':out.decode('utf-8',errors='replace'),
                'stderr':err.decode('utf-8',errors='replace'),'executed_actions':0,
                'evidence_directory':str(directory),'error':None if failure is None else repr(failure)}
            if failure is None:record.update(response=packet['response'],prompt_context=observed)
            write_record(directory/'receipt.json',record);self.receipts.append(record)
            if failure is not None:raise failure
            observations.append(observed)
            results.append({'component':name,'observation_id':observed['id'],'result':packet['response']})
        return {'observations':observations,'results':results}


def validate_profile(profile):
    config=profile['learning_components']
    if type(config) is not dict or set(config)!={'components','evidence_root','guard_manifest','guard_admission'}:
        raise ValueError('Learning profile schema')
    if not Path(config['evidence_root']).is_absolute():raise ValueError('Absolute learning evidence root required')
    if profile['files'].get(config['guard_manifest'])!=config['guard_admission']:
        raise ValueError('Learning closure guard must be pinned')
    if type(config['components']) is not dict or set(config['components'])!=set(COMPONENTS):
        raise ValueError('Exact learning component configuration required')
    for name,item in config['components'].items():
        if type(item) is not dict or set(item)!={'manifest','sha256'}:raise ValueError('Component profile schema')
        if profile['files'].get(item['manifest'])!=item['sha256']:raise ValueError('Component manifest must be pinned')
        manifest=json.loads(Path(item['manifest']).read_bytes())
        for path,sha in manifest['files'].items():
            if profile['files'].get(path)!=sha:raise ValueError('Component closure missing from profile')
    for path in COMPONENTS.values():
        if str(path) not in profile['files']:raise ValueError('Unpinned component contract')
