"""Read OS-owner observed profile history using its canonical wrapper digest.

This consumes exported facts/receipts without rewriting the OS owner's ledger.
The isolated built-fact ledger uses a different predecessor scheme and is not
used for these observed private-profile facts.
"""
import hashlib
import json
import re
from components.os_atomspace.contract import validate,digest
from components.os_atomspace.os_fact_v1 import decode,validate_fact


def owner_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def import_profile_history(facts_raw,receipts_raw,source_commit):
    facts=decode(facts_raw,16384);receipts=decode(receipts_raw,32768)
    if type(source_commit) is not str or not re.fullmatch('[0-9a-f]{40}',source_commit):
        raise ValueError('Pinned OS-owner source commit required')
    if (type(facts) is not list or type(receipts) is not list or not 1<=len(facts)<=16
            or len(facts)!=len(receipts)):
        raise ValueError('Bounded complete OS profile history required')
    previous='0'*64;identity=None
    for index,(fact,receipt) in enumerate(zip(facts,receipts),1):
        fact=validate_fact(fact)
        if fact['backend']!='nix' or fact['stage']!='observed':
            raise ValueError('Profile operation receipt is only an observed claim')
        current=(fact['machine'],fact['backend'])
        if identity is None:identity=current
        if (current!=identity or fact['revision']!=index or fact['predecessor']!=previous
                or type(receipt) is not dict or fact['evidence_sha256']!=owner_digest(receipt)):
            raise ValueError('OS profile revision/receipt/identity chain mismatch')
        operation=receipt.get('operation')
        if operation=='build-and-profile-switch':
            if set(receipt)!={'operation','build','switch','payload'} or type(receipt['switch']) is not dict:
                raise ValueError('Unsupported native profile switch receipt')
            profile=receipt['switch'].get('receipt')
            expected_scope='private-user-profile'
        elif operation=='rollback':
            if set(receipt)!={'operation','receipt'}:
                raise ValueError('Unsupported native profile rollback receipt')
            profile=receipt['receipt']
            expected_scope='private-user-profile-rollback'
        else:raise ValueError('Unsupported OS profile operation')
        if type(profile) is not dict or profile.get('scope')!=expected_scope:
            raise ValueError('Only explicit private-profile receipts supported')
        previous=owner_digest({'fact':fact,'mode':'observed'})
    latest=facts[-1]
    evidence={'source_commit':source_commit,'facts_hex':facts_raw.hex(),'receipts_hex':receipts_raw.hex(),
              'source_ledger_head_sha256':previous,'mode':'observed'}
    sha=digest(evidence)
    return validate({'schema':'roko.os-state.claims.v0','backend':'nix','machine':latest['machine'],
        'boot':'unobserved-in-private-profile-receipt','producer':'os-owner:'+source_commit,
        'sequence':latest['revision'],'evidence':[{'sha256':sha,'body':evidence}],
        'facts':[{'phase':'observed','subject':'private-profile-operation','generation':latest['generation'],
            'evidence_sha256':sha,'value':{'source_fact':latest,'operation':receipts[-1]['operation'],
                'source_chain_verified':True,'source_ledger_head_sha256':previous,
                'native_execution_requalified_here':False,'producer_authenticated':False,
                'system_activation_observed':False,'scope':'external-private-user-profile-operation'}}]})
