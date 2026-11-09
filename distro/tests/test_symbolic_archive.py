"""Regression for the actual guest's root-owned runtime accessibility failure."""
import importlib.util
from pathlib import Path
import stat
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_probe import baseline

class SymbolicArchiveTests(unittest.TestCase):
    def test_user_home_ownership_header(self):
        raw=baseline.entry('home/roko',b'',stat.S_IFDIR|0o700,1)
        raw=raw[:22]+b'000003e8000003e8'+raw[38:]
        raw+=baseline.entry('TRAILER!!!',b'',0,2)
        row=baseline.inspect(raw)['home/roko']
        self.assertEqual((row['uid'],row['gid'],row['mode']&0o777),(1000,1000,0o700))

    def test_bounded_probe_memory_validation(self):
        from run_probe import run
        for size in (True,0,255,2049,65536):
            with self.assertRaises(ValueError):run('/missing','/missing','/missing','/missing',memory_mib=size)
