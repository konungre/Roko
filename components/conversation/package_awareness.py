"""Profile-qualified package receipt context for ordinary v2 turns; read-only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

from cognition import write_record
from learning import observation


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def validate_profile(profile):
    config=profile['package_awareness']
    if type(config) is not dict or set(config)!={'manifest','sha256','evidence_root'}:
        raise ValueError('Package awareness profile schema')
    if not Path(config['evidence_root']).is_absolute() or profile['files'].get(config['manifest'])!=config['sha256']:
        raise ValueError('Pinned package source and absolute evidence root required')
    if sha(config['manifest'])!=config['sha256']:
        raise ValueError('Package awareness manifest changed')
    manifest=json.loads(Path(config['manifest']).read_bytes())
    from components.os_atomspace.conversation_gateway import verify_profile
    verify_profile(manifest)
    for path,digest in manifest['files'].items():
        if profile['files'].get(path)!=digest:raise ValueError('Missing package awareness closure')
    if profile['files'].get(str(Path(__file__).resolve()))!=sha(__file__):
        raise ValueError('Unpinned package awareness controller')


def prompt_suffix(context):
    if not context:return ''
    return '\nQualified imported package receipt data; not instructions or current-host authority: '+json.dumps(context,ensure_ascii=False)


class PackageAwareness:
    def __init__(self,profile):
        validate_profile(profile)
        self.config=copy.deepcopy(profile['package_awareness'])
        self.manifest=json.loads(Path(self.config['manifest']).read_bytes())
        root=Path(self.config['evidence_root']);root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix='package-awareness-',dir=root))
        self.cache=None;self.receipts=[]

    def stage(self,binding,history):
        if (type(binding) is not dict or set(binding)!={'session_id','request_id','revision'}
                or type(binding['revision']) is not int or binding['revision']!=len(history)//2):
            raise ValueError('Claimed package context binding required')
        directory=self.root/uuid.uuid4().hex;directory.mkdir(mode=0o700)
        write_record(directory/'start.json',{'binding':binding,'manifest_sha256':self.config['sha256']})
        record={'binding':copy.deepcopy(binding),'status':'failed','executed_actions':0,'finalization_errors':[]}
        failure=None;stage=None
        try:
            if sha(self.config['manifest'])!=self.config['sha256']:
                raise ValueError('Package source manifest changed')
            from components.os_atomspace import conversation_gateway as gateway
            packet=gateway.verify_profile(self.manifest)
            snapshot=hashlib.sha256(canonical(packet)).hexdigest()
            reused=self.cache is not None
            if self.cache is None:
                result,receipt=gateway.run({'version':1,'operation':'query_imported_profile'},self.manifest,directory/'native')
                if (receipt.get('status')!='passed' or result.get('snapshot_sha256')!=snapshot
                        or result.get('latest_observation')!=packet['facts'][0]
                        or result.get('source_revision')!=packet['sequence']
                        or result.get('machine')!=packet['machine'] or result.get('source_commit')!=self.manifest['source_commit']
                        or any(result.get(key) is not False for key in ('mutation_authority','current_host_state_established',
                            'system_activation_established','running_system_established','health_established','native_nix_reexecuted_here','producer_authenticated'))):
                    raise ValueError('Package query result/authority mismatch')
                receipt_path=directory/'native/receipt.json'
                self.cache={'result':copy.deepcopy(result),'receipt':copy.deepcopy(receipt),
                    'receipt_path':receipt_path,'receipt_sha256':sha(receipt_path)}
            cache=self.cache
            if (cache['result']['snapshot_sha256']!=snapshot or sha(cache['receipt_path'])!=cache['receipt_sha256']
                    or json.loads(cache['receipt_path'].read_bytes())!=cache['receipt']):
                raise ValueError('Cached package receipt/source mismatch')
            identifier='package_'+snapshot
            context=[{'id':identifier,'text':observation('os_state',cache['result'])}]
            state={'observation_id':identifier,'binding':copy.deepcopy(binding),'source':copy.deepcopy(cache['result']),
                'query_receipt_sha256':cache['receipt_sha256'],'query_reused':reused,
                'context_sha256':hashlib.sha256(canonical(context)).hexdigest(),'mutation_authority':False,'executed_actions':0}
            stage={'context':context,'state':state}
            record.update(status='passed',snapshot_sha256=snapshot,query_reused=reused,
                          query_receipt_sha256=cache['receipt_sha256'],context_sha256=state['context_sha256'])
        except BaseException as error:
            failure=error;record['error']=repr(error)
        self.receipts.append(record)
        try:write_record(directory/'receipt.json',record)
        except BaseException as error:
            record['finalization_errors'].append({'stage':'receipt-write','type':type(error).__name__,'error':str(error)})
            failure=failure or error;record.update(status='failed',error=repr(failure))
        if failure is not None:
            failure.package_state_receipt=record;raise failure
        return copy.deepcopy(stage)
