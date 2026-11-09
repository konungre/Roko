"""Receive-only JSON-line framing; caller owns connection, trust and all sends."""


class FramingError(ValueError):pass


class JsonLineFrames:
    max_frame_bytes=131072
    max_chunk_bytes=65536
    max_frames_per_chunk=64

    def __init__(self):
        self._buffer=bytearray();self.state='open';self.frames_received=0

    def abort(self):
        self._buffer.clear();self.state='failed'

    def feed(self,data):
        if self.state!='open':raise FramingError('Receiver is not open')
        try:
            if type(data) is not bytes or len(data)>self.max_chunk_bytes:
                raise FramingError('Expected bounded immutable byte chunk')
            frames=[]
            for part in data.split(b'\n')[:-1]:
                if len(self._buffer)+len(part)>self.max_frame_bytes:raise FramingError('Reply frame byte cap')
                self._buffer.extend(part)
                if not self._buffer:raise FramingError('Empty reply frame')
                try:frame=self._buffer.decode('utf-8',errors='strict')
                except UnicodeError as error:raise FramingError('Invalid UTF-8 reply frame') from error
                frames.append(frame);self._buffer.clear()
                if len(frames)>self.max_frames_per_chunk:raise FramingError('Reply frame batch cap')
            tail=data.rsplit(b'\n',1)[-1]
            if len(self._buffer)+len(tail)>self.max_frame_bytes:raise FramingError('Reply frame byte cap')
            self._buffer.extend(tail);self.frames_received+=len(frames)
            return frames
        except BaseException:
            self.abort();raise

    def eof(self):
        if self.state=='closed':return
        if self.state!='open':raise FramingError('Receiver is not open')
        if self._buffer:
            self.abort();raise FramingError('Incomplete reply frame at EOF')
        self.state='closed'

    def view(self):
        return dict(state=self.state,buffered_bytes=len(self._buffer),frames_received=self.frames_received)


class ReplyIngress:
    """Deliver completed reply frames only; no sockets, timers, sends or retries."""
    def __init__(self,deliver,lost):
        self._frames=JsonLineFrames();self._deliver=deliver;self._lost=lost
        self._state='open';self._delivered=0;self._failure_type=None;self._finalization_errors=[];self._loss_notified=False

    def _notify_lost(self):
        if not self._loss_notified:
            self._loss_notified=True;self._lost()

    def _fail(self,primary):
        self._state='failed';self._failure_type=type(primary).__name__;self._frames.abort()
        try:self._notify_lost()
        except BaseException as error:
            detail={'stage':'local-loss-notification','type':type(error).__name__}
            self._finalization_errors.append(detail)
            primary.reply_ingress_finalization_errors=list(self._finalization_errors)

    def feed(self,data):
        if self._state!='open':raise FramingError('Reply ingress is not open')
        try:
            frames=self._frames.feed(data)
            for frame in frames:
                self._deliver(frame);self._delivered+=1
            return len(frames)
        except BaseException as error:
            self._fail(error);raise

    def transport_failed(self,error):
        if not isinstance(error,BaseException):raise ValueError('Expected caller transport exception')
        if self._state!='open':return False
        self._fail(error);return True

    def eof(self):
        if self._state=='closed':return
        if self._state!='open':raise FramingError('Reply ingress is not open')
        try:
            self._frames.eof();self._notify_lost();self._state='closed'
        except BaseException as error:
            self._fail(error);raise

    def view(self):
        return dict(state=self._state,frames_delivered=self._delivered,
            framing=self._frames.view(),failure_type=self._failure_type,
            finalization_errors=[dict(item) for item in self._finalization_errors],
            automatic_requests=False,connection_authenticated=False,live_host_state_established=False)
