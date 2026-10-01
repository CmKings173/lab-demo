# Lab 3 Phase 3.3 WeKnora Evidence Bridge Implementation Plan

> **For agentic workers:** Implement inline in this session, one task at a time, using test-first checkpoints. Do not commit.

**Goal:** Resolve only the three approved maximum-capacity product facts from completed, product-mapped WeKnora evidence, with deterministic parsing and auditable provenance.

**Architecture:** Keep `DeterministicProductFactResolver` for explicitly tagged offline fixtures. Add a separate Lab3 verified resolver plus a Lab3-owned provider-neutral provenance interface; its real implementation checks the existing Lab2 PostgreSQL product-document mapping repository. The real Lab3 composition directly owns/reuses existing PostgreSQL and WeKnora adapters and closes only resources it creates.

**Tech Stack:** Python 3.11, Pydantic, FastAPI lifespan, psycopg repository, existing WeKnora `httpx` adapter, pytest.

**Spec:** User-provided Phase 3.3 prompt, attachment `C:\Users\Admin\.codex\attachments\8a45fdb9-9491-4c72-aad2-7c0109725364\Pasted text.txt`.

## Global Constraints

- Preserve all pre-existing tracked and untracked changes; do not touch `.tmp/`, `.env`, `demo-ui/`, or OpenClaw.
- Do not commit/push; do not call live WeKnora or GB300; do not add a database, knowledge base, Lab2 HTTP dependency, LLM extraction, or ingestion tool.
- Resolve only `max_ram_gb`, `max_gpu_slots`, and `max_storage_gb`.
- Never treat provider score or provider `verified` metadata as a verification gate.
- A verified fact requires completed mapping provenance, strict explicit deterministic extraction, and `Product` validation.
- Conflicting accepted values yield no fact; duplicate equal values use rank then stable IDs, independent of hit order.
- Reuse `LAB3_POSTGRES_DSN`, `WEKNORA_BASE_URL`, `WEKNORA_API_KEY`, and `WEKNORA_KNOWLEDGE_BASE_ID`; keep secrets as `SecretStr` and never read `.env`.
- Keep the existing workflow state machine and executor shutdown behavior.

---

### Task 1: Narrow deterministic capacity extractor

**Files:** Create `lab3_workflow/evidence/capacity_extractor.py`; test in a new `lab3_workflow/tests/test_verified_product_facts.py`.

**Interface:** `extract_capacity_value(text: str, field_name: str) -> int | None` supports exactly the three approved fields. It accepts only explicit maximum/capacity statements, normalizes RAM/storage TB by 1024, and returns `None` for unsupported, ambiguous, installed/current, model-count, malformed, non-integral, boolean, or invalid values.

- [ ] Add parameterized examples A-H, including valid GB/TB, installed/current wording, GPU model count, unsupported unit, ambiguity, and fractional conversion.
- [ ] Run `python -m pytest lab3_workflow/tests/test_verified_product_facts.py -q` and confirm the new import/behavior fails before implementation.
- [ ] Implement narrow field-specific patterns and validate integer output with `Product.model_validate`; explicitly reject `bool`.
- [ ] Rerun the focused tests; require all parser cases to pass.

### Task 2: Provenance verifier and verified resolver

**Files:** Create `lab3_workflow/evidence/provenance.py`, `lab3_workflow/evidence/verified_product_facts.py`, and `adapters/real/weknora_provenance.py`; extend `lab3_workflow/tests/test_verified_product_facts.py`.

**Interfaces:** `EvidenceProvenanceVerifier.verify(hit: DocumentHit, expected_product_id: str) -> bool`; `VerifiedDocumentProductFactResolver.resolve(product: Product, hits: Sequence[DocumentHit]) -> list[ResolvedProductFact]` and `.apply(product, facts) -> Product`.

- [ ] Add failing provenance cases for missing mapping, wrong configured KB/product/source, non-completed status, mismatched hit identity, plus a positive completed mapping.
- [ ] Add failing resolver tests proving provider `verified=true` and score do not authorize facts, conflicts are rejected regardless of order, and equal duplicates select by `(rank, knowledge_id, chunk_id)`.
- [ ] Implement a provider-neutral verifier protocol and a real verifier backed by `PostgresProductDocumentRepository.get_by_knowledge_id(configured_kb, knowledge_id)`; require mapping KB/status/product/source and hit product/source to agree.
- [ ] Implement fact resolution only after provenance, parser, and `Product` validation; set provenance fields and neutral `confidence=1.0` (not a calibrated probability).
- [ ] Rerun focused tests; require all provenance and determinism cases to pass.

### Task 3: Workflow query and provider-bridge regression

**Files:** Modify `lab3_workflow/workflow/orchestrator.py`; extend workflow tests under `lab3_workflow/tests/`.

- [ ] Add a regression for unresolved capacity fields showing the query contains only static human-readable capacity terms and excludes generic field tokens/unrelated categories.
- [ ] Add a workflow path test covering `READ_DOCUMENTS -> APPLY_VERIFIED_FACTS -> REVALIDATE`, using a WeKnora-shaped hit and real verifier/resolver, with no injected `metadata.verified` prerequisite.
- [ ] For the real verified resolver, use static human-readable terms mapped only from unresolved approved fields and skip search when none apply. Preserve the existing offline fixture/demo query so its explicit evidence fixtures and proposal behavior remain unchanged.
- [ ] Run the focused workflow tests and ensure an empty valid result still reaches `INSUFFICIENT_PRODUCT_DATA` when unknown fields remain.

### Task 4: Real runtime settings, ownership, and lifespan

**Files:** Modify `lab3_workflow/runtime/settings.py`, `lab3_workflow/runtime/composition.py`, `lab3_workflow/runtime/real_app.py`, and `lab3_workflow/runtime/http/app.py`; extend runtime and HTTP tests.

- [ ] Add tests for environment parsing with `load_dotenv=False`, secret-safe validation failures, real runtime construction with injected fakes, owned provider closure on lifespan shutdown, and not closing externally injected search.
- [ ] Configure the existing WeKnora variables as secret-safe settings; construct the existing PostgreSQL product/document/option repositories, WeKnora search adapter, provenance verifier, and verified resolver directly in real runtime.
- [ ] Keep injected search ownership external; close internally created search/client after existing workflow executor shutdown using the existing FastAPI lifespan.
- [ ] Verify provider exception details do not leak through run snapshots, SSE, or public results; retain empty-result semantics.
- [ ] Run focused runtime and HTTP tests.

### Task 5: Documentation and complete verification

**Files:** Update only relevant Lab3 docs, including `docs/architecture.md` and `docs/current-state.md`; update `.env.example` only if a required safe placeholder is missing.

- [ ] Document that `verified=true` means configured completed mapping + deterministic rule + `Product` validation, not real-world truth; record conflict rejection, score independence, neutral confidence, and Phase 3.4 deferral.
- [ ] Run all requested Python gates and isolated Postgres tests only when `LAB2_TEST_POSTGRES_DSN` exists; never report a skipped integration test as pass.
- [ ] Run `git diff --check`; audit exact changed paths and ensure `.env`, `.tmp/`, `demo-ui/`, OpenClaw, generated files, and all pre-existing changes remain untouched.
- [ ] Report command outputs and unverified live PostgreSQL/WeKnora/GB300 status; do not commit or push.
