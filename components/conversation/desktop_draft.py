"""Candidate desktop draft state: proposals only, never a transport executor."""
if __package__:
    from .desktop_diagnostics import DesktopDiagnostics
    from .desktop_reply import DesktopReplyPanel
else:
    from desktop_diagnostics import DesktopDiagnostics
    from desktop_reply import DesktopReplyPanel

class DesktopDraft:
    def __init__(self, text=''):
        self._draft=''; self.edit(text); self._active=None; self._needs_snapshot=True; self._reply=None
    def edit(self, text):
        if type(text) is not str: raise ValueError('Draft must be text')
        self._draft=text
    def begin(self, request, *, confirmed=False):
        if confirmed is not True: raise ValueError('Explicit send required')
        if self._active is not None: raise ValueError('Review the unresolved request first')
        proposal=DesktopDiagnostics(request)
        if proposal.original().get('text')!=self._draft or not self._draft:
            raise ValueError('Request must capture the current nonempty draft')
        panel=DesktopReplyPanel(proposal.original())
        self._active=proposal; self._reply=panel; self._needs_snapshot=True
        return proposal.original()
    def transport_lost(self):
        self._require_active().transport_lost(); self._needs_snapshot=True
    def receive_snapshot(self, packet):
        self._require_active().receive_snapshot(packet); self._needs_snapshot=False
    def receive_reply(self, packet):
        self._require_active()
        self._reply.receive(packet)
    def receive_reply_line(self, line):
        self._require_active()
        self._reply.receive_line(line)
    def set_provenance_details_visible(self, visible):
        self._require_active()
        self._reply.set_provenance_details_visible(visible)
    def receive_error(self, packet):
        self._require_active().receive_error(packet); self._needs_snapshot=True
    def propose(self, action, *, confirmed=False, owner_stopped=False):
        if action!='snapshot' and self._needs_snapshot: raise ValueError('Inspect a fresh snapshot after service loss or error')
        return self._require_active().request_for_user_action(action,confirmed=confirmed,owner_stopped=owner_stopped)
    def review_and_release(self, *, confirmed=False):
        """User finishes reviewing an attempt; does not assert its outcome."""
        current=self._require_active().view()
        if confirmed is not True or self._needs_snapshot or current['snapshot_revision'] is None or current['pending'] is not None:
            raise ValueError('Explicit review of a snapshot without pending work required')
        self._active=None; self._reply=None
    def _require_active(self):
        if self._active is None: raise ValueError('No captured request')
        return self._active
    def view(self):
        active=self._active.view() if self._active else None
        if active is not None:
            active['reply']=self._reply.view(snapshot_revision=active['snapshot_revision'],transcript=active['transcript'])
        if active is not None and self._needs_snapshot:
            active['available_actions']=['snapshot']; active['recovery_requires_verified_dead_owner']=False
        return dict(draft=self._draft,active=active,
                    can_begin=self._active is None,needs_snapshot=self._needs_snapshot,automatic_requests=False,
                    outcome='not_established',render_as_plain_text=True)
