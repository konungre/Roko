import hashlib
from pathlib import Path
import stat
import subprocess
import unittest
import prepare

class DeltaTests(unittest.TestCase):
    def test_locked_actual_inputs_and_small_size(self):
        entries,receipt=prepare.prepare()
        self.assertLess(receipt['payload_bytes'],2*1024**2)
        self.assertFalse(receipt['assembly_performed'])
        for name,(data,mode,major,minor) in entries.items():
            self.assertFalse(stat.S_ISLNK(mode));self.assertFalse(mode&0o6000)
        self.assertIn('roko-test-seed/files/diagnostic-entry.sh',entries)
    def test_hook_exact_and_after_tmpfs(self):
        original=(prepare.ROOT/'boot/disk-root-guest/init.sh').read_bytes()
        derived=prepare.derive_init(original)
        marker=b'/bin/busybox sh /roko-test-install.sh || fail test-delta\n'
        self.assertEqual(derived.replace(marker,b''),original)
        self.assertLess(derived.index(b'mount -t tmpfs'),derived.index(marker))
        self.assertLess(derived.index(marker),derived.index(b'switch_root /newroot'))
        with self.assertRaises(ValueError):prepare.derive_init(original+b'changed')
    def test_files_only_has_no_corner_payload_and_explicit_short_command(self):
        entries,receipt=prepare.prepare('files')
        self.assertFalse(any('/corner/' in name for name in entries))
        self.assertIsNone(receipt['corner_inputs_sha256'])
        self.assertIn(b'fp() { /bin/sh',entries['roko-test-seed/env.sh'][0])
        self.assertLess(receipt['payload_bytes'],32*1024)
        with self.assertRaises(ValueError):prepare.prepare('arbitrary')
    def test_corner_only_has_no_files_helpers(self):
        entries,receipt=prepare.prepare('corner')
        self.assertFalse(any('/files/' in name for name in entries))
        self.assertIn('roko-test-seed/env.sh',entries)
        self.assertIn(b'rc() { /usr/bin/python3.13',entries['roko-test-seed/env.sh'][0])
        self.assertNotIn(b'fp()',entries['roko-test-seed/env.sh'][0])
        self.assertLess(receipt['payload_bytes'],579000)
        self.assertIn('roko-test-seed/corner/observe.py',entries)
    def test_path_rejection(self):
        for name in ['/etc/passwd','../escape','a/../b','a b','a\ncommand','a;command']:
            with self.assertRaises(ValueError):prepare.safe_name(name)
    def test_installer_checks_hashes_modes_owners_and_refuses_reuse(self):
        entries,report=prepare.prepare();script=entries['roko-test-install.sh'][0]
        self.assertIn(b'[ ! -e "$DEST" ] && [ ! -L "$DEST" ]',script)
        self.assertIn(b'sha256sum -c /roko-test-sha256',script)
        self.assertIn(b'stat -c %u:%g:%h:%a',script)
        subprocess.run(['sh','-n'],input=script,check=True)
    def test_run_mount_is_executable_without_security_change(self):
        script=(prepare.ROOT/'boot/disk-root-guest/init.sh').read_text()
        self.assertIn('"$options",nodev,nosuid',script)
        self.assertNotIn('noexec',script)
        self.assertNotIn('mount -o bind',script)

if __name__=='__main__':unittest.main()
