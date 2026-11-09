"""Local receipt-age lease, NOT compositor freshness or sender-time proof."""
import math
class ReportLease:
    def __init__(self):self.report=None;self.received=None
    def clear(self):self.report=None;self.received=None
    def accept_drained(self,reports,now,*,fully_drained,eof=False,error=False,helper_running=True):
        # Caller parses complete bounded JSON records with existing tracker parser.
        # A bounded drain that cannot reach EAGAIN is NOT a fresh report.
        self.clear()
        if type(now) not in (int,float) or not math.isfinite(now):return False
        if not fully_drained or eof or error or not helper_running:return False
        if type(reports) is not tuple or not 1<=len(reports)<=2:return False
        # Never allow an earlier invalid/clear report in this batch to be hidden
        # by a later active one. A later clean heartbeat may restore eligibility.
        if any(type(r) is not dict or r.get('active') is not True for r in reports):return False
        self.report=dict(reports[-1]);self.received=now;return True
    def current(self,now,*,helper_running=True):
        if type(now) not in (int,float) or not math.isfinite(now) or not helper_running:
            self.clear();return None
        if self.received is None:return None
        if not 0<=now-self.received<1.0:self.clear();return None
        return self.report
