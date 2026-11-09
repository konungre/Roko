"""Pure waiting presentation; no clock, transport, timeout or action executor."""
import math
if __package__:
    from .desktop_draft import DesktopDraft
else:
    from desktop_draft import DesktopDraft

def waiting_view(draft,elapsed_seconds,*,connection_lost=False):
    if not isinstance(draft,DesktopDraft):raise ValueError('Expected captured desktop draft')
    if type(elapsed_seconds) not in (int,float) or not math.isfinite(elapsed_seconds) or elapsed_seconds<0:
        raise ValueError('Elapsed time must be finite and nonnegative')
    if type(connection_lost) is not bool:raise ValueError('Expected connection state boolean')
    state=draft.view()
    if state['active'] is None:raise ValueError('No captured request is being awaited')
    if connection_lost:
        message='Connection lost. The request outcome is unknown. Inspect the session before deciding whether to replay or recover.'
    elif elapsed_seconds>=30:
        message='Still waiting for a committed reply. No new reply has been confirmed. Your draft is retained.'
    else:
        message='Waiting for a committed reply. Your draft is retained.'
    return dict(message=message,elapsed_seconds=int(elapsed_seconds),progress_fraction=None,
                request_outcome='unknown' if connection_lost else 'not_confirmed',
                draft=state['draft'],transcript=state['active']['transcript'] if state['active']['snapshot_revision'] is not None else None,
                transcript_available=state['active']['snapshot_revision'] is not None,
                render_as_plain_text=True,send_enabled=False,replay_enabled=False,recover_enabled=False,
                suggested_actions=['inspect_session'],action_requires_confirmation=True,
                automatic_requests=False,automatic_timeout=False)
