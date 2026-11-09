"""Repository layout checks; no native runtime or external dependency required."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MetaMoLayoutTests(unittest.TestCase):
    def test_retired_core_is_not_published(self):
        self.assertFalse((ROOT / 'metamo-core-v3').exists())
        manifest = json.loads((ROOT / 'PUBLICATION_MANIFEST.json').read_text())
        self.assertFalse(any(p.startswith('metamo-core-v3/') for p in manifest['files']))

    def test_active_consumer_dependencies_remain(self):
        from components.omega_learning.metamo_turn import RuntimeBinding
        imports = RuntimeBinding(ROOT).imports()
        self.assertTrue(imports)
        self.assertEqual(Path(imports[0]), ROOT / 'metamo-core-v4/source/numeric_compat.metta')
        self.assertTrue(Path(imports[0]).is_file())

    def test_attribution_and_history_remain(self):
        core = ROOT / 'metamo-core-v4'
        self.assertIn('MIT License', (core / 'upstream/LICENSE').read_text())
        self.assertTrue((core / 'NATIVE_RESULT.md').is_file())
        self.assertTrue((core / 'source/test_finalization.py').is_file())


if __name__ == '__main__':
    unittest.main()
