import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_release as verify
from release import canonical, pack


class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root/'bundle'
        self.metadata = self.root/'metadata'
        self.signature = self.root/'signature'
        self.key = self.root/'public.pem'
        self.private = self.root/'private.pem'
        self.bundle.write_bytes(b'synthetic-release-bytes')
        self.value = {'schema': 'roko-signed-release-v1', 'release': 'fixture', 'sequence': 5,
                      'bytes': self.bundle.stat().st_size,
                      'sha256': hashlib.sha256(self.bundle.read_bytes()).hexdigest()}
        subprocess.run(['/usr/bin/openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(self.private)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/openssl', 'pkey', '-in', str(self.private), '-pubout', '-out', str(self.key)], check=True, capture_output=True)
        self.sign()

    def sign(self):
        self.metadata.write_bytes(canonical(self.value))
        message = self.root/'message'
        message.write_bytes(verify.DOMAIN + self.metadata.read_bytes())
        subprocess.run(['/usr/bin/openssl', 'pkeyutl', '-sign', '-inkey', str(self.private), '-rawin', '-in', str(message), '-out', str(self.signature)], check=True, capture_output=True)

    def check(self, floor=5):
        return verify.verify(self.bundle, self.metadata, self.signature, self.key, floor)

    def test_actual_signature(self):
        report = self.check()
        self.assertTrue(report['signature_verified'])
        self.assertFalse(report['installed'])
        self.assertFalse(report['rollback_floor_updated'])

    def test_payload_tamper(self):
        self.bundle.write_bytes(b'X' * self.value['bytes'])
        with self.assertRaisesRegex(ValueError, 'digest'): self.check()

    def test_signature_tamper(self):
        data = bytearray(self.signature.read_bytes()); data[0] ^= 1
        self.signature.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'signature'): self.check()

    def test_metadata_tamper(self):
        self.value['sequence'] = 99
        self.metadata.write_bytes(canonical(self.value))
        with self.assertRaisesRegex(ValueError, 'signature'): self.check()

    def test_rollback_even_with_valid_signature(self):
        with self.assertRaisesRegex(ValueError, 'rollback'): self.check(6)

    def test_duplicate_keys_and_noncanonical_bytes(self):
        for raw in (self.metadata.read_bytes().replace(b'"sequence":5', b'"sequence":5,"sequence":9'), json.dumps(self.value).encode()):
            self.metadata.write_bytes(raw)
            with self.assertRaises(ValueError): self.check()

    def test_symlink_and_hardlink_payload(self):
        original = self.root/'original'
        self.bundle.rename(original)
        self.bundle.symlink_to(original)
        with self.assertRaises(OSError): self.check()
        self.bundle.unlink()
        os.link(original, self.bundle)
        with self.assertRaises(ValueError): self.check()

    def test_bool_sequence_not_integer(self):
        self.value['sequence'] = True
        self.sign()
        with self.assertRaises(ValueError): self.check()

    def test_truncated_payload(self):
        self.bundle.write_bytes(b'x')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_trust_anchor(self):
        other = self.root/'other.pem'
        subprocess.run(['/usr/bin/openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(other)], check=True, capture_output=True)
        subprocess.run(['/usr/bin/openssl', 'pkey', '-in', str(other), '-pubout', '-out', str(self.key)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, 'signature'): self.check()

    def test_real_packer_to_signed_admission(self):
        assets = self.root/'assets'
        assets.mkdir()
        lock = {'schema': 'roko-release-v1', 'architecture': 'x86_64', 'release': 'fixture', 'assets': []}
        for role in ('kernel', 'initramfs', 'rootfs'):
            data = (role + '-fixture').encode()
            (assets/role).write_bytes(data)
            lock['assets'].append({'name': role, 'role': role, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        lock_path = self.root/'lock.json'
        lock_path.write_bytes(canonical(lock))
        packed = self.root/'packed.tar'
        report = pack(lock_path, assets, packed)
        self.bundle = packed
        self.value.update(bytes=report['bytes'], sha256=report['sha256'])
        self.sign()
        self.assertEqual(self.check()['sha256'], report['sha256'])
