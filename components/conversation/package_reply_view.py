"""Plain-text receipt presentation for v2 replies; no transport or authority.

stdin accepts one saved/server response per line. This does not recheck sources,
rerun a model, authenticate a producer, or establish current host state.
"""
import datetime
import json
import re
import sys


LIMITS='Live host, running system, activation and health: not established. No mutation authority.'
STATUSES={
    'available_freshness_unknown':'Qualified receipt available at the recorded check; observation age unknown.',
    'source_missing':'Receipt data missing at the recorded check; package absence is not established.',
    'source_inaccessible':'Receipt data inaccessible at the recorded check; package absence is not established.',
    'source_unreadable':'Receipt data unreadable at the recorded check; package absence is not established.',
    'source_changed':'Receipt bytes changed; no current source admitted.',
    'source_invalid':'Receipt data invalid; no current source admitted.',
    'admission_expired':'Local admission expired; this is not the source observation age.',
    'admission_clock_unverifiable':'Local admission clock unverifiable; no current source admitted.',
}
AUTHORITY=('mutation_authority','current_host_state_established','system_activation_established',
           'running_system_established','health_established','native_nix_reexecuted_here','producer_authenticated')


def _digest(value,length=64):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None


def _identity(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',value) is not None


def _label(value):
    if type(value) is not str or not 1<=len(value)<=128:raise ValueError('Receipt label')
    # Quoted JSON avoids control-character, newline, and terminal escape injection.
    return json.dumps(value,ensure_ascii=True)


def _source(value):
    if type(value) is not dict or any(value.get(key) is not False for key in AUTHORITY):
        raise ValueError('Receipt cannot establish host authority')
    if (type(value.get('source_revision')) is not int or value['source_revision']<1
            or not _digest(value.get('source_commit'),40) or not _digest(value.get('snapshot_sha256'))):
        raise ValueError('Receipt provenance')
    return {'machine':_label(value.get('machine')),'revision':value['source_revision'],
            'commit':value['source_commit'],'snapshot':value['snapshot_sha256']}


def receipt_notice(response):
    """Return deterministic plain text; unsupported metadata yields no source claims."""
    if 'package_state' not in response:return None
    generic=('Package receipt: provenance could not be presented. Observation age unknown. '+LIMITS)
    try:
        state=response['package_state'];binding=state['binding']
        if (type(state) is not dict or type(binding) is not dict
                or not _identity(response.get('session_id')) or not _identity(response.get('request_id'))
                or binding.get('session_id')!=response.get('session_id')
                or binding.get('request_id')!=response.get('request_id')
                or type(response.get('revision')) is not int or response['revision']<1
                or type(binding.get('revision')) is not int or binding['revision']!=response['revision']-1
                or state.get('mutation_authority') is not False
                or type(state.get('executed_actions')) is not int or state['executed_actions']!=0
                or type(response.get('executed_actions')) is not int or response['executed_actions']!=0):
            raise ValueError('Receipt reply binding/authority')
        status=state.get('evidence_status')
        if 'evidence_status' not in state:
            if any(key in state for key in ('availability','admission_status','data_admitted',
                    'source_observation_time_known','evidence_checked_at_ns','qualified_at_ns','max_admission_age_seconds')):
                raise ValueError('Incomplete receipt status schema')
            # Legacy strict admission lacks a check timestamp and freshness policy.
            if state.get('source') is None:raise ValueError('Missing strict source')
            summary='Qualified imported receipt; check time and observation age unknown.'
            admitted=True
        else:
            if status not in STATUSES or state.get('source_observation_time_known') is not False:
                raise ValueError('Unknown receipt status/freshness')
            admitted=status=='available_freshness_unknown'
            if state.get('data_admitted') is not admitted:raise ValueError('Receipt admission mismatch')
            availability=('available' if admitted or status.startswith('admission_') else status.removeprefix('source_'))
            admission=('valid' if admitted else status.removeprefix('admission_') if status.startswith('admission_') else None)
            if state.get('availability')!=availability or (admission is not None and state.get('admission_status')!=admission):
                raise ValueError('Receipt status mismatch')
            qualified=state.get('qualified_at_ns');window=state.get('max_admission_age_seconds')
            checked=state.get('evidence_checked_at_ns')
            if (type(qualified) is not int or qualified<0 or type(window) is not int or not 1<=window<=31536000
                    or type(checked) is not int or checked<0):
                raise ValueError('Receipt admission policy')
            recorded_admission=('clock_unverifiable' if checked<qualified else 'expired'
                if checked-qualified>window*1000000000 else 'valid')
            if state.get('admission_status')!=recorded_admission:
                raise ValueError('Contradictory recorded admission')
            if not _digest(state.get('source_commit'),40):raise ValueError('Missing status source commit')
            summary=STATUSES[status]
        lines=['Package receipt',summary,'Service-reported provenance; this view does not independently verify source files.']
        if 'evidence_status' in state:
            checked=state.get('evidence_checked_at_ns')
            if type(checked) is not int or checked<0:raise ValueError('Receipt check time')
            seconds,nanos=divmod(checked,1000000000)
            stamp=datetime.datetime.fromtimestamp(seconds,datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f'Recorded evidence check: {stamp}.{nanos:09d} UTC (not observation time).')
        source=state.get('source') if admitted else state.get('last_known_source')
        proof=state.get('query_receipt_sha256') if admitted else state.get('last_known_query_receipt_sha256')
        if not admitted and (state.get('source') is not None or state.get('query_receipt_sha256') is not None):
            raise ValueError('Unadmitted current source')
        if source is not None:
            provenance=_source(source)
            if 'evidence_status' in state and provenance['commit']!=state['source_commit']:
                raise ValueError('Contradictory source commit')
            if not _digest(proof):raise ValueError('Missing query proof digest')
            prefix='Imported source' if admitted else 'Historical last-known source (not current evidence)'
            lines.append(f"{prefix}: machine {provenance['machine']}, revision {provenance['revision']}.")
            lines.append('Source commit: '+provenance['commit'])
            lines.append('Snapshot digest: '+provenance['snapshot'])
            lines.append('Local query receipt digest: '+proof+' (not producer authentication).')
        elif admitted:raise ValueError('Missing admitted provenance')
        elif proof is not None:raise ValueError('Orphan historical query proof')
        lines.extend([LIMITS,'Recorded for this turn; saved replay does not refresh evidence.'])
        return '\n'.join(lines)
    except (KeyError,TypeError,ValueError,OverflowError,OSError):
        return generic


def render_reply(response):
    if (type(response) is not dict or type(response.get('api_version')) is not int or response['api_version']!=2
            or response.get('status') not in ('completed','truncated') or type(response.get('text')) is not str
            or len(response['text'])>4000):
        raise ValueError('Expected bounded completed or truncated v2 reply')
    # Terminal-safe text; preserve raw text in the authoritative API response.
    text=''.join(c if c in '\n\t' or c.isprintable() else '\\u%04x'%ord(c) for c in response['text'])
    notice=receipt_notice(response)
    if notice is None:notice='No package receipt attached to this reply. '+LIMITS
    heading='Generated answer (package claims are advisory):'
    if response['status']=='truncated':heading+=' [truncated]'
    quoted='\n'.join('  | '+line for line in text.split('\n'))
    return ((notice+'\n\n') if notice else '')+heading+'\n'+quoted


def load_packet(line):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate response key')
            result[key]=value
        return result
    def nonfinite(value):raise ValueError('Nonfinite response number')
    return json.loads(line,object_pairs_hook=unique,parse_constant=nonfinite)


def main():
    while True:
        line=sys.stdin.readline(131073)
        if not line:break
        if len(line.encode('utf-8'))>131072:raise ValueError('Response byte cap')
        print(render_reply(load_packet(line)),flush=True)


if __name__=='__main__':main()
