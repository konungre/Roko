"""Controller-only immutable evidence selection, with no runtime or save API.

The caller defines mandatory evidence before preparing a request. Goal/task
instructions always remain in context. This module cannot discover which other
records a verifier/model fixture needs; the integrating controller must name all
of them. Keep the complete original WorkingState; this only produces advice.
"""
from dataclasses import dataclass
import hashlib
import re

from ecan_guest_contract import (ECANContractError, MAX_REVISION, canonical, decode,
                                 digest, exact, integer, make_request, parse_request,
                                 require, string, validate_response)

MAX_SNAPSHOT_BYTES = 1024 * 1024
MAX_CONTEXT_BYTES = 65536
STATE_KEYS = {'task_id', 'goal', 'phase', 'evidence', 'proposal', 'verification', 'executed_actions'}


def _snapshot(value):
    exact(value, STATE_KEYS, 'controller snapshot')
    string(value['task_id'], 128, 'task ID')
    string(value['goal'], 2000, 'task instructions')
    require(value['phase'] == 'open' and type(value['phase']) is str,
            'Advice requires an open task')
    require(value['proposal'] is None and value['verification'] is None,
            'Advice requires unproposed, unverified state')
    integer(value['executed_actions'], 0, 0, 'executed actions')
    records = value['evidence']
    require(type(records) is dict and 1 <= len(records) <= 16, 'Expected 1..16 evidence records')
    for identifier, row in records.items():
        require(type(identifier) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier) is not None,
                'Invalid existing controller evidence ID')
        exact(row, {'source', 'text', 'sha256'}, 'controller evidence')
        string(row['source'], 1000, 'evidence provenance')
        string(row['text'], 8000, 'evidence text')
        require(type(row['sha256']) is str and row['sha256'] == hashlib.sha256(row['text'].encode('utf-8')).hexdigest(),
                'Original evidence digest mismatch')
    return decode(canonical(value), MAX_SNAPSHOT_BYTES)


@dataclass(frozen=True)
class PreparedAdvice:
    """Controller-local detached bytes, never a worker request or writable state."""
    snapshot_json: bytes
    request_json: bytes
    required_ids: tuple
    bindings: tuple

    def request(self):
        return parse_request(self.request_json)


def prepare_advice(snapshot, revision, attention, required_ids, *, focus_capacity, selection_count):
    snapshot = _snapshot(snapshot)
    integer(revision, 1, MAX_REVISION, 'revision')
    evidence = snapshot['evidence']
    require(type(attention) is dict and set(attention) == set(evidence),
            'Attention must cover exactly the controller evidence')
    require(type(required_ids) is list and 1 <= len(required_ids) <= len(evidence),
            'Explicit mandatory evidence is required')
    require(all(type(item) is str and item in evidence for item in required_ids),
            'Mandatory evidence is unavailable')
    require(len(set(required_ids)) == len(required_ids), 'Duplicate mandatory evidence')
    candidates, bindings = [], []
    for index, identifier in enumerate(sorted(evidence)):
        exact(attention[identifier], {'sti', 'lti', 'stimulus'}, 'controller attention')
        generated = f'c{index:02d}'
        candidates.append({'id': generated, **attention[identifier]})
        bindings.append((generated, identifier, evidence[identifier]['sha256']))
    snapshot_sha256 = digest({'state': snapshot, 'required_ids': required_ids, 'bindings': bindings})
    request = make_request(task_id=snapshot['task_id'], revision=revision,
                           snapshot_sha256=snapshot_sha256, candidates=candidates,
                           focus_capacity=focus_capacity, selection_count=selection_count)
    return PreparedAdvice(canonical(snapshot), canonical(request), tuple(required_ids), tuple(bindings))


def _current(plan, snapshot, revision):
    require(type(plan) is PreparedAdvice, 'Invalid prepared advice type')
    request = plan.request()
    current = _snapshot(snapshot)
    integer(revision, 1, MAX_REVISION, 'current revision')
    require(revision == request['revision'], 'Stale controller revision')
    require(canonical(current) == plan.snapshot_json, 'Controller snapshot changed')
    require(type(plan.bindings) is tuple and type(plan.required_ids) is tuple,
            'Invalid immutable controller bindings')
    expected_ids = sorted(current['evidence'])
    expected_bindings = tuple((f'c{i:02d}', identifier, current['evidence'][identifier]['sha256'])
                              for i, identifier in enumerate(expected_ids))
    require(plan.bindings == expected_bindings, 'Controller evidence binding mismatch')
    require([row['id'] for row in request['candidates']] == [row[0] for row in expected_bindings],
            'Candidate set differs from controller evidence')
    require(request['task_id'] == current['task_id'], 'Cross-task advice')
    require(1 <= len(plan.required_ids) <= len(expected_ids)
            and all(type(item) is str and item in current['evidence'] for item in plan.required_ids),
            'Invalid mandatory evidence')
    require(len(set(plan.required_ids)) == len(plan.required_ids), 'Duplicate mandatory evidence')
    require(request['snapshot_sha256'] == digest({'state': current,
            'required_ids': list(plan.required_ids), 'bindings': plan.bindings}),
            'Controller snapshot/mandatory binding digest mismatch')
    return current, request


def assert_current(plan, snapshot, revision):
    """Recheck immediately before use/save; persistence must ALSO use CAS.

    This read-only guard cannot close a race between a read and a later write.
    A future save must use StateStore.save(expected_revision=request.revision)
    and must never overwrite the full original evidence with selected context.
    """
    _current(plan, snapshot, revision)


def select_context(plan, response_raw, *, current_snapshot, current_revision, max_context_bytes):
    """Fail closed; return a detached context and audit, never mutate task state."""
    integer(max_context_bytes, 1, MAX_CONTEXT_BYTES, 'context byte budget')
    snapshot, request = _current(plan, current_snapshot, current_revision)
    response = validate_response(response_raw, request)
    local = {generated: identifier for generated, identifier, _ in plan.bindings}
    top_k = [local[identifier] for identifier in response['selection']]
    chosen = list(plan.required_ids)
    chosen += [identifier for identifier in top_k if identifier not in chosen]
    context = {'version': 1, 'task_id': snapshot['task_id'], 'goal': snapshot['goal'],
               'evidence': [{'id': identifier, **snapshot['evidence'][identifier]} for identifier in chosen]}
    # Bound actual model-facing UTF-8 JSON, including instructions, IDs/provenance,
    # punctuation/escaping and hashes; never drop or truncate required records.
    context_bytes = canonical(context)
    require(len(context_bytes) <= max_context_bytes, 'Selected context exceeds byte budget; no evidence was dropped')
    overrides = [{'id': identifier, 'reason': 'controller_required_outside_advisory_top_k'}
                 for identifier in plan.required_ids if identifier not in top_k]
    return {'version': 1, 'task_id': request['task_id'], 'revision': current_revision,
            'request_sha256': request['request_sha256'], 'snapshot_sha256': request['snapshot_sha256'],
            'advisory_only': True, 'authorizes_actions': False, 'persistent_state_changed': False,
            'native_focus': list(response['focus']), 'ranking': list(response['ranking']),
            'selection': list(response['selection']), 'selected_evidence_ids': chosen,
            'mandatory_overrides': overrides, 'context': context,
            'context_sha256': hashlib.sha256(context_bytes).hexdigest(), 'context_bytes': len(context_bytes)}
