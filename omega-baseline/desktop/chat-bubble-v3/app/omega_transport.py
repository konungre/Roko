"""Persistent JSON-lines transport for components/conversation/run.py.

One process owns one Omega session. A lost/cancelled worker requires explicit reset;
we never replay a possibly committed turn or silently start replacement history.
"""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time

MAX_REPLY_BYTES = 65536
MAX_DIAGNOSTIC_BYTES = 1048576


def decode_reply(line):
    value = json.loads(line)
    if type(value) is not dict or set(value) != {'text', 'context_ids', 'executed_actions'}:
        raise ValueError('Unexpected Omega reply fields')
    if type(value['text']) is not str or not value['text'].strip() or len(value['text']) > 4000:
        raise ValueError('Invalid Omega reply text')
    if type(value['executed_actions']) is not int or value['executed_actions'] != 0:
        raise ValueError('Unexpected action report')
    # This desktop revision sends no symbolic context records.
    if value['context_ids'] != []:
        raise ValueError('Unexpected symbolic context identity')
    return value['text']


class OmegaTransport:
    def __init__(self, command, *, timeout=180, env=None):
        if not command or any(not isinstance(a,str) or not a for a in command):
            raise ValueError('Expected explicit command arguments')
        if not Path(command[0]).is_absolute():
            raise ValueError('Conversation executable must be absolute')
        self.command=tuple(command);self.timeout=timeout;self.env=env
        self.lock=threading.Lock();self.proc=None;self.thread=None
        self.closed=False;self.failed=False;self.busy=False;self.cancel_event=None
        self.diagnostics=''

    def submit(self, text, done):
        if type(text) is not str or not text.strip() or len(text)>4000:
            raise ValueError('Conversation text must contain 1–4000 characters')
        with self.lock:
            if self.closed:raise RuntimeError('Conversation service is closed')
            if self.failed:raise RuntimeError('Session ended. Choose New conversation before sending again.')
            if self.busy:raise RuntimeError('An Omega turn is already running')
            self.busy=True;cancel=threading.Event();self.cancel_event=cancel
            self.thread=threading.Thread(target=self._turn,args=(text,done,cancel),name='roko-conversation',daemon=False)
            self.thread.start()
        return cancel.set

    def _turn(self, text, done, cancel):
        answer=None;error=None
        try:
            if cancel.is_set():raise RuntimeError('Turn cancelled; session ended')
            first=self.proc is None
            if first:
                self.proc=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,start_new_session=True,env=self.env)
                for pipe in (self.proc.stdin,self.proc.stdout,self.proc.stderr):os.set_blocking(pipe.fileno(),False)
            elif self.proc.poll() is not None:
                raise RuntimeError('Omega worker exited; session ended')
            answer=self._exchange(text,cancel,first=first)
            if cancel.is_set():raise RuntimeError('Turn cancelled; completion is uncertain')
        except Exception as exc:
            error=str(exc)
            with self.lock:self.failed=True
            try:self._terminate()
            except Exception as cleanup_error:error += '; cleanup failed: ' + str(cleanup_error)
        finally:
            with self.lock:self.busy=False;self.cancel_event=None
        done(answer,error)

    def _exchange(self,text,cancel,*,first=False):
        payload=(json.dumps({'text':text,'context':[]},ensure_ascii=False)+'\n').encode('utf-8')
        proc=self.proc;buffer=bytearray();diagnostic_bytes=0;sent=0
        deadline=time.monotonic()+self.timeout
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout,selectors.EVENT_READ,'out')
            selector.register(proc.stderr,selectors.EVENT_READ,'err')
            # Reject unsolicited output left by a prior turn, before writing.
            ready=[] if first else selector.select(0)
            for key,_ in ready:
                if key.data=='out':
                    data=os.read(proc.stdout.fileno(),MAX_REPLY_BYTES+1)
                    if data:raise RuntimeError('Unsolicited Omega output; session ended')
                    raise RuntimeError('Omega worker closed its output')
            selector.register(proc.stdin,selectors.EVENT_WRITE,'in')
            while True:
                if cancel.is_set():raise RuntimeError('Turn cancelled; session ended')
                if time.monotonic()>=deadline:raise TimeoutError('Omega turn timed out; completion is uncertain')
                for key,_ in selector.select(min(.05,max(0,deadline-time.monotonic()))):
                    if key.data=='in':
                        try:sent+=os.write(proc.stdin.fileno(),payload[sent:])
                        except BlockingIOError:continue
                        if sent==len(payload):selector.unregister(proc.stdin)
                        continue
                    try:data=os.read(key.fileobj.fileno(),4096)
                    except BlockingIOError:continue
                    if not data:
                        selector.unregister(key.fileobj)
                        if key.data=='out':raise RuntimeError('Omega worker ended before replying; see diagnostics')
                        continue
                    if key.data=='err':
                        diagnostic_bytes+=len(data)
                        self.diagnostics=(self.diagnostics+data.decode('utf-8',errors='replace'))[-8192:]
                    else:
                        buffer.extend(data)
                        if len(buffer)>MAX_REPLY_BYTES:raise ValueError('Omega output line exceeds cap')
                        while b'\n' in buffer:
                            line,_,rest=buffer.partition(b'\n');buffer[:]=rest
                            if line.startswith(b'{'):
                                if sent!=len(payload) or buffer.strip():raise ValueError('Unexpected extra Omega output')
                                return decode_reply(line.decode('utf-8'))
                            diagnostic_bytes+=len(line)+1
                    if diagnostic_bytes>MAX_DIAGNOSTIC_BYTES:raise ValueError('Omega diagnostic output exceeds cap')

    def _terminate(self):
        proc=self.proc
        if proc is None:return
        try:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            # Terminate remaining members even if the group leader already exited.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait(timeout=2)
        finally:
            for pipe in (proc.stdin,proc.stdout,proc.stderr):pipe.close()
            self.proc=None

    def reset(self):
        with self.lock:
            if self.closed:raise RuntimeError('Conversation service is closed')
            if self.busy:raise RuntimeError('Wait for the previous turn to stop')
            self._terminate();self.failed=False;self.diagnostics=''

    def close(self):
        with self.lock:
            self.closed=True
            if self.cancel_event:self.cancel_event.set()
            thread=self.thread
        if thread and thread is not threading.current_thread():thread.join(timeout=5)
        if thread and thread.is_alive():raise RuntimeError('Conversation cleanup has not completed')
        self._terminate()
