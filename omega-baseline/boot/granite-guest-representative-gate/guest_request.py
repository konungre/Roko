#!/usr/bin/python3.13
"""Exactly two frozen direct Omega requests, independent checks, no tool dispatch."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/run/granite-model-probe/roko')
sys.path[:0]=[str(ROOT/'evaluation'),str(ROOT/'adapters'),str(ROOT/'vendor/guest-python'),str(ROOT/'vendor/PeTTa/repos/Omega/src')]
import providers
import granite_guest
import guest_cases
from working_state import WorkingState


def run_case(case,provider):
    request=guest_cases.make_request(case,providers)
    prompt=granite_guest.render_prompt(request)
    grammar=granite_guest.tool_grammar(granite_guest.validate_request(request))
    if hashlib.sha256(prompt.encode()).hexdigest()!=case['rendered_prompt_sha256'] or hashlib.sha256(grammar.encode()).hexdigest()!=case['grammar_sha256']:
        raise ValueError('Frozen original direct request or grammar changed')
    print('ROKO_GRANITE_GUEST_PHASE '+json.dumps({'phase':'request','case_id':case['id'],'backend':provider.backend}),flush=True)
    provider.last={}
    began=time.monotonic()
    response=providers.llmProviderChat(request)
    row=guest_cases.assess(case,response,WorkingState)
    row.update(request_seconds=round(time.monotonic()-began,3),native=dict(provider.last),
               native_completed=provider.last.get('returncode')==0,
               serialized_proposal=providers.llmResponseToSExpr(response),
               rendered_prompt_sha256=case['rendered_prompt_sha256'],grammar_sha256=case['grammar_sha256'])
    row['passed']=row['native_completed'] and row['format_valid'] and row['exact_correct'] and row['controller_accepted'] is True
    print('ROKO_GRANITE_CASE_RESULT '+json.dumps(row,sort_keys=True),flush=True)
    return row


def summarize(rows,expected_count,runtime_blocker):
    completed=len(rows)==expected_count and runtime_blocker is None and all(row['native_completed'] for row in rows)
    accuracy=completed and all(row['exact_correct'] and row['controller_accepted'] is True for row in rows)
    return {'measurement_completed':completed,'format_valid':completed and all(row['format_valid'] for row in rows),
            'accuracy_passed':accuracy,'passed':accuracy and all(row['format_valid'] for row in rows),
            'model_loaded':True if any(row['native_completed'] for row in rows) else None,
            'failed_accuracy_cases':[row['id'] for row in rows if not row['exact_correct'] or row['controller_accepted'] is not True]}


def main():
    result={'passed':False,'model_loaded':False,'external_actions':0,'default_model_changed':False,
            'actual_omega_commit':'21d8634b57deb45df3d5bcbb144cf4b314793f14',
            'input_token_cap':512,'output_token_cap':64,'native_threads':4,'tcg_cpus':4,
            'cpu_kind':'TCG emulated max; not user hardware','model_hash_checks_warm_page_cache':True,
            'cache_drop_attempted':False,'cases':[],'runtime_blocker':None,
            'request_envelope':'Frozen original native-host direct Omega, not UI/CLI wrapper',
            'graphical_ui_tested':False,'automatic_retries':False}
    provider=granite_guest.GraniteGuestProvider(ROOT);began=time.monotonic()
    try:
        plan=json.loads((ROOT/'evaluation/cases.lock.json').read_text())
        if plan['case_ids']!=['literal_copy','invoice_extraction'] or len(plan['cases'])!=2:
            raise ValueError('Unexpected case selection')
        result['selected_case_ids']=plan['case_ids']
        interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir())
        if interfaces!=['lo']:raise ValueError('Unexpected network interface')
        result['network_interfaces']=interfaces
        result['cpu_proof']=json.loads(subprocess.check_output([str(ROOT/'runtime/granite/cpuid-probe')],timeout=3))
        if result['cpu_proof']['tested_cpus']!=4:raise ValueError('Expected four emulated CPUs')
        print('ROKO_GRANITE_GUEST_PHASE '+json.dumps({'phase':'admission','cpu_proof':result['cpu_proof']}),flush=True)
        providers.registerLLMProvider('GraniteRepresentativeGuest',provider)
        providers.llmProviderStart('GraniteRepresentativeGuest')
        result['startup_verification_seconds']=round(time.monotonic()-began,3)
        result['selected_backend']=provider.backend
        result['raw_model_checks']=provider._raw_model.report
        result['raw_model_record']=provider._raw_model.record
        for case in plan['cases']:
            row=run_case(case,provider);result['cases'].append(row)
            if not row['native_completed']:
                raise RuntimeError('Stop after native runtime/resource/deadline failure in '+case['id'])
    except BaseException as error:
        result['runtime_blocker']=type(error).__name__+': '+str(error)
    finally:
        provider.stop()
        result.update(summarize(result['cases'],2,result['runtime_blocker']))
        result['elapsed_seconds']=round(time.monotonic()-began,3)
        result['guest_meminfo_after']=Path('/proc/meminfo').read_text()
        print('ROKO_GRANITE_GUEST_RESULT '+json.dumps(result,sort_keys=True),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':sys.exit(main())
