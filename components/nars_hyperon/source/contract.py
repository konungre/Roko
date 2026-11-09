"""Data-only NAL-1 chain contract. Independent oracle is a checker, not fallback.

Two inheritance premises with three distinct symbols. Fixed point input keeps
native source generation finite. Actual native conclusions are retained; a
missing, extra, malformed or numerically wrong result is always an error.
"""
import hashlib
import json
import math
import re
from fractions import Fraction

MAX_REQUEST=4096
MAX_RESPONSE=16384
MODULES=['truthfunctions.metta','nal1.metta']

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate JSON key')
        result[k]=v
    return result

def decode(raw,cap):
    if type(raw) is not bytes or not 1<=len(raw)<=cap:raise ValueError('JSON byte cap')
    try:return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (UnicodeError,RecursionError) as e:raise ValueError('Invalid JSON encoding/nesting') from e

def ident(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,31}',value,re.ASCII) is None:raise ValueError('Invalid bounded identifier')
    return value

def premise_payload(p):return {k:v for k,v in p.items() if k!='sha256'}

def make_premise(identifier,source,subject,predicate,frequency_milli,confidence_milli):
    p={'id':identifier,'source':source,'subject':subject,'predicate':predicate,'frequency_milli':frequency_milli,'confidence_milli':confidence_milli}
    return dict(p,sha256=digest(p))

def validate_request(v):
    keys={'version','operation','task_id','revision','premises'}
    if type(v) is not dict or set(v)!=keys:raise ValueError('Request schema')
    if type(v['version']) is not int or v['version']!=1 or v['operation']!='nal1-chain':raise ValueError('Operation/version')
    ident(v['task_id'])
    if type(v['revision']) is not int or not 1<=v['revision']<=2**53-1:raise ValueError('Revision')
    ps=v['premises']
    if type(ps) is not list or len(ps)!=2:raise ValueError('Exactly two premises')
    for p in ps:
        if type(p) is not dict or set(p)!={'id','source','subject','predicate','frequency_milli','confidence_milli','sha256'}:raise ValueError('Premise schema')
        for k in ('id','subject','predicate'):ident(p[k])
        if type(p['source']) is not str or not 1<=len(p['source'].encode('utf-8'))<=256:raise ValueError('Source byte cap')
        for k,hi in (('frequency_milli',1000),('confidence_milli',999)):
            if type(p[k]) is not int or not 0<=p[k]<=hi:raise ValueError('Truth values must be bounded fixed-point integers')
        if type(p['sha256']) is not str or p['sha256']!=digest(premise_payload(p)):raise ValueError('Premise provenance digest')
    if ps[0]['id']==ps[1]['id']:raise ValueError('Distinct evidence IDs required; no evidence reuse')
    a,b,c=ps[0]['subject'],ps[0]['predicate'],ps[1]['predicate']
    if ps[1]['subject']!=b or len({a,b,c})!=3:raise ValueError('Only distinct-symbol inheritance chain')
    raw=canonical(v)
    if len(raw)>MAX_REQUEST:raise ValueError('Request exceeds byte cap')
    return decode(raw,MAX_REQUEST)

def parse_request(raw):return validate_request(decode(raw,MAX_REQUEST))

def input_values(request):
    r=validate_request(request)
    return [p[k] for p in r['premises'] for k in ('frequency_milli','confidence_milli')]

def independent_expected(request):
    r=validate_request(request)
    f1,c1,f2,c2=[Fraction(x,1000) for x in input_values(r)]
    f=f1*f2;weight=f*c1*c2
    return {(0,2):(f,weight),(2,0):(Fraction(1),weight/(weight+1))}

def check_native_rows(rows,request):
    expected=independent_expected(request)
    if type(rows) is not list or len(rows)!=2:raise ValueError('Exactly two actual native conclusions')
    seen=set()
    for row in rows:
        if type(row) is not dict or set(row)!={'subject_index','predicate_index','frequency','confidence'}:raise ValueError('Native row schema')
        a,b=row['subject_index'],row['predicate_index']
        if type(a) is not int or type(b) is not int or (a,b) not in expected or (a,b) in seen:raise ValueError('Unknown/duplicate native conclusion')
        seen.add((a,b))
        for k,reference in zip(('frequency','confidence'),expected[(a,b)]):
            x=row[k]
            if type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1:raise ValueError('Invalid native truth value')
            if not math.isclose(x,float(reference),rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Independent truth-function check failed')
    return sorted(rows,key=lambda x:(x['subject_index'],x['predicate_index']))

def response_from_rows(request,rows):
    r=validate_request(request);rows=check_native_rows(rows,r)
    terms=[r['premises'][0]['subject'],r['premises'][0]['predicate'],r['premises'][1]['predicate']]
    conclusions=[]
    for row in rows:
        direction=(row['subject_index'],row['predicate_index'])
        conclusions.append({'subject':terms[direction[0]],'predicate':terms[direction[1]],
          'frequency':row['frequency'],'confidence':row['confidence'],
          'rule':'deduction' if direction==(0,2) else 'exemplification',
          'premise_ids':[p['id'] for p in r['premises']], 'status':'uncertain-derived-belief'})
    return {'version':1,'operation':'nal1-chain','task_id':r['task_id'],'revision':r['revision'],
      'request_sha256':digest(r),'premises':r['premises'],'conclusions':conclusions,
      'authorizes_actions':False,'executed_actions':0,'persistent_state_changed':False,
      'full_nars':False,'independent_check':'fixed-point-fraction-oracle'}

def validate_packet(packet,request):
    r=validate_request(request)
    if type(packet) is not dict or set(packet)!={'version','request','strict_imports','native_rows','response','runtime','network_denial_observed'}:raise ValueError('Packet schema')
    if canonical(packet['version'])!=b'1' or canonical(packet['request'])!=canonical(r):raise ValueError('Packet identity')
    if packet['strict_imports']!=MODULES or packet['network_denial_observed'] is not True:raise ValueError('Native import/network observation')
    result=response_from_rows(r,packet['native_rows'])
    if canonical(packet['response'])!=canonical(result):raise ValueError('Response differs from native rows, provenance or authority contract')
    return result
