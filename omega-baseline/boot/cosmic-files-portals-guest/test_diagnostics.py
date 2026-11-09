"""Offline unit tests only; never connects to a bus or starts a guest."""
import importlib.util
import pathlib
import unittest
spec = importlib.util.spec_from_file_location('diagnose', pathlib.Path(__file__).with_name('diagnose.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class OwnerTests(unittest.TestCase):
    def test_exact_names_and_read_methods(self):
        calls = []
        def query(method, arg):
            calls.append((method, arg))
            return 123 if method == 'GetConnectionUnixProcessID' else ':1.42'
        evidence = {'pid': 123, 'exe': '/usr/libexec/xdg-desktop-portal-cosmic'}
        result = d.owner_records(query, {'processes': [evidence]})
        self.assertEqual(len(result['bus_owners']), 4)
        self.assertEqual({m for m, _ in calls}, {'GetNameOwner', 'GetConnectionUnixProcessID'})
        self.assertTrue(all(r['process_evidence'] == evidence and r['owner_stable'] for r in result['bus_owners']))
        self.assertFalse(result['dialog_backend_proven_by_ownership_alone'])
    def test_missing_not_activation(self):
        def query(method, arg):
            raise RuntimeError('org.freedesktop.DBus.Error.NameHasNoOwner')
        result = d.owner_records(query, {'processes': []})
        self.assertTrue(all(r['status'] == 'missing_owner' for r in result['bus_owners']))
        self.assertFalse(result['activation_requested'])
    def test_owner_race(self):
        count = {}
        def query(method, arg):
            if method == 'GetConnectionUnixProcessID': return 999
            count[arg] = count.get(arg, 0) + 1
            return ':1.' + str(count[arg])
        result = d.owner_records(query, {'processes': []})
        self.assertTrue(all(r['status'] == 'owner_changed_during_snapshot' and r['process_evidence'] is None for r in result['bus_owners']))
    def test_no_activation_api(self):
        import inspect
        source = inspect.getsource(d.bus_owners)
        self.assertIn('Gio.DBusCallFlags.NO_AUTO_START', source)
        self.assertNotIn('StartServiceByName', source)

if __name__ == '__main__': unittest.main()
