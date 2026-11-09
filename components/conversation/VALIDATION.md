# Local validation, 2026-11-09

- 11 Python contract tests pass (`python3 -B -m unittest discover -s components/conversation/tests -v`).
- Native probe attempted with available baseline PeTTa, Omega, and runtime root.
  Exited 2 before inference: missing native Granite executable, private ECAN source,
  baseline Python environment and baseline SWI runtime. No fallback was used.
- Recovered SWI executable initially failed loading libswipl.so.10. Supplying the
  recovered SWI and Python library directories allowed `--version` to report
  SWI-Prolog 10.0.2. This does not establish Janus or Omega compatibility.
- Real Granite conversational turns completed: **0**.
- MeTTa conversation worker: authored, **not native-qualified**.
- Tests use a fake text provider and fake attention selector. They establish input
  validation, history behavior, literal text handling, context selection and failure
  behavior only. They do not establish model quality, native ECAN or Omega execution.

The source checkpoint is suitable for review and native-runtime integration, not
for claiming the requested end-to-end conversation goal complete. No push performed.
