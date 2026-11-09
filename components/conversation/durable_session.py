"""Explicit host binding of real native MORK to durable Omega history.

No runtime, path, session or query can be selected by the JSON chat request.
The existing four-exchange limit remains stricter than the storage capacity.
"""
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import uuid

import conversation


class DurableSession(conversation.Session):
    def __init__(self, provider, ranker, store, session_id, lease_fd):
        super().__init__(provider, ranker)
        self.store, self.session_id, self.lease_fd = store, session_id, lease_fd
        self.memory_receipts = []
        self.prepared = None
        self.store.abandon_open_requests(session_id)
        saved = store.snapshot(session_id)
        turns = saved['turns']
        if len(turns) > conversation.MAX_HISTORY or len(turns) % 2 or any(
                t['role'] != ('user' if i % 2 == 0 else 'assistant') for i,t in enumerate(turns)):
            raise ValueError('Durable history is not a complete bounded conversation')
        self.history = [{'role':t['role'],'content':t['content']} for t in turns]

    def prepare(self, request):
        super().prepare(request)
        receipt = self.store.prepare_exchange(self.session_id, request_id=uuid.uuid4().hex,
            expected_revision=len(self.history), content=self.pending['content'],
            source='host-chat-input')
        # All <=8 committed messages fit the native <=16 turn-role index. Use
        # the actual native-selected evidence to hydrate Omega's entire history.
        selected = [{'role':t['role'],'content':t['content']} for t in receipt['evidence']]
        if selected != self.history or selected != receipt['messages']:
            raise ValueError('Native memory did not supply the complete committed history')
        self.history = selected
        self.prepared = receipt
        record = {'request_id':receipt['request_id'], 'session':self.session_id,
                  'revision':receipt['revision'], 'history_sha256':receipt['history_sha256'],
                  'evidence':[{'id':t['id'],'sha256':t['sha256'],'source':t['source'],
                               'created_ns':t['created_ns']} for t in receipt['evidence']],
                  'native':receipt['memory']}
        self.memory_receipts.append(record)
        print('ROKO_MORK_PREPARED '+json.dumps(record),file=sys.stderr,flush=True)
        return True

    def commit(self, omega_messages):
        expected = self.history + [self.user_message(), {'role':'assistant','content':self.reply}]
        if self.reply is None or omega_messages != expected or self.prepared is None:
            raise ValueError('Incomplete durable Omega exchange')
        r = self.prepared
        self.store.accept_exchange(self.session_id, request_id=r['request_id'],
            request_token=r['request_token'], content=self.reply)
        self.history = expected
        self.pending = self.prepared = None
        return json.dumps({'text':self.reply, 'context_ids':[f['id'] for f in self.context],
                           'executed_actions':0},ensure_ascii=False)

    def close(self):
        try:
            self.store.abandon_open_requests(self.session_id)
        finally:
            try: self.store.close()
            finally:
                if self.lease_fd is not None:
                    os.close(self.lease_fd)
                    self.lease_fd = None


def open_session(provider, ranker, profile):
    config = profile['durable_memory']
    source = Path(__file__).resolve().parents[2]/'mork-recovery-v1/source'
    sys.path.insert(0,str(source))
    from mork_host import ExternalMORKBackend
    from conversation_store import ConversationStore
    runtime = ExternalMORKBackend(profile)
    path = Path(config['database'])
    parent = path.parent.stat()
    if (not path.is_absolute() or path.parent.resolve()!=path.parent or
            parent.st_uid!=os.getuid() or parent.st_mode & 0o077 or path.is_symlink()):
        raise ValueError('Durable database requires a private host-owned directory')
    if path.exists():
        status = path.stat()
        if not stat.S_ISREG(status.st_mode) or status.st_uid != os.getuid() or status.st_nlink != 1:
            raise ValueError('Invalid durable database file')
    fd = os.open(str(path)+'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    store = None
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store = ConversationStore(path,native_backend=runtime)
        os.chmod(path,0o600)
        return DurableSession(provider,ranker,store,config['session'],fd)
    except BaseException:
        if store is not None:store.close()
        os.close(fd)
        raise
