"""Same-guest CLOCK_MONOTONIC output-age lease; no compositor acknowledgment."""
import json,time
MAX_LINE=2048
MAX_INT=(1<<63)-1
class SenderLease:
    def __init__(self):self.report=None;self.last_seq=0;self.last_ms=None;self.failed=False
    def reset_for_new_helper(self):self.__init__()
    def invalidate(self):self.report=None;self.failed=True
    def accept(self,raw,parse_report,now_ns=None):
        if self.failed:return False
        if now_ns is None:now_ns=time.monotonic_ns()
        try:
            if type(now_ns) is not int or not 0<=now_ns<=MAX_INT*1_000_000:raise ValueError('clock')
            if len(raw)>MAX_LINE:raise ValueError('line')
            item=json.loads(raw);seq=item.get('heartbeat_seq');ms=item.get('monotonic_ms')
            if type(seq) is not int or type(ms) is not int or not 1<=seq<=MAX_INT or not 0<=ms<=MAX_INT:raise ValueError('metadata')
            if seq!=self.last_seq+1 or (self.last_ms is not None and ms<self.last_ms):raise ValueError('sequence/time')
            # Millisecond truncation may be up to <1ms older than the actual write.
            age=now_ns-ms*1_000_000
            if age<0:raise ValueError('future')
            report=parse_report(raw)
            self.last_seq=seq;self.last_ms=ms
            self.report=report if age<1_000_000_000 and report.get('active') is True else None
            return self.report is not None
        except (ValueError,TypeError,AttributeError,RecursionError,OverflowError):
            self.invalidate();return False
    def current(self,now_ns=None):
        if now_ns is None:now_ns=time.monotonic_ns()
        if self.failed or self.report is None:return None
        if type(now_ns) is not int or not 0<=now_ns-self.last_ms*1_000_000<1_000_000_000:
            self.report=None;return None
        return self.report
