"""Tiny static overlay checks and actual host CLI recovery; no archive/image/VM."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import observe
import overlay
import storage

DESKTOP=overlay.ROOT/'build-src/omega-avatar-controller-stage/overlay-v1/usr/share/applications/roko.desktop'
CLI=overlay.ROOT/'build-src/omega-avatar-controller-stage/overlay-v1/opt/roko/scripts/roko.py'

class OverlayTests(unittest.TestCase):
    def test_desktop_only_changes_state_destination(self):
        old=DESKTOP.read_bytes();new=overlay.desktop_entry(old)
        self.assertEqual(new.replace(b'/var/lib/roko',b'/root/.local/state/roko'),old)
        self.assertIn(b'--avatar-events /run/user/0/roko/avatar.json',new)
    def test_wrapper_only_changes_state_destination(self):
        wrapper=(overlay.ROOT/'boot/basilisk-avatar-guest/console-fixture.sh').read_bytes()
        original=b'[Desktop Entry]\nExec=/usr/bin/roko-console-fixture\n'
        files,receipt=overlay.prepare(original,wrapper)
        self.assertEqual(files['usr/share/applications/roko.desktop'][0],original)
        self.assertEqual(files['usr/bin/roko-console-fixture'][0].replace(b'/var/lib/roko',b'/root/.local/state/roko'),wrapper)
        self.assertIn('wrapper_after_sha256',receipt)
    def test_rejects_unknown_desktop(self):
        with self.assertRaises(ValueError): overlay.desktop_entry(b'Exec=sh')
    def test_mount_before_session_and_cleanup_before_poweroff(self):
        original=(overlay.ROOT/'boot/cosmic-session-guest/init.sh').read_bytes()
        result=overlay.derive_init(original)
        self.assertLess(result.index(b'/usr/libexec/roko-storage-mount'),result.index(b'/usr/bin/dbus-daemon --config-file'))
        self.assertLess(result.index(b'/usr/libexec/roko-storage-unmount'),result.index(b'echo ROKO_SESSION_POWER_OFF'))
        with self.assertRaises(ValueError): overlay.derive_init(b'unknown init')
    def test_actual_pinned_module_overlay(self):
        files,receipt=overlay.prepare(DESKTOP.read_bytes())
        self.assertEqual(set(receipt['modules']),{'virtio_blk','crc32c_generic','jbd2','crc16','mbcache','ext4'})
        self.assertIn('storage-modules/ext4.ko',files)
        self.assertIn('usr/libexec/roko-storage-observe.py',files)
    def test_safe_disk_command(self):
        base=['qemu','-nic','none','-append','rdinit=/init']
        result=storage.attach_command(base,99,'write')
        self.assertIn('rdinit=/init roko.desktop-storage=write',result)
        self.assertIn('/proc/self/fd/99',' '.join(result))
        for changed in [base+['-drive','file=/dev/sda'],['qemu','-nic','user','-append','rdinit=/init']]:
            with self.assertRaises(ValueError): storage.attach_command(changed,99,'read')
        with self.assertRaises(ValueError): storage.attach_command(base,99,'other')

class GenuineStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.state=Path(self.temp.name);self.state.chmod(0o700)
        self.patches=[patch.object(observe,'CLI',CLI),patch.object(observe,'STATE',self.state)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def call(self,*args):
        subprocess.run([sys.executable,str(CLI),'--state-dir',str(self.state),*args],check=True,capture_output=True,text=True,timeout=10)
    def populate(self):
        self.call('create','desktop-persist','--goal','Desktop recovery')
        self.call('evidence','desktop-persist','source','--source','fixture:desktop','--text','Arithmetic: 7 * 8.')
        self.call('propose','desktop-persist','--tool','record_answer','--arguments','{"text":"56"}','--evidence','source')
        self.call('check','desktop-persist','--checker','arithmetic')
        self.call('close','desktop-persist')
    def test_observer_uses_actual_cli_without_writing(self):
        self.populate();before={p.name:p.read_bytes() for p in self.state.iterdir()}
        value=observe.snapshot();self.assertEqual(value['revision'],5)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.state.iterdir()})
    def test_pending_task_cannot_pass(self):
        self.call('create','desktop-persist','--goal','Desktop recovery')
        with self.assertRaises(ValueError):observe.snapshot()
    def test_pair_requires_matching_actual_state_and_console_evidence(self):
        self.populate();value=observe.snapshot()
        common='ROKO_DESKTOP_STORAGE_STATE '+json.dumps(value)+'\nROKO_DESKTOP_STORAGE_UNMOUNTED\n'
        write='ROKO_DESKTOP_STORAGE_MOUNTED write\nROKO_DESKTOP_STORAGE_BLANK\nROKO_DESKTOP_STORAGE_WRITE_PASSED\nROKO_DESKTOP_STORAGE_CONSOLES [{"pid":10,"argv":["/usr/bin/python3.13","/opt/roko/scripts/roko.py","--state-dir","/var/lib/roko","--avatar-events","/run/user/0/roko/avatar.json","console"]}]\n'+common
        read='ROKO_DESKTOP_STORAGE_MOUNTED read\nROKO_DESKTOP_STORAGE_READ_PASSED\n'+common
        self.assertTrue(storage.validate_pair(write,read)['storage_passed'])
        with self.assertRaises(ValueError):storage.validate_pair(write.replace('[{"pid":10,"argv":["/usr/bin/python3.13","/opt/roko/scripts/roko.py","--state-dir","/var/lib/roko","--avatar-events","/run/user/0/roko/avatar.json","console"]}]','[]'),read)
        with self.assertRaises(ValueError):storage.validate_pair(write,read.replace(value['checkpoint_sha256'],'0'*64))
    def test_corrupt_actual_checkpoint_rejected(self):
        self.populate();p=next(self.state.glob('*.json'));p.write_bytes(p.read_bytes().replace(b'Desktop recovery',b'Wrong goal here'))
        with self.assertRaises(ValueError):observe.snapshot()

if __name__=='__main__':unittest.main()
