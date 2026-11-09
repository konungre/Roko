"""Explain optional receipt-data limitations; controls/runtime remain mandatory."""
import copy
import hashlib
import json
from pathlib import Path
import time
import uuid

from package_awareness import PackageAwareness,canonical,sha
from cognition import write_record


def validate_status_profile(profile):
    config=profile['package_awareness']
    required={'manifest','sha256','evidence_root','receipt_policy','qualified_at_ns','max_admission_age_seconds'}
    if type(config) is not dict or set(config)!=required or config['receipt_policy']!='explain_v1':
        raise ValueError('Package evidence status policy schema')
    if (type(config['qualified_at_ns']) is not int or config['qualified_at_ns']<0
            or type(config['max_admission_age_seconds']) is not int or not 1<=config['max_admission_age_seconds']<=31536000):
        raise ValueError('Explicit bounded admission time policy required')
    if (not Path(config['evidence_root']).is_absolute() or profile['files'].get(config['manifest'])!=config['sha256']
            or sha(config['manifest'])!=config['sha256']):
        raise ValueError('Pinned status manifest/private evidence root required')
    manifest=json.loads(Path(config['manifest']).read_bytes())
    from components.os_atomspace.conversation_gateway import verify_runtime
    verify_runtime(manifest)
    data_paths={manifest['facts_path'],manifest['receipts_path']}
    for path,digest in manifest['files'].items():
        if path in data_paths:
            if path in profile['files']:raise ValueError('Optional source data is also mandatory in base profile')
        elif profile['files'].get(path)!=digest:raise ValueError('Missing status runtime closure')
    for path in (Path(__file__).resolve(),Path(__file__).resolve().with_name('package_awareness.py')):
        if profile['files'].get(str(path))!=sha(path):raise ValueError('Unpinned package status controller')


