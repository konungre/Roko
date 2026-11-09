"""No format, large extraction, assembly or VM. Tiny in-memory fixtures only."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import image
import plan
import probe
import runner_support
import source
import tooling
import transform

class ArchiveTests(unittest.TestCase):
    def test_root_tar_metadata_and_symlink(self):
        with tarfile.open(fileobj=io.BytesIO(probe.fixture()),mode='r:') as tar:
            items={x.name:x for x in tar}
            self.assertEqual({(x.uid,x.gid) for x in items.values()},{(0,0)})
            self.assertEqual(items['private'].mode,0o750)
            self.assertEqual(items['private/fixture'].mode,0o640)
            self.assertTrue(items['private/link'].issym());self.assertEqual(items['private/link'].linkname,'fixture')
    def test_no_unsafe_path_special_or_setid(self):
        for name in ['/etc/passwd','../escape','root/../escape','root\nfile']:
            with self.assertRaises(ValueError):source.tar_info(name,stat.S_IFREG|0o644)
        for mode in [stat.S_IFCHR|0o600,stat.S_IFREG|0o4755]:
            with self.assertRaises(ValueError):source.tar_info('file',mode)
    def test_payload_hash_and_bounds(self):
        value=source.Slice(io.BytesIO(b'abcTAIL'),3)
        self.assertEqual(value.read(100),b'abc');value.verify(hashlib.sha256(b'abc').hexdigest())
        with self.assertRaises(ValueError):value.verify('0'*64)
        with self.assertRaises(ValueError):source.Slice(io.BytesIO(b'a'),3).read()
    def test_hash_sink(self):
        target=io.BytesIO();sink=source.HashSink(target);sink.write(b'abc')
        self.assertEqual(sink.count,3);self.assertEqual(sink.digest.hexdigest(),hashlib.sha256(b'abc').hexdigest())
    def test_actual_source_inventory_and_budget(self):
        value=plan.summary();self.assertEqual(value['source_entries'],12010)
        self.assertEqual(value['reserve_bytes'],4*1024**3)
        self.assertFalse(value['assembly_permitted'])
        self.assertGreater(value['required_free_bytes'],value['streaming_required_free_bytes'])

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'build').mkdir()
    def tearDown(self):self.temp.cleanup()
    def test_root_reopens_readonly_and_never_overwrites(self):
        with patch.object(image,'SIZE',4096):
            fd=image.open_image(self.root,True);os.close(fd)
            with self.assertRaises(FileExistsError):image.open_image(self.root,True)
            fd=image.open_image(self.root)
            try:
                with self.assertRaises(OSError):os.write(fd,b'changed')
            finally:os.close(fd)
    def test_root_readonly_both_qemu_layers(self):
        args=image.attach(7)
        self.assertTrue(json.loads(args[1])['read-only']);self.assertTrue(json.loads(args[3])['read-only'])
        self.assertIn('serial=roko-readonly-root',args[-1])
    def test_optional_data_attachment_order_and_scope(self):
        cmd=['qemu','-nic','none','-append','rdinit=/init']
        args=runner_support.attach(cmd,7,8,'read');joined=' '.join(args)
        self.assertLess(joined.index('roko-readonly-root'),joined.index('roko-root-controller'))
        for fd,phase in [(None,'read'),(8,'none')]:
            with self.assertRaises(ValueError):runner_support.attach(cmd,7,fd,phase)
        with self.assertRaises(ValueError):runner_support.attach(cmd+['-drive','file=/dev/sda'],7)
    def test_fixed_stdin_tar_command(self):
        args=tooling.format_args(9,'probe')
        self.assertEqual(args[args.index('-d')+1],'-')
        self.assertEqual(args[-1],'/proc/self/fd/9')
        self.assertIn('no_copy_xattrs',args[args.index('-E')+1])
        with self.assertRaises(ValueError):tooling.format_args(9,'host')

class BootTests(unittest.TestCase):
    def test_switch_root_moves_mounts_not_runtime_tree(self):
        script=(source.HERE/'init.sh').read_text()
        self.assertIn('ro,noload,nodev,nosuid',script)
        self.assertIn('switch_root /newroot /usr/libexec/roko-session-init',script)
        for path in ['/proc /newroot/proc','/sys /newroot/sys','/dev /newroot/dev']:self.assertIn(path,script)
        self.assertNotIn('mkfs',script)
        self.assertIn('/usr/share/roko/root-seed/.',script)
    def test_exact_mount_and_observer_transform(self):
        data=b'\n'.join([b'$BB mount -t proc proc /proc || fail proc',b'$BB mount -t sysfs sysfs /sys || fail sysfs',b'$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs',b'exec </dev/console >/dev/console 2>&1',b'/usr/libexec/roko-storage-mount || fail storage-mount',b'/usr/bin/python3.13 -u /usr/libexec/roko-storage-observe.py >/dev/console 2>&1 &',b'storage_observer_pid=$!'])+b'\n'
        result=transform.session_init(data)
        self.assertNotIn(b'mount -t proc',result);self.assertIn(b'ROKO_DISK_ROOT_POST_SWITCH',result)
        with self.assertRaises(ValueError):transform.session_init(b'unknown')

class ReadbackTests(unittest.TestCase):
    def test_numeric_inode_only(self):
        import verify
        self.assertEqual(verify.inode_spec(12),'<12>')
        for value in [0,-1,'/etc/passwd',True]:
            with self.assertRaises(ValueError):verify.inode_spec(value)
    def test_listing_preserves_owner_mode_and_name(self):
        import verify
        value=verify.parse_listing('/14/100640/0/0/file with spaces/20/\n')[0]
        self.assertEqual(value,{'inode':14,'mode':stat.S_IFREG|0o640,'uid':0,'gid':0,'name':'file with spaces','bytes':20})
        with self.assertRaises(ValueError):verify.parse_listing('error from debugfs')
    def test_completed_bootstrap_manifest_if_present(self):
        import bootstrap
        path=source.OUT/'bootstrap.json'
        if not path.exists():self.skipTest('Root not assembled')
        manifest=json.loads(path.read_text());data=(source.OUT/'bootstrap.cpio.gz').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['initramfs_sha256'])
        self.assertEqual(bootstrap.fs.archive.inspect(gzip.decompress(data)),manifest['entries'])
        self.assertLess(len(data),4*1024**2)
        self.assertNotIn('usr/bin/cosmic-comp',manifest['entries'])
        self.assertEqual(manifest['build_id'],source.source_identity()[0])

if __name__=='__main__':unittest.main()
