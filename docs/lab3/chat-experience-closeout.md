# Lab2/Lab3 one-call chat experience closeout - 2026-10-01

Source/local verification: PASS. Real PostgreSQL integration: SKIPPED.
Fresh GB300/Qwen/OpenClaw/WeKnora E2E: NOT RUN. No staging, commit or push.

## Root causes and implemented boundaries

- Lab3 previously extracted facts, then requested an advisor turn, comparing
  the two requirements. This doubled model latency and introduced an unnecessary
  equality failure mode. Normal chat now makes exactly one completion returning
  `AdvisorTurn {reply, requirement}` through strict JSON and Pydantic validation.
  The obsolete extraction-only path/error was removed, not retained as a fallback.
- Full history reaches that completion. Assistant messages are context only;
  explicit user statements, confirmations, selections and latest corrections
  establish requirements. Unknowns remain null. These semantic rules are prompt
  policy: strict structural validation does not prove live model compliance.
- The server still computes missing required fields (`model_size_b`, `usage`,
  `budget_vnd`) and alone submits the deterministic workflow. Extra root/fact
  fields, duplicate keys, non-finite numbers, coercion, incomplete requirement
  objects, prose/fences and out-of-bound replies fail safely. No products,
  sizing, pricing or proposal decisions move into Qwen. No Lab3 tools, OpenClaw,
  MCP, LangGraph or new agents were introduced.
- `LAB3_LLM_JSON_SCHEMA_ENABLED` true/false both use one completion. True sends
  the nested eight-field schema; false uses strict plain JSON. The adapter retains
  `enable_thinking=false`, temperature zero, body limits and no permissive retry.
- Existing `workflow_run_id` lookup remains before model calls; follow-ups never
  submit a second workflow even if facts change. NEW CHAT is required for a new
  run. Tests cover thanks, conceptual clarification, changed budget and repeated
  follow-up posts.
- Both Lab2 SOUL and Lab3 advisor configure the user-facing identity:
  "Mình là nhân viên tư vấn của CNTTShop." Identity adds no new facts, preserves
  prior facts, uses no Lab2 tools, and invents no employee name/title or outside
  access. Internal model/system/tool implementation is not disclosed. These are
  configured prompt rules, not fresh evidence of real Qwen/OpenClaw behavior.
- Lab3 Enter uses `formRef.current?.requestSubmit()`; Shift+Enter keeps the native
  newline and IME composition Enter never submits. SEND, maxLength 4000 and all
  locking states remain. The helper documents both key combinations.
- The conversation proxy validates application/json, a 16 KiB error body and an
  exact error shape with known code and nonblank message <=300 characters.
  Optional FastAPI details are discarded. Messages are local constants, never
  upstream prose (even when the upstream code is known). Unknown/malformed errors
  become `LAB3_BACKEND_ERROR`. The previous safe HTTP status mapping remains.
- Local browser smoke also reproduced a pre-existing React-key collision when
  two evidence references shared a URL. Keys now include each reference's index;
  both links remain visible, with no changes to evidence, workflow or layout.

Explanation remains one separate completion using the stored terminal summary:
75000 ms timeout, maxDuration 90, max 4000 characters. Conversation remains
135000 ms / maxDuration 150. SSE and beforeFiles/afterFiles routing are unchanged.

## Verification evidence

Environment: Python 3.11.9, Node v24.18.0, npm 11.16.0, Windows PowerShell.
Used available Python directly; no uv repair or uv execution.
All final commands below completed with exit code zero.

| Directory | Exact command | Result |
| --- | --- | --- |
| Repository | `python -m pytest lab3_workflow/tests/test_advisor.py lab3_workflow/tests/test_conversation.py lab3_workflow/tests/test_conversation_corrective.py lab3_workflow/tests/test_chat_experience.py -q -o addopts=''` | PASS: 92 passed, 1 warning, 1.92 s |
| Repository | `python -m pytest -q -ra -o addopts=''` | PASS runnable tests: 626 passed; 4 SKIPPED; 1 warning; 265.29 s |
| Repository | `ruff check lab3_workflow adapters shared` | PASS: All checks passed |
| demo-ui | `npm test` | PASS: 51 tests, 0 failures, 0 skipped |
| demo-ui | `npm run lint` | PASS |
| demo-ui | `npm run typecheck` | PASS |
| demo-ui | `$env:BACKEND_URL='http://127.0.0.1:8000'; npm run build` | PASS: Next production build |
| demo-ui | `npm run test:lab3-proxy` | PASS: 7 tests, 0 failures, 0 skipped |
| lab2_rag_agent/openclaw/plugin | `npm run typecheck` | PASS |
| lab2_rag_agent/openclaw/plugin | `npm run plugin:validate` | PASS: build and plugin validation |
| lab2_rag_agent/openclaw/plugin | `npm test` | PASS: 5 tests, 0 failures, 0 skipped |
| Repository | `git diff --check` | PASS |

Expected TDD failures were observed before implementation: Python 5 failed / 1
passed; focused UI 6 failed / 7 passed; persona plugin 1 failed. The evidence-key
regression also failed before its fix, then passed. Final gates have no failures.
The final UI gates were rerun after the evidence-key fix. Python and plugin
source did not change after their successful full runs.

