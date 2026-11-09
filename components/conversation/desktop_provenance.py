"""Local evidence disclosure only; it reads the captured response, never files."""
if __package__:
    from .package_reply_view import receipt_notice,render_reply,LIMITS
else:
    from package_reply_view import receipt_notice,render_reply,LIMITS


DETAIL_PREFIXES=('Source commit: ','Snapshot digest: ','Local query receipt digest: ')


def provenance_view(packet,*,expanded=False):
    if type(expanded) is not bool:raise ValueError('Local details visibility must be boolean')
    full=render_reply(packet)
    notice=receipt_notice(packet)
    if notice is None:notice='No package receipt attached to this reply. '+LIMITS
    prefix=notice+'\n\n'
    if not full.startswith(prefix):raise ValueError('Reply presentation sections disagree')
    # Only fixed receipt-notice lines are summarized. Model text never supplies
    # metadata, local controls, or any authority flag.
    summary='\n'.join(line for line in notice.split('\n') if not line.startswith(DETAIL_PREFIXES))
    summary+='\nSource observation age: unknown. Inspecting details reads this captured reply only; evidence is not refreshed.'
    return {'summary_text':summary,'details_text':notice if expanded else None,
        'answer_text':full[len(prefix):],'details_expanded':expanded,
        'available_local_controls':['hide_details' if expanded else 'show_details'],
        'render_as_plain_text':True,'automatic_requests':False,'source_check_refreshed':False,
        'live_host_state_established':False,'mutation_authority':False}
