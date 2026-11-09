"""Provisional representation-only OS claims, pending the OS owner's receipt schema."""
import hashlib
import json

PHASES=('desired','resolved','built','activated','running','observed','health')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def encoded(value):return 'h_'+canonical(value).hex()


def validate(packet):
    if type(packet) is not dict or set(packet)!={'schema','backend','machine','boot','producer','sequence','facts','evidence'}:
        raise ValueError('OS claims envelope schema')
    if packet['schema']!='roko.os-state.claims.v0' or packet['backend'] not in ('nix','guix','synthetic'):
        raise ValueError('Provisional OS claims version/backend')
    for key in ('machine','boot','producer'):
        if type(packet[key]) is not str or not 1<=len(packet[key].encode())<=128:
            raise ValueError('Bounded OS claim identity required')
    if type(packet['sequence']) is not int or packet['sequence']<0:
        raise ValueError('Nonnegative snapshot sequence required')
    if type(packet['evidence']) is not list or len(packet['evidence'])>32:
        raise ValueError('Evidence count cap')
    evidence={}
    for row in packet['evidence']:
        if type(row) is not dict or set(row)!={'sha256','body'} or type(row['body']) is not dict:
            raise ValueError('Evidence schema')
        if row['sha256']!=digest(row['body']) or row['sha256'] in evidence:
            raise ValueError('Evidence hash mismatch or duplicate')
        evidence[row['sha256']]=row['body']
    if type(packet['facts']) is not list or len(packet['facts'])>32:
        raise ValueError('Fact count cap')
    seen=set()
    for row in packet['facts']:
        if type(row) is not dict or set(row)!={'phase','subject','generation','value','evidence_sha256'}:
            raise ValueError('State fact schema')
        if row['phase'] not in PHASES:
            raise ValueError('Unknown state phase')
        for name in ('subject','generation'):
            if type(row[name]) is not str or not 1<=len(row[name].encode())<=256:
                raise ValueError('Bounded fact identity required')
        if type(row['evidence_sha256']) is not str or row['evidence_sha256'] not in evidence:
            raise ValueError('Unbound state evidence')
        identity=(row['phase'],row['subject'])
        if identity in seen:raise ValueError('Ambiguous phase/subject')
        seen.add(identity)
    if len(canonical(packet))>16384:
        raise ValueError('OS claims byte cap')
    return json.loads(canonical(packet))


def atoms(packet):
    packet=validate(packet);snapshot='sha_'+digest(packet)
    result=[]
    for row in packet['facts']:
        result.append('(RokoStateClaim '+snapshot+' '+row['phase']+' '+encoded(row['subject'])+' '+
            encoded(row['generation'])+' '+encoded(row['value'])+' sha_'+row['evidence_sha256']+' unverified)')
    result.append('(= (rokoOSState $phase) (match &self (RokoStateClaim '+snapshot+
        ' $phase $subject $generation $value $evidence unverified) '+
        '(RokoStateRow $phase $subject $generation $value $evidence unverified)))')
    return result


def check_rows(packet,phase,rows):
    if phase not in PHASES or type(rows) is not list:
        raise ValueError('Unexpected native phase/results')
    expected=[['RokoStateRow',phase,encoded(row['subject']),encoded(row['generation']),
               encoded(row['value']),'sha_'+row['evidence_sha256'],'unverified']
              for row in packet['facts'] if row['phase']==phase]
    if sorted(rows)!=sorted(expected):
        raise ValueError('Native phase query mismatch')
    return [dict(row) for row in packet['facts'] if row['phase']==phase]
