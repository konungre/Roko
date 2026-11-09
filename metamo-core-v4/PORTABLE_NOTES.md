# Portable source and current qualification

This directory contains the authored v4 scoring integration source and public upstream source lock. `NATIVE_RESULT.md` supersedes the frozen pre-execution README status: one separately reviewed host attempt passed 8 processes, 8 scoring/selection cases, 21 actual scores and 128 helper/consumer checks. The failed v3 attempt remains preserved separately. None was rerun for this migration.

No upstream source snapshot, recovered Python/SWI/Janus/PeTTa installation, ELF inventory, private proof, raw log, native admission manifest or native execution permission is included. Relative paths describe the expected separately provisioned layout. Scripts must fail without that exact reviewed closure; do not substitute a local interpreter and claim equivalence.

Portable authored checks (standard-library tests plus an optional already-installed NumPy reference) can be run from `source`:

`python3 -B -m unittest test_pure`

The portable suite reports 73 tests: 69 pass and four source-reference checks explicitly skip because exact-pin upstream modules are external. If NumPy is absent, its optional reference test also skips. In the historical qualification all 73 checks passed with the verified source inputs present. Native gates and the broader state cycle are not portable-test results.
