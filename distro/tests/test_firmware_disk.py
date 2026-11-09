import binascii
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'update'))
from firmware_trials import gpt

class FirmwareDiskTests(unittest.TestCase):
    def test_primary_and_backup_gpt_crc_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'esp.img';first,blocks=gpt(path)
            self.assertEqual(path.stat().st_size,256*1024**2)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            with path.open('rb') as f:
                mbr=f.read(512);primary=bytearray(f.read(512));entries=f.read(16384)
                f.seek(-512,2);backup=bytearray(f.read(512))
            self.assertEqual(mbr[510:],b'\x55\xaa')
            for header in (primary,backup):
                self.assertEqual(header[:8],b'EFI PART')
                checksum=struct.unpack_from('<I',header,16)[0]
                struct.pack_into('<I',header,16,0)
                self.assertEqual(checksum,binascii.crc32(header[:92])&0xffffffff)
                self.assertEqual(struct.unpack_from('<I',header,88)[0],binascii.crc32(entries)&0xffffffff)
            start,end=struct.unpack_from('<QQ',entries,32)
            self.assertEqual(start,first);self.assertEqual((end-start+1)//2,blocks)
            self.assertLess(end*512,path.stat().st_size-16384)
            with self.assertRaises(FileExistsError):gpt(path)
