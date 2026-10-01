# Lab2/Lab3 chat correction closeout - 2026-10-01

> Historical report. The two-call architecture and test counts below are
> superseded by [the one-call chat experience closeout](chat-experience-closeout.md).

Historical first-pass verification below predates the Lab3-only corrective pass.
Its counts and user-only extraction/one-run-per-request wording are not the final
Lab3 contract. See [the current corrective closeout](conversation-corrective-closeout.md)
for contextual user confirmation, existing-run protection, the 4000-character
contract, selective proxy timeout and fresh verification. Lab2 is unchanged by
that follow-up.

Source validation and local browser smoke: PASS. Live GB300 verification of this
correction: NOT RUN. No commit or push. Branch
`codex/lab2-phase2.5-openclaw-runtime`; unchanged HEAD
`8d6a4b4a9d48ccc58ec3ed7213c94d3a081c73c7`.

## Root causes and corrected architecture

Lab2 depended on browser `crypto.randomUUID()`, unavailable on ordinary HTTP LAN.
Its server required a client-generated conversation UUID, used a bare model
header, and compared Origin against Next's synthesized internal request hostname.
The latter also rejected legitimate LAN requests even after UUID repair.

Lab3 was a user-only JSON extractor followed by a fixed missing-fields question:
no conversational reply contract, no assistant context for clarification, and
no initial advisor reply on workflow submission.

Lab2 remains Browser → same-origin Next route → OpenClaw → vLLM/Qwen → exactly
six tools → private Tool API → PostgreSQL/WeKnora. Node now issues the first UUID;
later requests validate/reuse it. Rendering uses a local ref counter. The route
uses `vllm/Qwen/Qwen3-14B`, validates Origin against the actual Host (not forwarded
Host), blocks cross-site requests, bounds payloads/replies and sanitizes failures.
Failed sends remove only the failed optimistic bubble and restore the draft.

Lab3 remains Browser → Next rewrite → FastAPI → direct Qwen Advisor → validated
CustomerRequirement → deterministic workflow → actual stored result/explanation.
The same existing model client first validates cumulative user-only facts, then
generates a contextual reply with full user/assistant history. The second
requirement must exactly equal those facts; assistant text cannot change them.
This is two requests to one model, not another agent or workflow layer.

## Instructions and final contract

OpenClaw **2026.9.6** instructions use its supported per-agent workspace bootstrap:
`examples/lab2-workspace/SOUL.md`, with `contextInjection="always"`, no skills,
the qualified model and unchanged six-tool allowlist. The installed pinned agent
schema validates the example. No unsupported `systemPrompt` property is added.
See `lab2_rag_agent/openclaw/config/README.md` for installation and primary
documentation. Greetings/concepts need no tools; concrete domain claims need
tool grounding, including truthful unavailable configuration comparisons.

`AdvisorTurn` contains `reply: str` and `requirement: CustomerRequirement`.
All eight requirement fields must be present; unknowns are null. Unsupported
fields, coercions, duplicate keys, non-finite values, prose/fences/trailing junk,
blank/oversized replies, oversized bodies and truncated model output fail safely.
The server computes required fields (model size, usage, budget):

```text
incomplete → 200 {status:"conversation", reply, requirement, missing_fields}
complete   → 202 {status:"submitted", reply, requirement, run_id, run_status}
```

Only complete validated facts submit one run per request. The frontend appends
the backend reply before attaching the run. Manual `/runs`, topology, SSE and
actual terminal snapshot/explanation are preserved. No ready_to_run field,
model tools, OpenClaw in Lab3, model-selected products or workflow bypass.

The deployed vLLM version/schema capability is not recorded in this checkout.
`LAB3_LLM_JSON_SCHEMA_ENABLED=false` defaults to bounded strict JSON validation.
Verified deployments may opt in to the documented JSON-schema response_format;
both paths get identical server validation. No permissive retry of bad output.

## Verification (Python 3.11.9; Node 24.18.0)

Commands were executed in the repository root unless indicated otherwise.
`-o addopts=` exposes exact counts rather than the configured quiet default.
No uv repair was attempted.

| Command | Final result |
| --- | --- |
| `python -m pytest lab3_workflow/tests -o addopts= -q -rs` | PASS: 233 passed, 2 skipped, 0 failed; 1 deprecation warning |
| `python -m pytest lab2_rag_agent/tests shared/tests -o addopts= -q -rs` | PASS: 172 passed, 2 skipped, 0 failed; 1 deprecation warning |
| `python -m pytest -o addopts= -q -rs` | PASS: 586 passed, 4 skipped, 0 failed; 1 warning; 222.95 seconds |
| `ruff check lab2_rag_agent lab3_workflow shared adapters infra` | PASS: All checks passed |
| `git -c core.safecrlf=false diff --check` | PASS: no output |
| UI: `npm test` | PASS: 26 passed, 0 failed/skipped |
| UI: `npm run lint` | PASS: no errors or warnings |
| UI: `npm run typecheck` | PASS: exit 0 |
| UI: `npm run build` | PASS: production build and TypeScript completed |
| Plugin: `npm run build` | PASS: exit 0 |
| Plugin: `npm run typecheck` | PASS: exit 0 |
| Plugin: `npm run plugin:validate` | PASS: Plugin lab2-catalog-tools is valid |
| Plugin: `npm test` | PASS: 5 passed, 0 failed/skipped |

Compileall initially FAILED on Windows cache write permissions; redirecting to
the OS temp directory also FAILED on permissions. The successful final command
used an ignored workspace cache and excluded third-party JavaScript dependencies:

```powershell
$env:PYTHONPYCACHEPREFIX='D:\project\lab demo\.pytest_cache\compile-20261001'
python -m compileall -q -x 'node_modules|dist' lab2_rag_agent lab3_workflow shared adapters infra
```

