"""Read the OS owner's v1 built fact with its exact content-bound Nix receipt.

This checks data correspondence. It does not authenticate the producer, rerun
Nix, establish activation/running state or grant an operation capability.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

from components.os_atomspace.contract import validate,digest


def decode(raw,limit):
    if type(raw) is not bytes or not 0<len(raw)<=limit:
        raise ValueError('OS fact/receipt byte cap')
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('Duplicate OS evidence key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=unique)


def validate_fact(fact):
    required={'machine','backend','revision','stage','generation','evidence_sha256','predecessor','schema'}
    if type(fact) is not dict or set(fact)!=required or fact['schema']!='roko-os-fact-v1':
        raise ValueError('Require exact OS-owner v1 fact')
    if fact['backend'] not in ('nix','guix') or fact['stage'] not in ('desired','resolved','built','activated','running','observed','health'):
        raise ValueError('OS fact backend/stage')
    if type(fact['revision']) is not int or fact['revision']<1:
        raise ValueError('OS fact revision')
    for key in ('machine','generation'):
        if type(fact[key]) is not str or not re.fullmatch('[a-zA-Z0-9._-]{1,128}',fact[key]):
            raise ValueError('OS fact identity')
    for key in ('evidence_sha256','predecessor'):
        if type(fact[key]) is not str or not re.fullmatch('[0-9a-f]{64}',fact[key]):
            raise ValueError('OS fact digest')
    return fact


def import_built_fact(fact_raw,receipt_raw,source_commit):
    fact=validate_fact(decode(fact_raw,4096))
    if fact['backend']!='nix' or fact['stage']!='built':
        raise ValueError('Only content-bound Nix built facts supported by this reader')
    if type(source_commit) is not str or not re.fullmatch('[0-9a-f]{40}',source_commit):
        raise ValueError('Pinned OS-owner source commit required')
    receipt=decode(receipt_raw,8192)
    if hashlib.sha256(receipt_raw).hexdigest()!=fact['evidence_sha256']:
        raise ValueError('Native build receipt bytes differ from v1 fact')
    if type(receipt) is not list or len(receipt)!=1 or type(receipt[0]) is not dict:
        raise ValueError('Require one native Nix build result')
    row=receipt[0]
    if (set(row)!={'drvPath','outputs','startTime','stopTime'} or type(row['outputs']) is not dict
            or set(row['outputs'])!={'out'}):
        raise ValueError('Unsupported Nix build receipt')
    for key in ('startTime','stopTime'):
        if type(row[key]) is not int or row[key]<0:raise ValueError('Nix build timestamp')
    if row['stopTime']<row['startTime']:raise ValueError('Nix build timestamp order')
    for path in (row['drvPath'],row['outputs']['out']):
        if type(path) is not str:
            raise ValueError('Nix output path')
        parsed=PurePosixPath(path)
        if not parsed.is_absolute() or '..' in parsed.parts or str(parsed)!=path:
            raise ValueError('Nix output path')
    if not row['drvPath'].endswith('.drv') or PurePosixPath(row['outputs']['out']).name!=fact['generation']:
        raise ValueError('Nix output does not match fact generation')
    evidence={'source_commit':source_commit,'fact_hex':fact_raw.hex(),'receipt_hex':receipt_raw.hex(),
              'receipt_sha256':fact['evidence_sha256']}
    sha=digest(evidence)
    packet={'schema':'roko.os-state.claims.v0','backend':'nix','machine':fact['machine'],
        'boot':'unobserved-in-v1-built-fact','producer':'os-owner:'+source_commit,'sequence':fact['revision'],
        'evidence':[{'sha256':sha,'body':evidence}],
        'facts':[{'phase':'built','subject':'generation-artifact','generation':fact['generation'],
            'evidence_sha256':sha,'value':{'source_fact':fact,'receipt_binding_verified':True,
                'native_execution_requalified_here':False,'producer_authenticated':False,
                'output_artifact_bytes_verified':False,
                'output_path':row['outputs']['out']}}]}
    return validate(packet)
