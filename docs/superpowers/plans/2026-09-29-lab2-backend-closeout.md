# Lab 2 backend/runtime/package closeout plan

## Goal and constraints

Finish the existing Phase 2.5 working-tree implementation without resetting,
checking out, cleaning, stashing, deleting, or overwriting unrelated work. Keep
the operator ingestion path separate from the six-tool OpenClaw/API boundary.
Do not touch `.tmp/`, `.env`, `demo-ui/`, or Lab 3 behavior. Do not commit or push.

## Implementation sequence

1. **Baseline inventory** — confirm branch/HEAD and scoped status; inspect the
   existing WeKnora, PostgreSQL mapping, runtime, plugin, and docs diffs without
   reading `.env` or enumerating `.tmp/` contents.
2. **Provider source check** — verify the pinned WeKnora v0.8.0 upload, duplicate,
   and status response contracts from the pinned official source; use only the
   existing dependency set.
3. **Ingestion contracts and tests (RED)** — add focused tests for explicit
   product/file input, product existence, byte-level SHA-256, existing mapping,
   upload, safe 409 reconciliation, bounded polling, terminal/malformed/provider
   failures, and secret redaction using `httpx.MockTransport` and fakes.
4. **Minimal ingestion service (GREEN)** — add a reusable single-file service in
   `lab2_rag_agent/ingestion/`; use existing settings/repository contracts, keep
   provider payload parsing in this boundary, persist identity/status, and never
   expose upload as an HTTP or OpenClaw tool.
5. **Thin operator CLI** — accept exactly one explicit product ID and file path;
   reject directories, verify the product before upload, use bounded polling, and
   print only a safe result/error.
6. **Environment and packaging** — add safe WeKnora placeholders to `.env.example`,
   inspect the existing nested `package-lock.json`, confirm `npm ci` reproducibility,
   and preserve `node_modules/` and `dist/` as ignored generated artifacts.
7. **Boundary regression checks** — retain search invariants and prove the shared
   contracts, Python Tool API, plugin names, and agent allowlist still contain
   exactly the same six tools; retain the honest unconfigured configuration result.
8. **Documentation reconciliation** — update the requested root, Lab 2, runtime,
   OpenClaw, Docker, and ingestion docs to distinguish source implementation from
   unverified GB300/live E2E behavior and consistently use ports 8080/8090.
9. **Verification** — run focused then full Python tests, Ruff, compileall,
   `git diff --check`, the requested npm install/build/typecheck/plugin validation/
   tests, and PostgreSQL integration only when its DSN exists. Record PASS/FAIL/
   SKIPPED with exact commands and counts.
10. **Final audit** — re-check scoped status and intended files; confirm no
    `.tmp/`, `.env`, `demo-ui/`, Lab 3, secrets, commits, or pushes were touched.

## Acceptance criteria

- One explicit product ID + one explicit local file per invocation; no directory
  traversal, filename inference, or agent/API upload capability.
- Product existence check precedes provider upload; SHA-256 uses actual bytes.
- Existing `(product, KB, SHA-256)` mappings are reused; duplicate upload is
  reconciled only with validated provider identity, otherwise fails safely.
- `pending`, `processing`, and `finalizing` poll with a finite bound; `completed`
  is ready; `failed` and `cancelled` are terminal non-success; unknown/malformed
  provider states fail without leaking credentials.
- Mapping identity and parse status are persisted; incomplete mappings remain
  ineligible for document search.
- `package-lock.json` remains present and intended for tracking; generated package
  output remains ignored.
- All requested verification results are reported truthfully; no live GB300/E2E
  success is claimed without an actual run.
