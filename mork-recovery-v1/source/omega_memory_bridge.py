"""Prepare Omega requests from durable history; no provider or tool execution.

The host supplies its already-loaded Omega providers module and provider budgets.
The return value is (Omega request, durable receipt). Host-approved response text
must be committed using the receipt's request_id and request_token.
"""
from conversation_store import MAX_HISTORY_BYTES, MAX_TURNS, RevisionConflict
from durable_memory import _text


def prepare_omega_request(store, providers, session, *, request_id,
                          expected_revision, system_prompt, max_messages,
                          max_characters, max_tokens=128, role=None):
    system_prompt = _text(system_prompt, 4096)
    if type(max_messages) is not int or not 2 <= max_messages <= MAX_TURNS + 1:
        raise ValueError('Invalid provider message budget')
    if type(max_characters) is not int or not 1 <= max_characters <= MAX_HISTORY_BYTES + 4096:
        raise ValueError('Invalid provider character budget')
    if type(max_tokens) is not int or not 1 <= max_tokens <= 128:
        raise ValueError('Invalid output token budget')
    snap = store.snapshot(session)
    if type(expected_revision) is not int or snap['revision'] != expected_revision:
        raise RevisionConflict('Conversation changed before Omega preparation')
    if not snap['turns'] or len(snap['turns']) + 1 > max_messages or len(system_prompt) + sum(
            len(t['content']) for t in snap['turns']) > max_characters:
        raise ValueError('Complete history exceeds provider budget or is empty')
    receipt = store.prepare(session, request_id=request_id,
                            expected_revision=expected_revision, role=role)
    # Evidence stays in the receipt for inspection. Never promote remembered
    # text/provenance to system instructions or serialize it as executable MeTTa.
    request = providers.llmRequest(
        providers.llmRequestMessage('system', system_prompt),
        [providers.llmRequestMessage(m['role'], m['content']) for m in receipt['messages']],
        max_tokens, 'none', [])
    return request, receipt
