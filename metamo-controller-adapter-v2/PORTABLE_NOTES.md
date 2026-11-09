# Portable controller adapter

This is the authored immutable evidence/proposal adapter with 53 pure tests. It binds the observed MetaMo v4 scoring contract, retains original evidence, rejects stale revisions and incomplete provenance, and uses the existing deterministic WorkingState checkers on detached copies. Outputs are proposals only and execute zero actions.

`python3 -B -m unittest discover -s metamo-controller-adapter-v2/source -p test_adapter.py`

These tests use explicitly marked mock receipts. They are not new native results. The separately reviewed two-process native adapter gate passed once. See NATIVE_RESULT.md for its actual scope and observed result; it was not rerun for this source migration. No native receipt, runtime inventory, admission manifest or private source is published here. Native scripts are not standalone execution authorization.
