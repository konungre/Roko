# Confirmed native PathMap limitation

This evidence was captured at PR #2 head 3ca27bb before the durable v2 reconciliation. The original qualified runtime was not changed.

A standalone authored Rust probe linked to the existing pinned PathMap build reproduced a fork-focus defect. For map keys `ab` and `abc`, prefix `xy`, and a parent focused at `xya`, the fork should enumerate `b`, `bc`. Instead it enumerated `x`, `xy`, `xyb`, `xybc`; assertion exit 101 confirms the defect. Execution was bounded to 512 MiB address space, five CPU seconds, ten wall seconds, and no core dump.

Revision: 5f2118c1d61d782a7590bac8874dcb3c94c1e0fb.
Upstream fix: 5866a4ecea1fc2bba7940572d08f8a4d68b2fed9.
Official issue: https://github.com/Adam-Vandervorst/PathMap/issues/96

This is a direct native PathMap reproducer, not an observed failure of Roko's bounded fact adapter. No proof of unreachability is claimed. Do not describe arbitrary MORK or PathMap operations as qualified. No candidate runtime was repaired or substituted. All 568 files in the previously qualified runtime manifest were rehashed and unchanged; manifest SHA-256 b480e3973455b2b6bedc903ec245b5cd0e7a8fd0e9b30a85a7a6329d54aef7d2.

Reproduction requires the previously built private runtime/toolchain; run reproduce.py with its root as the only argument. It links existing artifacts without rebuilding or downloading dependencies. The archive includes authored probe/script and logs only, no upstream binaries or sources.

At capture time, durable v2 reconciliation was blocked. The successor source is now published on main and reconciled into PR #2; current replay semantics are documented in components/conversation/DURABLE_API.md. The earlier Library HTTP 401 remains untouched. Upstream licensing is unresolved. There is no CI qualification. Prior real-native bounded tests and model restart/cancellation evidence remain intact.
