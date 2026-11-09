"""Real non-root Unix sockets and SO_PEERCRED, not a PipeWire service test."""
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'session'))
import foundation_state


@unittest.skipUnless(os.getuid() == 1000 and os.getgid() == 1000, 'Requires non-root session UID/GID1000')
class RealPeerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'pipewire-0'
        code = """import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(sys.argv[1]);s.listen(4)
print('ready',flush=True)
sys.stdin.buffer.read(1)
"""
        self.child = subprocess.Popen([sys.executable, '-I', '-c', code, str(self.path)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop)
        self.assertTrue(select.select([self.child.stdout], [], [], 5)[0], 'Peer startup timed out')
        self.assertEqual(self.child.stdout.readline(), b'ready\n')

    def stop(self):
        if self.child.poll() is None: self.child.terminate()
        self.child.communicate(timeout=5)

    def probe(self, pid):
        # Only relocate the fixed guest socket path; socket and credential calls are real.
        with patch.object(foundation_state, 'Path', return_value=self.path):
            return foundation_state.pipewire_ready(pid)

    def test_launched_nonroot_peer_accepted(self):
        self.assertTrue(self.probe(self.child.pid))

    def test_different_same_uid_process_rejected(self):
        with self.assertRaisesRegex(ValueError, 'launched role'): self.probe(os.getpid())

    def test_dead_peer_refused(self):
        self.stop()
        with self.assertRaises(ConnectionRefusedError): self.probe(self.child.pid)

    def test_symlink_socket_refused(self):
        alias = self.path.with_name('alias')
        alias.symlink_to(self.path)
        self.path = alias
        with self.assertRaisesRegex(ValueError, 'identity'): self.probe(self.child.pid)
