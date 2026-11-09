"""Pure client guidance for durable v2 failures; never retries or recovers.

Transport loss is ambiguous: a turn may have committed before delivery failed.
Only the server can verify claim ownership/death. Messages are fixed local text,
never interpolated model output, request identifiers, paths or remote details.
"""
import re

_CONTEXT = {'context_limit','context_projection_limit'}
_RESOURCE = {'native_timeout','resource_limit','native_cancelled','native_turn_failed',
             'context_projection_failed','invalid_token_count_receipt',
             'invalid_output_encoding','missing_generation_receipt','invalid_generation_receipt'}
_TERMINAL = {'failed','interrupted'}


def _result(code, message, retry_mode, *, owner_check=False, outcome='not_established'):
    return {'code':code, 'message':message, 'next_operation':'snapshot',
            'retry_mode':retry_mode, 'automatic_retry':False,
            'requires_user_decision':True, 'requires_verified_dead_owner':owner_check,
            'outcome':outcome}


def describe_transport_failure():
    """Unknown delivery outcome; a new request ID could duplicate user intent."""
    return _result('transport_failure',
        'Delivery stopped before a complete response. Inspect the session, then '
        'resubmit the exact original request, including request_id, expected_revision, '
        'and payload, to retrieve any saved response. '
        'A pending claim must be resolved explicitly; no automatic retry is performed.',
        'exact_original_request_after_snapshot', outcome='unknown')


def describe_error(response):
    """Return bounded plain-language guidance for an actual v2 error packet."""
    if (type(response) is not dict or type(response.get('api_version')) is not int
            or response['api_version']!=2 or response.get('status')!='error'):
        raise ValueError('Expected a v2 error response')
    raw=response.get('code')
    code=raw if type(raw) is str and re.fullmatch(r'[a-z_]{1,64}',raw) else 'unknown_error'
    if code in ('pending','busy'):
        return _result(code,
            'The session has unresolved work. Inspect its snapshot and wait for the '
            'active worker. Recover only after cancellation and after the server '
            'verifies that the original owner is dead.', 'wait_or_explicit_recovery',
            owner_check=True)
    if code=='stale_revision':
        return _result(code,
            'The session changed. Read the latest snapshot and review the new history '
            'before submitting a new request.', 'new_id_after_review')
    if code=='request_conflict':
        return _result(code,
            'This request ID already names a different payload or revision. Use its '
            'exact original request, including expected_revision, for replay, or review '
            'the session before a new request.',
            'original_request_or_new_id_after_review')
    if code=='history_limit':
        return _result(code,
            'This session is full. Its complete history remains available in the '
            'snapshot. Explicitly start a new session if you want to continue.',
            'new_session_after_snapshot')
    if code in _CONTEXT:
        message=('The complete transcript remains available in the snapshot. Review '
                 'a shorter request or an explicitly chosen context policy; if history '
                 'capacity is exhausted, explicitly start a new session. Existing '
                 'history is not deleted or silently summarized.')
        return _result(code,message,'new_id_after_review')
    if code in _RESOURCE or code in _TERMINAL:
        return _result(code,
            'This attempt cannot be rerun with the same ID. Inspect the session and '
            'the reported resource or native failure, then explicitly decide whether '
            'to submit a new request. The client does not resume generation automatically.',
            'new_id_after_review')
    if code=='invalid_request':
        return _result(code,
            'Review the request fields, text bounds and context values before '
            'submitting a corrected request. The client does not repair it automatically.',
            'review_request')
    if code=='not_pending':
        return _result(code,
            'This claim is no longer pending. Read the session snapshot before '
            'deciding whether any further request is needed.', 'review_before_retry')
    if code=='unavailable':
        return _result(code,
            'The server could not verify the required state. Inspect the session '
            'and restore availability before retry or recovery.',
            'review_before_retry', owner_check=True)
    if code=='unsupported_context_policy':
        return _result(code,
            'The configured runtime does not admit this context policy. Review the '
            'request or runtime configuration. No policy is enabled automatically.',
            'review_policy_configuration')
    return _result('unknown_error',
        'The request failed. Inspect the session and diagnostics before another '
        'attempt. Unrecognized remote details are not treated as instructions.',
        'review_before_retry')
