"""Per-record invalidation; later batch recovery never revives an armed press."""
def consume(raw,parse_report,lease,target,previous):
    report=parse_report(raw)
    accepted=lease.accept(raw,parse_report)
    supported=(report.get('active') is True and not report.get('fullscreen',True)
               and not report.get('maximized',True))
    if not accepted or not supported or report!=previous:
        if target is not None:target.invalidate()
    if lease.failed:raise ValueError('Heartbeat metadata invalid')
    return report