class ReceiptStatusAwareness(PackageAwareness):
    def classify(self):
        if sha(self.config['manifest'])!=self.config['sha256']:
            raise ValueError('Package control manifest changed')
        from components.os_atomspace import conversation_gateway as gateway
        gateway.verify_runtime(self.manifest)
        now=time.time_ns();qualified=self.config['qualified_at_ns']
        admission=('clock_unverifiable' if now<qualified else 'expired'
            if now-qualified>self.config['max_admission_age_seconds']*1000000000 else 'valid')
        availability='available';actual={};raw={}
        for label,key,limit in (('facts','facts_path',16384),('receipts','receipts_path',32768)):
            try:
                raw[label]=gateway.read_source(self.manifest[key],limit)
                actual[label]=hashlib.sha256(raw[label]).hexdigest()
            except FileNotFoundError:availability='missing';break
            except PermissionError:availability='inaccessible';break
            except OSError:availability='unreadable';break
            except ValueError:availability='invalid';break
            if actual[label]!=self.manifest['files'][self.manifest[key]]:
                availability='changed';break
        if availability=='available':
            try:gateway.parse_source(self.manifest,raw['facts'],raw['receipts'])
            except (ValueError,UnicodeError):availability='invalid'
            except FileNotFoundError:availability='missing'
            except PermissionError:availability='inaccessible'
            except OSError:availability='unreadable'
        if self.cache is not None:
            if (sha(self.cache['receipt_path'])!=self.cache['receipt_sha256']
                    or json.loads(self.cache['receipt_path'].read_bytes())!=self.cache['receipt']):
                raise ValueError('Cached package query proof changed')
        status=('source_'+availability if availability!='available' else
                'admission_'+admission if admission!='valid' else 'available_freshness_unknown')
        return {'evidence_status':status,'availability':availability,'admission_status':admission,
            'evidence_checked_at_ns':now,'qualified_at_ns':qualified,
            'max_admission_age_seconds':self.config['max_admission_age_seconds'],
            'source_observation_time_known':False,'actual_source_digests':actual,
            'expected_source_digests':{label:self.manifest['files'][self.manifest[key]] for label,key in
                                      (('facts','facts_path'),('receipts','receipts_path'))}}

    def stage(self,binding,history):
        if (type(binding) is not dict or set(binding)!={'session_id','request_id','revision'}
                or type(binding['revision']) is not int or binding['revision']!=len(history)//2):
            raise ValueError('Claimed status context binding required')
        directory=self.root/uuid.uuid4().hex;directory.mkdir(mode=0o700)
        write_record(directory/'start.json',{'binding':binding,'receipt_policy':'explain_v1','manifest_sha256':self.config['sha256']})
        record={'binding':copy.deepcopy(binding),'stage_kind':'evidence_status','status':'failed',
                'executed_actions':0,'finalization_errors':[]};failure=None;stage=None
        try:
            status=self.classify();active=None
            if status['evidence_status']=='available_freshness_unknown':
                try:active=super().stage(binding,history)
                except Exception:
                    # Only independently observed data loss/expiry can become a
                    # status answer. Runtime/control/proof errors still raise.
                    status=self.classify()
                    if status['evidence_status']=='available_freshness_unknown':raise
                else:status=self.classify()
            admitted=active is not None and status['evidence_status']=='available_freshness_unknown'
            if admitted:
                source=active['state']['source']
                text=('Imported package receipt: machine='+source['machine']+', source revision='+str(source['source_revision'])+
                    '. Source observation time is unknown. Admission was valid at the evidence check; this does not prove source freshness. '
                    'No current-host, running-system or health state is established. No mutation authority.')
            else:
                source=None
                reasons={'source_missing':'receipt data is missing','source_inaccessible':'receipt data is inaccessible',
                    'source_unreadable':'receipt data cannot be read','source_changed':'receipt bytes changed from the qualified version',
                    'source_invalid':'receipt data does not match the supported schema',
                    'admission_expired':'the local admission window expired; this is not the source observation time',
                    'admission_clock_unverifiable':'the local admission clock cannot be verified'}
                text=('No package receipt is admitted: '+reasons[status['evidence_status']]+'. '
                    'Missing or expired evidence does not imply packages are absent. Source observation time is unknown. '
                    'Any last-known receipt is historical, not current evidence. No current-host, running-system or health state is established; no mutation authority.')
            if len(text)>500:raise ValueError('Package status context cap')
            identity={key:status[key] for key in ('evidence_status','availability','admission_status')}
            identifier='package_status_'+hashlib.sha256(canonical({'manifest':self.config['sha256'],**identity})).hexdigest()
            context=[{'id':identifier,'text':text}]
            state={**status,'observation_id':identifier,'binding':copy.deepcopy(binding),'data_admitted':admitted,
                'source':copy.deepcopy(source),'last_known_source':None if admitted or self.cache is None else copy.deepcopy(self.cache['result']),
                'last_known_query_receipt_sha256':None if admitted or self.cache is None else self.cache['receipt_sha256'],
                'source_commit':self.manifest['source_commit'],'query_receipt_sha256':active['state']['query_receipt_sha256'] if admitted else None,
                'query_reused':active['state']['query_reused'] if admitted else False,
                'context_sha256':hashlib.sha256(canonical(context)).hexdigest(),'mutation_authority':False,'executed_actions':0}
            stage={'context':context,'state':state}
            record.update(status='passed',evidence_status=status['evidence_status'],data_admitted=admitted,
                          context_sha256=state['context_sha256'],query_receipt_sha256=state['query_receipt_sha256'])
        except BaseException as error:failure=error;record['error']=repr(error)
        self.receipts.append(record)
        try:write_record(directory/'receipt.json',record)
        except BaseException as error:
            record['finalization_errors'].append({'stage':'receipt-write','type':type(error).__name__,'error':str(error)})
            failure=failure or error;record.update(status='failed',error=repr(failure))
        if failure is not None:
            failure.package_evidence_status_receipt=record;raise failure
        return copy.deepcopy(stage)