Final compileall: PASS, exit 0. No application logic was changed to fix permission
failures. Frontend tests emit a Node experimental TypeScript transformation
warning; Python emits one Starlette/httpx deprecation warning. OpenClaw validation
passes but warns that its Windows temp log file is not writable.

PostgreSQL: explicitly SKIPPED (no LAB2_TEST_POSTGRES_DSN), covering Lab2 catalog,
product_documents, Lab3 configuration options and WeKnora provenance integration.
Mock/provider-boundary tests do not prove live WeKnora availability.

## Real browser, isolated fixture

Next production server was tested over plain HTTP LAN. The development server's
LAN resource policy blocked its dev resources; production smoke required no
security/config relaxation. Fixture startup commands:

```powershell
python -m uvicorn lab3_workflow.tests.browser_fixture:app --host 127.0.0.1 --port 3180
python -m uvicorn lab3_workflow.tests.browser_fixture:app --host 127.0.0.1 --port 8000
# In demo-ui, process-only settings (not an .env edit):
$env:LAB2_OPENCLAW_GATEWAY_URL='http://127.0.0.1:3180'
$env:LAB2_OPENCLAW_GATEWAY_TOKEN='browser-test-fixture-token'
npm run start -- --hostname 0.0.0.0 --port 3101
```

Lab2: first reply, shared server-issued UUID across turns, qualified model header,
sanitized injected Gateway failure, restored draft and successful retry verified.
Lab3: greeting/partial/clarification returned replies without runs; full history
reached the model boundary; complete facts created exactly one stored run; actual
SSE delivered 43 events and terminal snapshot/explanation rendered. The final
default plain_json mode was retested after the schema opt-in correction.
Console warnings/errors in the final production smoke: none observed.

The fixture uses the real HTTP/conversation/vLLM adapter/workflow paths but a
test-only model endpoint and the existing in-memory demo catalog. Its terminal
domain state was `proposal_failed`, displayed as an unverified draft rather
than disguised as a successful proposal. This is NOT a live GB300 E2E claim.

## Review, preserved boundaries and remaining deployment work

Five-axis self-review used code-review-and-quality after testing; no unresolved
correctness/security blocker found in this scoped source change. Incremental
tests caught the extra LAN origin defect and the unsafe assumption that a
deployed vLLM would necessarily support schema enforcement.

Secrets remain server-side; .env is unchanged. Only non-secret configuration was
added to .env.example. No LangGraph/MCP/new agent/DB/vector DB or arbitrary tools.
Lab1 logic/artifacts and deterministic workflow selection, sizing, validation,
pricing, evidence and proposal code were not modified. Both package-lock files
remain tracked and unchanged. Generated node_modules/dist/.next/caches remain
ignored. No staging, commit, push, reset, checkout, stash or deletion of user work.
The existing next-env.d.ts generated change predates this task; .tmp/ and the
transfer tarball remain untouched and untracked.

Deploy the backend and frontend together because the conversation response
contract changed. On GB300, merge the dedicated Lab2 agent config, install its
SOUL.md, reload the Gateway and start a new session. Verify actual greeting vs
factual tool-grounded answers, configuration-unavailable behavior, and exactly
six tools. Verify Lab3 greeting/clarification/corrections, cumulative facts,
one run/SSE and actual terminal explanation with real Qwen/PostgreSQL/WeKnora.
Only enable JSON schema after checking the deployed vLLM version and request.
Prior infrastructure successes are operator-reported, not re-executed here.

Intentional limits: two model requests add latency; semantic extraction/reply
quality still depends on Qwen and cannot be proven by fixtures; no automatic
workflow retry or fake successful proposal; Lab2 tool trace remains unavailable
from the HTTP final-answer endpoint; trusted-network demo still lacks end-user
authentication; configuration comparison availability remains repository-dependent.

## Intended changed files

```text
.env.example
adapters/real/vllm_chat.py
demo-ui/LAB2-CONNECTION.md
demo-ui/README.md
demo-ui/components/lab2/hooks/use-lab2-chat.ts
demo-ui/components/lab3/conversation-panel.tsx
demo-ui/components/lab3/hooks/use-lab3-conversation.ts
demo-ui/lib/api/lab3.ts
demo-ui/lib/lab2-contracts.ts
demo-ui/lib/lab3-contracts.ts
demo-ui/lib/server/openclaw-lab2.ts
demo-ui/lib/lab2-chat.test.mjs
demo-ui/lib/lab3-advisor.test.mjs
demo-ui/package.json
docs/architecture.md
docs/current-state.md
docs/lab3/overview.md
docs/lab3/chat-correction-closeout.md
lab2_rag_agent/openclaw/config/README.md
lab2_rag_agent/openclaw/plugin/examples/lab2-agent.json
lab2_rag_agent/openclaw/plugin/examples/lab2-workspace/SOUL.md
lab2_rag_agent/openclaw/plugin/package.json
lab2_rag_agent/openclaw/plugin/tests/advisor.test.mjs
lab3_workflow/runtime/advisor.py
lab3_workflow/runtime/composition.py
lab3_workflow/runtime/conversation.py
lab3_workflow/runtime/http/app.py
lab3_workflow/runtime/http/conversation_models.py
lab3_workflow/runtime/settings.py
lab3_workflow/tests/browser_fixture.py
lab3_workflow/tests/test_advisor.py
lab3_workflow/tests/test_conversation.py
lab3_workflow/tests/test_vllm_chat.py
```

`demo-ui/next-env.d.ts` is existing/generated local state, not an intended manual
source edit. No runtime or UI deployment was performed in this task.
