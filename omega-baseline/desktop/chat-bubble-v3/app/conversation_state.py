"""UI turn lifecycle independent of GTK and the eventual Omega transport.

submit(text, done) must return an optional cancellation callable. done(answer,
error=None) may run on any thread. The UI marshals delivery onto its main loop.
Cancellation invalidates presentation; it does not imply backend rollback.
"""
class ConversationState:
    def __init__(self):
        self.generation = 0
        self.pending = False
        self.closed = False
        self.cancel = None
        self.turns = []

    def begin(self, text):
        if self.closed or self.pending or not text.strip():
            return None
        self.generation += 1
        self.pending = True
        self.turns.append(('You', text))
        return self.generation

    def finish(self, token, answer, error=None):
        if self.closed or not self.pending or token != self.generation:
            return False
        self.pending = False
        self.cancel = None
        if error:
            self.turns.append(('Roko', 'Conversation failed: ' + str(error)))
        elif isinstance(answer, str) and answer.strip():
            self.turns.append(('Roko', answer))
        else:
            self.turns.append(('Roko', 'The conversation service returned no answer.'))
        return True

    def attach_cancel(self, token, cancel):
        if self.pending and token == self.generation:
            self.cancel = cancel if callable(cancel) else None

    def stop(self, *, close=False):
        cancel, self.cancel = self.cancel, None
        was_pending = self.pending
        self.generation += 1
        self.pending = False
        self.closed = self.closed or close
        if was_pending:
            self.turns.append(('Roko', 'Turn dismissed; backend completion is not confirmed.'))
        if cancel:
            try:
                cancel()
            except Exception:
                # UI remains dismissible even if transport cleanup fails.
                self.turns.append(('Roko', 'The conversation service could not confirm cancellation.'))
