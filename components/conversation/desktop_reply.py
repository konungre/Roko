"""Candidate reply panel contract; read-only, framework-neutral, no transport."""
import json
if __package__:
    from .desktop_diagnostics import DesktopDiagnostics
    from .package_reply_view import render_reply
    from .desktop_provenance import provenance_view
else:
    from desktop_diagnostics import DesktopDiagnostics
    from package_reply_view import render_reply
    from desktop_provenance import provenance_view


class DesktopReplyPanel:
    def __init__(self,request):
        original=DesktopDiagnostics(request).original()
        if type(original.get('text')) is not str or not 0<len(original['text'])<=4000:
            raise ValueError('Captured bounded turn text required')
        self._request=json.dumps(original,sort_keys=True,allow_nan=False)
        self._reply=None;self._provenance_expanded=False

    def receive(self,packet):
        original=json.loads(self._request)
        if type(packet) is not dict:raise ValueError('Expected completed matching v2 reply')
        encoded=json.dumps(packet,sort_keys=True,allow_nan=False)
        if len(encoded.encode('utf-8'))>131072:raise ValueError('Reply presentation byte cap')
        packet=json.loads(encoded)
        if (type(packet) is not dict or type(packet.get('api_version')) is not int or packet['api_version']!=2
                or packet.get('status') not in ('completed','truncated')
                or packet.get('session_id')!=original['session_id'] or packet.get('request_id')!=original['request_id']
                or type(packet.get('revision')) is not int or packet['revision']!=original['expected_revision']+1
                or type(packet.get('executed_actions')) is not int or packet['executed_actions']!=0
                or type(packet.get('text')) is not str or not 0<len(packet['text'])<=4000):
            raise ValueError('Expected completed matching v2 reply')
        # Validate presentation before accepting; malformed receipt metadata is
        # intentionally a neutral notice, not a silently granted capability.
        render_reply(packet)
        if self._reply is not None and self._reply!=encoded:
            raise ValueError('Saved reply changed for the captured request')
        self._reply=encoded

    def set_provenance_details_visible(self,visible):
        if type(visible) is not bool:raise ValueError('Local details visibility must be boolean')
        if self._reply is None:raise ValueError('No captured reply to inspect')
        self._provenance_expanded=visible

    def view(self,*,snapshot_revision=None,transcript=None):
        if self._reply is None:return None
        packet=json.loads(self._reply);original=json.loads(self._request)
        relation='snapshot_unavailable'
        if snapshot_revision is not None:
            if type(snapshot_revision) is not int or snapshot_revision<0 or type(transcript) is not list:
                raise ValueError('Expected validated snapshot view')
            if snapshot_revision<packet['revision']:relation='snapshot_behind_reply'
            else:
                index=original['expected_revision']*2
                expected=[{'role':'user','content':original['text']},{'role':'assistant','content':packet['text']}]
                relation=('matching_snapshot_turn' if transcript[index:index+2]==expected else 'conflicting_snapshot_turn')
        return {'status':packet['status'],'session_id':packet['session_id'],'request_id':packet['request_id'],
            'reply_revision':packet['revision'],'display_text':render_reply(packet),'history_relation':relation,
            'provenance':provenance_view(packet,expanded=self._provenance_expanded),
            'source_check_refreshed':False,'live_host_state_established':False,'mutation_authority':False,
            'render_as_plain_text':True,'automatic_requests':False}
