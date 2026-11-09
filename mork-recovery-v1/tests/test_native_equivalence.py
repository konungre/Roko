"""Opt-in real native bounded-contract tests; no native fixtures or fallback.

Set ROKO_NATIVE_MANIFEST and ROKO_NATIVE_MANIFEST_SHA256 to a reviewed closure.
These tests do not qualify arbitrary PathMap operations or repair its known bug.
"""
import itertools
import os
import random
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
from rebuilt_mork import RebuiltMORKCandidate
from durable_memory import DurableMemory
from conversation_store import ConversationStore, RevisionConflict


@unittest.skipUnless(os.environ.get('ROKO_NATIVE_MANIFEST'), 'explicit native closure required')
class NativeEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = RebuiltMORKCandidate(os.environ['ROKO_NATIVE_MANIFEST'],
            expected_manifest_sha256=os.environ['ROKO_NATIVE_MANIFEST_SHA256'])

    def lookup(self, facts, query):
        result = self.runtime.query_facts(facts, query)
        self.assertEqual('native-mork-rebuild-bounded-facts', result['implementation'])
        self.assertFalse(result['authorizes_actions'])
        self.assertTrue(result['network_denied'])
        expected = {(f['relation'], tuple(f['args'])) for f in facts
                    if f['relation'] == query['relation'] and
                    all(q is None or q == x for q, x in zip(query['args'], f['args']))}
        self.assertEqual(expected, {(f['relation'], tuple(f['args'])) for f in result['facts']})
        return result

    def test_all_wildcard_masks_and_symbol_aliasing(self):
        # Equal symbols in different positions must not unify independent wildcards.
        for arity in (1, 2, 3):
            facts = [{'relation':'r', 'args':list(args)}
                     for args in itertools.product(('r', 'a'), repeat=arity)]
            facts += [{'relation':'other', 'args':['r'] * arity}]
            for mask in itertools.product((False, True), repeat=arity):
                with self.subTest(arity=arity, mask=mask):
                    self.lookup(facts, {'relation':'r', 'args':[None if x else 'r' for x in mask]})

    def test_permutation_duplicates_absence_and_maximum_symbols(self):
        facts = [{'relation':'relation_1234567', 'args':['symbol_123456789', 'a'+str(i)]}
                 for i in range(8)]
        query = {'relation':'relation_1234567', 'args':[None,None]}
        first = self.lookup(facts, query)['facts']
        self.assertEqual(first, self.lookup(list(reversed(facts))*2, query)['facts'])
        self.lookup(facts, {'relation':'missing', 'args':[None,None]})
        self.lookup([], query)

    def test_duplicate_fact_provenance_and_session_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'memory.sqlite'
            store = DurableMemory(path, native_backend=self.runtime)
            fact = {'relation':'topic', 'args':['lighthouse']}
            try:
                ids = [store.remember('s', fact, source=source, turn='t1')
                       for source in ('host', 'untrusted !(execute)')]
                store.remember('other', fact, source='other-private', turn='t1')
            finally:
                store.close()

            store = DurableMemory(path, native_backend=self.runtime)
            try:
                result = store.recall('s', {'relation':'topic', 'args':[None]})
                self.assertEqual(set(ids), {row['id'] for row in result['evidence']})
                self.assertEqual(1, len(result['facts']))
                self.assertEqual(2, len(result['evidence']))
                self.assertTrue(all(row['created_ns'] > 0 for row in result['evidence']))
                self.assertFalse(result['authorizes_actions'])
                self.assertFalse(store.forget('other', ids[0]))
            finally:
                store.close()

    def test_seeded_maximum_fact_workloads(self):
        # Exercise trie branching and shared prefixes across distinct fresh spaces.
        # The fixed seed makes failures reproducible; no arbitrary programs enter MORK.
        rng = random.Random(729104)
        for case in range(12):
            arity = 1 + case % 3
            facts = [{'relation':rng.choice(('r', 'related', 'relation')),
                      'args':[rng.choice(('a', 'aa', 'aaa', 'ab', 'r')) for _ in range(arity)]}
                     for _ in range(16)]
            query = {'relation':rng.choice(('r', 'related', 'relation', 'absent')),
                     'args':[rng.choice((None, 'a', 'aa', 'r')) for _ in range(arity)]}
            with self.subTest(case=case):
                self.lookup(facts, query)

    def test_native_receipt_cannot_commit_after_other_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.sqlite'
            first = ConversationStore(path, native_backend=self.runtime)
            second = ConversationStore(path, native_backend=self.runtime)
            try:
                receipt = first.prepare_exchange('s', request_id='q', expected_revision=0,
                    content='!(erase-all) is data', source='untrusted-input')
                second.append('s', admission_id='other', role='user', content='intervening',
                              source='host', expected_revision=0)
                before = second.snapshot('s')
                with self.assertRaises(RevisionConflict):
                    first.accept_exchange('s', request_id='q',
                        request_token=receipt['request_token'], content='stale answer')
                self.assertEqual(before, second.snapshot('s'))
                self.assertEqual([], second.snapshot('other')['turns'])
            finally:
                first.close()
                second.close()


if __name__ == '__main__':
    unittest.main()
