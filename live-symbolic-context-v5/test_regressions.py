"""Rerun inherited endpoint/reconciliation tests against the new disabled path."""
import importlib.util
from pathlib import Path
import sys,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'omega-baseline/desktop/live-request-media'),str(HERE.parent/'production-hardening-002')]
import test_live_request as original
import test_candidate_reconciliation as reconciliation
import test_result_contract as result_contract
spec=importlib.util.spec_from_file_location('live_context_regression_candidate',HERE/'source/live_controller.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
reconciliation.candidate=candidate
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(original),
                         unittest.defaultTestLoader.loadTestsFromModule(reconciliation),
                         unittest.defaultTestLoader.loadTestsFromModule(result_contract)])
if __name__=='__main__':
    with patch.object(original,'controller',candidate),patch('subprocess.Popen',side_effect=AssertionError('Native process forbidden')),patch('subprocess.run',side_effect=AssertionError('Native process forbidden')),patch('os.execve',side_effect=AssertionError('Native exec forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
