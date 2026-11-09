import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"session"))
from foundation_state import wait_pipewire

class ReadinessTests(unittest.TestCase):
    def setup_role(self):
        self.now=0
        def drain(interval):self.now+=interval
        self.child=Mock(pid=321);self.child.poll.return_value=None
        self.supervisor=SimpleNamespace(state=SimpleNamespace(mode="starting"),children={"pipewire":self.child},drain=drain)
        return self.supervisor

    def test_missing_socket_then_owned_peer(self):
        role=self.setup_role();probe=Mock(side_effect=[FileNotFoundError(),ConnectionRefusedError(),True])
        self.assertTrue(wait_pipewire(role,clock=lambda:self.now,probe=probe))
        self.assertEqual(probe.call_count,3)
        probe.assert_called_with(321)

    def test_wrong_peer_is_not_retried(self):
        role=self.setup_role();probe=Mock(side_effect=ValueError("wrong peer"))
        with self.assertRaises(ValueError):wait_pipewire(role,clock=lambda:self.now,probe=probe)
        self.assertEqual(probe.call_count,1)

    def test_dead_role_refuses(self):
        role=self.setup_role();self.child.poll.return_value=69;probe=Mock()
        with self.assertRaises(RuntimeError):wait_pipewire(role,clock=lambda:self.now,probe=probe)
        probe.assert_not_called()

    def test_control_transition_aborts_startup(self):
        role=self.setup_role();role.state.mode="recovery";probe=Mock()
        self.assertFalse(wait_pipewire(role,clock=lambda:self.now,probe=probe));probe.assert_not_called()

    def test_bounded_wait_no_restart(self):
        role=self.setup_role();probe=Mock(side_effect=FileNotFoundError())
        with self.assertRaises(TimeoutError):wait_pipewire(role,clock=lambda:self.now,probe=probe)
        self.assertLessEqual(self.now,30.2)
        self.assertEqual(set(role.children),{"pipewire"})

if __name__=='__main__':unittest.main()
