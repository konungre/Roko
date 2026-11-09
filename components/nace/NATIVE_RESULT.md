# NACE host function-slice result — 2026-11-09

**Passed:** twelve fixed synthetic cases, each in a fresh process running the
actual seven-function derived NACE slice at upstream commit
`361fddf5f6885a60b6d5e0d179e0394da876df4c`. Total observed gate wall time was
0.442915487 seconds. All source and selected runtime hashes remained unchanged.
The derived source and original MIT notices were not modified.

This is a new host Python 3.12.14 qualification, not a replay of the earlier
unexecuted relocated-runtime NACE v3 proposal. It is not full NACE, general
learning, actual world actions, or Omega conversation integration.

## Evidence

- Prepared manifest SHA-256:
  `c8a4cfbb399d0aa503fb452a6c919df5b4cfe5287614ad5ab9ba282b3c5cb593`.
- Result SHA-256:
  `c224bdf12bbce0a5ec79ed3136db71f2da4f9ed9e8b3d6febd81e99148ed014c`.
- [Machine-readable result](qualification/results/host-001/result.json) and
  twelve raw worker stdout files are retained together. The full private host
  manifest and per-process receipts remain in the execution workspace.
- The controller compared each actual response to the authored Fraction oracle;
  the worker never imported that oracle. An independent readback checked every
  stdout hash, decoded result, exit status, and input/authority flags.
- All nine upstream review files were freshly fetched at the exact pin and
  matched their recorded byte counts, SHA-256 hashes, and Git blob IDs. Fresh
  AST-only regeneration reproduced the derived slice and all seven lineage
  records byte-for-byte, without importing full upstream modules.

Observed behavior included evidence reversal selecting r1 instead of r0,
selection of the second rule on equal truth, a 0.5 partial match, unchanged
predictions for action/inventory mismatch, and the expected positive/negative
reward sentinels. All twelve cases passed; no failed native case was retried.

## Resource and provenance limits

Each worker ran under prlimit with 2-second CPU, 256-MiB address-space,
32-KiB per-file output, 64-descriptor, 1-process, and zero-core limits.
The controller imposed a 5-second per-case timeout and 45-second gate deadline.
These are configured limits, not measurements of peak memory or a general
filesystem/network sandbox. The fixed reviewed worker does not launch actions,
load simulations, use network access, or persist a learned world.

The source files, host Python executable, and prlimit executable were hash-bound
before and after execution. The complete standard-library and shared-library
closure was not frozen. Therefore this result does not satisfy the older exact
relocated-runtime closure gate or qualify deployment in another environment.

## Reproduction

`qualification/run_host_slice.py prepare NEW_DIRECTORY` freezes the current
fixed cases, oracle expectations, source/runtime hashes, and bounded policy
without importing NACE. Review that manifest before using its printed digest:

`qualification/run_host_slice.py run DIRECTORY --admission DIGEST`

Invoke both with `python3 -B` from this component directory. Preparation refuses
an existing directory; execution refuses a prior attempt, altered source, changed
fixtures, changed limits, or a mismatched digest. Failed attempts and raw output
remain preserved. Six gate unit tests exercise preparation and rejection paths
without executing the native slice. The 70 portable source tests still pass;
their two path-based upstream checks skip because review files are kept outside
the published source tree. Those provenance checks were performed separately
against the freshly fetched files as described above.

## Conversation boundary

The slice consumes explicit typed 3x3 worlds, rules, and evidence updates. It
does not infer them from chat text or convert synthetic evidence into real-world
knowledge. Its output can support a controller-owned hypothetical prediction,
but a verified turn-loop API and provenance mapping are still required before
claiming genuine conversational integration. MetaMo and AIRIS's cleanup successor
remains separate; this run does not qualify either component.