Four PostgreSQL tests skipped because `LAB2_TEST_POSTGRES_DSN` is absent:

- `lab2_rag_agent/tests/test_postgres_integration.py`
- `lab2_rag_agent/tests/test_product_documents_integration.py`
- `lab3_workflow/tests/test_configuration_options_integration.py`
- `lab3_workflow/tests/test_weknora_provenance_integration.py`

These are not PostgreSQL PASS or live WeKnora verification. Non-fatal warnings:
Starlette/httpx TestClient deprecation, Node's experimental stripTypeScriptTypes,
and OpenClaw's inability to append its local Temp log (validation still exited 0).

## Local browser and HTTP smoke

Chrome DevTools MCP is unavailable in this session; used the provided browser
control API, DOM/AX observations, keyboard input and console inspection instead.
The review skill's supplemental security/performance checklist files are absent;
reviewed the main five axes against source, regression tests and runtime evidence.

Fixture startup (isolated localhost only, no .env read/edit by our scripts):

```powershell
python -m uvicorn lab3_workflow.tests.browser_fixture:app --host 127.0.0.1 --port 3180
```

From demo-ui, with command-local non-secret fixture settings:

```powershell
$env:BACKEND_URL='http://127.0.0.1:3180'
$env:LAB2_OPENCLAW_GATEWAY_URL='http://127.0.0.1:3180'
$env:LAB2_OPENCLAW_GATEWAY_TOKEN='local-browser-fixture-only'
node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100
```

Browser http://127.0.0.1:3100 smoke: PASS for Shift+Enter newline, Enter send,
maxLength 4000, greeting/identity null facts, partial 14B without a run, full
requirement -> one run, locking during workflow, actual 43 SSE events, terminal
explanation and same-ID follow-up without another run. After fixing duplicate
keys, repeated run/identity follow-up had zero new console errors/warnings.
IME composition was verified by the actual component handler unit test, not
an OS-level live IME session. The smoke model and catalog are explicit test
doubles; persona and contextual semantic accuracy remain unverified live.

The production Next/FastAPI proxy regression additionally observed conversation
HTTP 200 after 32094 ms (135000 ms budget), explanation HTTP 200 after 32018 ms
(75000 ms budget), real 504 expiry, unchanged routing/SSE and no resubmission.
Owned fixture processes and the temporary smoke browser tab were closed.
Screenshot was saved outside the repository, not added to Git.

## Changed files

```text
demo-ui/.env.example
demo-ui/components/lab3/conversation-panel.tsx
demo-ui/components/proposal-panel.tsx
demo-ui/lib/lab3-composer.test.mjs
demo-ui/lib/lab3-proxy.test.mjs
demo-ui/lib/server/lab3-conversation.ts
demo-ui/package.json
docs/architecture.md
docs/current-state.md
docs/lab3/chat-correction-closeout.md
docs/lab3/chat-experience-closeout.md
docs/lab3/conversation-corrective-closeout.md
docs/lab3/overview.md
lab2_rag_agent/openclaw/plugin/examples/lab2-workspace/SOUL.md
lab2_rag_agent/openclaw/plugin/tests/advisor.test.mjs
lab3_workflow/runtime/advisor.py
lab3_workflow/runtime/conversation.py
lab3_workflow/tests/browser_fixture.py
lab3_workflow/tests/proxy_fixture.py
lab3_workflow/tests/test_advisor.py
lab3_workflow/tests/test_chat_experience.py
lab3_workflow/tests/test_conversation.py
lab3_workflow/tests/test_conversation_corrective.py
```

`demo-ui/next-env.d.ts` retains the pre-existing generated production `.next/types`
imports, not an intended manual source change. Package lockfiles/dependencies
were preserved. No live DB/WeKnora writes, schema/catalog/seed edits, CNTTShop
staging data processing, Lab1 artifact or GB300-backup changes. Existing local
`.tmp/`, `lab1-ui-artifacts.tgz` and `lab2_rag_agent/data/staging/` remain excluded.
The existing real `.env` was not inspected or edited manually. No files staged.
HEAD remains `9c6e56ae0a188f7644adda3997976ccd069c0e2b` on
`codex/lab2-phase2.5-openclaw-runtime`. No commit or push performed.

## Remaining GB300/operator verification

1. After independent review and a separately authorized checkpoint, pull source,
   rebuild UI/plugin and restart services on GB300.
2. Copy the updated Lab2 workspace SOUL.md and restart OpenClaw; restart Lab3
   with its existing real-data settings. Do not add OpenClaw to Lab3.
3. Verify the deployed vLLM JSON-schema response matches AdvisorTurn and the
   nested exact eight nullable fields; no tools, thinking disabled, temperature 0.
   Enable `LAB3_LLM_JSON_SCHEMA_ENABLED=true` only after this live test passes.
4. Run natural Lab2/Lab3 E2E: identity/greeting/concepts without tools/new facts;
   grounded catalog/sizing via exactly six Lab2 tools; contextual selections,
   corrections, strict error codes, one model completion per normal Lab3 turn,
   one workflow/SSE/explanation and same-ID follow-ups without a second run.

This correction is ready for independent source review, not a claim of fresh
GB300 live verification or a committed/pushed checkpoint.
