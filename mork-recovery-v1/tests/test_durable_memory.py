import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'source'))
from durable_memory import DurableMemory
from native_mork import NativeMORKError


class DurableMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'memory.sqlite'
        self.memory = DurableMemory(self.path)
        self.fact = {'relation': 'likes', 'args': ['sam', 'tea']}

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def remember(self, **kw):
        return self.memory.remember('session_a', self.fact,
                                    source='user-message', turn='turn_1', **kw)

    def test_durable_idempotent_and_scoped_deletion(self):
        key = self.remember()
        self.assertEqual(key, self.remember())
        self.memory.close()
        self.memory = DurableMemory(self.path)
        self.assertFalse(self.memory.forget('session_b', key))
        self.assertTrue(self.memory.forget('session_a', key))
        self.assertFalse(self.memory.forget('session_a', key))

    def test_native_failure_is_never_replaced(self):
        self.remember()
        with patch('native_mork.query_facts', side_effect=NativeMORKError('unavailable')):
            with self.assertRaises(NativeMORKError):
                self.memory.recall('session_a', self.fact)

    def test_provenance_and_session_boundary_with_explicit_test_double(self):
        key = self.remember()
        # This is a contract test double, not native engine evidence.
        with patch('native_mork.query_facts', return_value={
                'facts': [self.fact], 'implementation': 'test-double'}) as query:
            result = self.memory.recall('session_a', self.fact)
            self.assertEqual(result['evidence'][0]['id'], key)
            self.assertEqual(result['evidence'][0]['turn'], 'turn_1')
            self.assertFalse(result['authorizes_actions'])
            self.memory.recall('session_b', self.fact)
            self.assertEqual(query.call_args.args[0], [])

    def test_arity_failure_rolls_back(self):
        self.remember()
        with self.assertRaises(ValueError):
            self.memory.remember('session_a', {'relation': 'likes', 'args': ['sam']},
                                 source='user-message', turn='turn_2')
        self.assertEqual(self.memory.db.execute('SELECT count(*) FROM evidence').fetchone()[0], 1)

    def test_capacity_does_not_silently_drop_evidence(self):
        for i in range(16):
            self.memory.remember('session_a', {'relation': 'r', 'args': ['a' + str(i)]},
                                 source='user-message', turn=str(i))
        with self.assertRaises(ValueError):
            self.remember()
        self.assertEqual(self.memory.db.execute('SELECT count(*) FROM evidence').fetchone()[0], 16)

    def test_executable_fact_rejected(self):
        with self.assertRaises(ValueError):
            self.memory.remember('s', {'relation': '!(execute)', 'args': ['a']},
                                 source='user', turn='t')


if __name__ == '__main__':
    unittest.main()
