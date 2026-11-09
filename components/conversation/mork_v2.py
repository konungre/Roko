"""Native MORK typed-history retrieval for the authoritative v2 CAS store.

SQLite owns history and revisions. This adapter neither commits nor recovers
requests. MORK sees generated turn IDs and roles, never raw conversation text.
Only the explicitly qualified eight-message candidate scope is admitted; its
PathMap revision predates the zipper fix. No matching fallback exists here.
"""
import hashlib
import json
import re
import time

from mork_host import ExternalMORKBackend

MAX_MESSAGES = 8
MAX_MESSAGE_BYTES = 4096
MAX_HISTORY_BYTES = 65536


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def history_digest(history):
    return hashlib.sha256(_canonical(history)).hexdigest()


def validate_history(history):
    if type(history) is not list or len(history)>MAX_MESSAGES or len(history)%2:
        raise ValueError('MORK history requires at most eight complete messages')
    for index,message in enumerate(history):
        if (type(message) is not dict or set(message)!={'role','content'}
                or message['role']!=('user' if index%2==0 else 'assistant')
                or type(message['content']) is not str or not message['content'].strip()
                or len(message['content'].encode('utf-8'))>MAX_MESSAGE_BYTES):
            raise ValueError('Invalid bounded MORK transcript message')
    if len(_canonical(history))>MAX_HISTORY_BYTES:
        raise ValueError('MORK transcript byte limit')


def retrieve_history(history, binding, profile):
    """Return all native-selected history plus receipt; never mutate the store.

    binding has session_id, request_id, revision and history_sha256. The caller
    must obtain these from its already claimed immutable SQLite snapshot, and
    retain the CAS claim through generation and commit.
    """
    validate_history(history)
    if type(binding) is not dict or set(binding)!={'session_id','request_id','revision','history_sha256'}:
        raise ValueError('MORK binding schema')
    for name in ('session_id','request_id'):
        if type(binding[name]) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',binding[name]) is None:
            raise ValueError('Invalid MORK binding identifier')
    if type(binding['revision']) is not int or binding['revision']!=len(history)//2:
        raise ValueError('MORK binding revision does not match complete history')
    before=_canonical(history)
    digest=hashlib.sha256(before).hexdigest()
    if binding['history_sha256']!=digest:
        raise ValueError('MORK binding history digest mismatch')
    config=profile.get('mork_memory')
    if type(config) is not dict or set(config)!={'manifest','manifest_sha256'}:
        raise ValueError('Explicit MORK manifest configuration required')
    facts=[{'relation':'chat_turn','args':['turn_'+str(i),message['role']]}
           for i,message in enumerate(history)]
    # Producer backend remains unchanged. Its database/session fields are not
    # used: only the reviewed runtime manifest is mapped into its host config.
    backend=ExternalMORKBackend({'python':profile['python'],'durable_memory':config})
    started=time.monotonic()
    native=backend.query_facts(facts,{'relation':'chat_turn','args':[None,None]},timeout=3)
    if (native.get('implementation')!='native-mork-rebuild-bounded-facts'
            or native.get('runtime_manifest_sha256')!=config['manifest_sha256']
            or native.get('authorizes_actions') is not False
            or native.get('descendants_cleaned') is not True):
        raise ValueError('MORK retrieval receipt mismatch')
    rows=native.get('facts')
    if type(rows) is not list or len(rows)!=len(facts):
        raise ValueError('MORK did not return complete committed history')
    actual=[]
    for row in rows:
        if type(row) is not dict or set(row)!={'relation','args'} or row['relation']!='chat_turn' or type(row['args']) is not list or len(row['args'])!=2 or any(type(x) is not str for x in row['args']):
            raise ValueError('Invalid MORK turn row')
        actual.append(tuple(row['args']))
    expected=[tuple(row['args']) for row in facts]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):
        raise ValueError('MORK selected missing, changed or unknown turn evidence')
    if _canonical(history)!=before:
        raise ValueError('History changed during native MORK retrieval')
    # Mapping admitted IDs back to text is hydration, not a Python matching
    # fallback. Every expected native result must have been returned above.
    selected=[dict(message) for message in history]
    receipt={**binding,'implementation':'native-mork-v2-complete-transcript-index',
             'seconds':round(time.monotonic()-started,3),'native':native,
             'evidence':[{'id':'turn_'+str(i),'role':message['role'],
                          'message_sha256':history_digest(message)}
                         for i,message in enumerate(selected)],
             'indexed_messages':len(selected),'history_omitted':False,
             'pathmap_limitation':'Pinned candidate predates zipper fix; bounded adapter scope only',
             'authorizes_actions':False,'executed_actions':0}
    return selected,receipt
