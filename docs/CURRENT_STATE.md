# Current state

Phase: Foundation hardening v2

Completed:

- Separated AI Server/Workstation platforms, GPU options and concrete product configurations.
- Removed the fixed 48GB-per-GPU assumption from sizing.
- Added PASS/FAIL/UNKNOWN validation and correct unknown-data workflow routing.
- Implemented the complete Lab 3 path including configuration building,
  document search, comparison, proposal A/B and evidence verification.
- Kept missing-information handling stateless.
- Replaced the Lab 1 dataset schema with chat/tool-calling examples, family-level
  split, validation, manifest statistics and 20 review seed families.
- Unified five tool names/contracts across Labs 1/2/3 and OpenClaw boundaries.
- Added dense+sparse embedding and scored `DocumentHit` contracts.
- Limited `ModelClient` to Lab 1 evaluation and recorded ADR 010.
- Added package discovery for `agent*`, `api*` and all current packages.

Not implemented:

- Model download or training.
- PostgreSQL, Qdrant, BGE-M3, vLLM or OpenClaw runtime.
- MCP, cloud deployment or UI.
- The future 3,000-example training dataset.

Unresolved items are tracked in `docs/OPEN_DECISIONS.md`.
