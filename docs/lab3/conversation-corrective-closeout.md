# Lab3 conversation corrective closeout - 2026-10-01

> Historical report. Its extraction/equality language and verification counts
> are superseded by [the one-call chat experience closeout](chat-experience-closeout.md).
> This report is not verification of the current working tree or a new deployment.

Source/local verification: PASS. PostgreSQL integration: SKIPPED (no dedicated
test DSN). Fresh live GB300/Qwen/WeKnora E2E: NOT RUN. No staging, commit or push.
This is a Lab3-only follow-up to the historical chat-correction closeout.

## Root causes and final boundaries

1. Two sequential model calls could take 32 seconds, while the generic Next
   rewrite stopped the conversation at about 30 seconds. A dedicated POST route
   now owns a finite conversation-only deadline. Other rewrites/SSE are untouched.
2. A 5000-character explanation could enter history whose message contract only
   permits 4000. The service, HTTP response and browser validator now agree on
   4000; an oversized model explanation fails safely instead of being truncated.
3. Cumulative complete requirements caused ordinary follow-ups to submit again.
   A typed optional `workflow_run_id` is validated as UUID4 and looked up using
   the existing store's UUID4.hex convention before model calls. With an existing
   run, the server cannot enter the submit branch, regardless of completeness or
   advisor prose. The browser retains/sends the ID and resets it on NEW CHAT.
4. User-only extraction lost references such as "the first one" or "500".
   Extraction now sees full history, with explicit instructions that assistant
   turns are context only. Only user statements or explicit selections,
   confirmations and corrections establish facts. Newest explicit corrections
   win. The advisor must copy the validated extraction exactly.
5. Only advisor generation used the optional structured-output interface.
   Extraction now supplies its own eight-field schema through that same existing
   adapter. The opt-in flag covers both requests; no new framework/client/agent.

Lab3 still uses direct Qwen/vLLM and the deterministic Python workflow, with
PostgreSQL/WeKnora as domain sources. No OpenClaw/model tools or model-selected
products, prices, GPU sizing, proposal/evidence or execution-authority fields
were added. Manual `/runs`, topology, SSE and stored terminal results are intact.

## Exact proxy and output contracts

- `POST /api/backend/conversation/runs`: Node route, dynamic, `maxDuration=150`.
- Default and maximum `LAB3_CONVERSATION_TIMEOUT_MS`: **135000 ms** (two current
  60-second provider timeout budgets plus 15 seconds overhead). Overrides must
  be positive integer milliseconds no greater than 135000; invalid config fails
  safely. The deployment platform must permit the route duration.
- Deadline covers reading the incoming request, fetching and reading the backend
  response. Genuine expiry returns HTTP 504 / `LAB3_CONVERSATION_TIMEOUT`, with
  no raw provider body, URL, credentials or exception details.
- Fixed configured backend path only, JSON POST, no forwarded client credentials,
  no redirects, no cache; request/response bounds are 96/128 KiB respectively.
- Messages, replies and explanations: **4000 characters**. Exactly 4000 is
  accepted and can be posted in subsequent history. 4001/5000 model explanations
  fail with sanitized HTTP 502 / `LLM_EXPLANATION_FAILED`. No frontend truncation.
- Existing ID: HTTP 200 `status="conversation"`; `missing_fields` may be empty.
  Invalid ID: 422; unknown valid UUID4: 404. Neither reaches the model or submit.
  No ID plus complete validated facts: one new run, HTTP 202, server-issued ID.
- `LAB3_LLM_JSON_SCHEMA_ENABLED=false`: strict bounded plain single-object JSON,
  no `response_format`. `true`: JSON-schema `response_format` on extraction and
  advisor requests, with the same strict server validation. Extraction requires
  the exact eight nullable CustomerRequirement fields, no extra properties.
  No tools, permissive salvage or fallback retry; existing `.env` is untouched.

## Files changed in this corrective pass

Pre-existing local work was preserved. The following list is relative to the
start of this task, not a claim that every dirty file in Git belongs to this pass.

Backend (8):

- `lab3_workflow/runtime/advisor.py`
- `lab3_workflow/runtime/conversation.py`
- `lab3_workflow/runtime/http/app.py`
- `lab3_workflow/runtime/http/conversation_models.py`
- `lab3_workflow/tests/test_advisor.py`
- `lab3_workflow/tests/test_conversation.py`
- `lab3_workflow/tests/test_conversation_corrective.py` (new)
- `lab3_workflow/tests/proxy_fixture.py` (new)

Frontend (9):

- `demo-ui/app/api/backend/conversation/runs/route.ts` (new)
- `demo-ui/lib/server/lab3-conversation.ts` (new)
- `demo-ui/components/lab3/hooks/use-lab3-conversation.ts`
- `demo-ui/lib/api/lab3.ts`
- `demo-ui/lib/lab3-contracts.ts`
- `demo-ui/lib/lab3-advisor.test.mjs`
- `demo-ui/lib/lab3-proxy.test.mjs` (new)
- `demo-ui/tests/lab3-proxy.test.mjs` (new)
- `demo-ui/package.json` (test scripts only; no dependency/lockfile changes)

Templates/documentation (8):

- `.env.example`
- `demo-ui/.env.example`
- `demo-ui/README.md`
- `docs/architecture.md` (Lab3 section only)
- `docs/current-state.md` (Lab3 section only)
- `docs/lab3/overview.md`
- `docs/lab3/chat-correction-closeout.md` (historical-report notice only)
- `docs/lab3/conversation-corrective-closeout.md` (this report)

## Fresh verification

Python 3.11.9, Node 24.18.0, npm 11.16.0, Ruff 0.16.8. No uv repair attempted.
Python/Ruff/Git commands ran at the repository root; npm commands in `demo-ui/`.

| Exact command | Final result |
| --- | --- |
| `python -m pytest -o addopts= -q -rs` | PASS: **607 passed, 4 skipped, 0 failed**, 1 warning; 236.45 s |
| `python -m pytest -o addopts= lab3_workflow/tests -q -rs` | PASS: **254 passed, 2 skipped, 0 failed**, 1 warning; 4.93 s |
| `ruff check lab3_workflow adapters shared` | PASS: All checks passed |
| `npm test` | PASS: **31 passed, 0 failed/skipped** |
| `npm run lint` | PASS: exit 0, no ESLint errors/warnings |
| `npm run typecheck` | PASS: exit 0 |
| `npm run build` | PASS: exit 0; explicit conversation API route in production route table |
| `npm run test:lab3-proxy` | PASS: **4 passed, 0 failed/skipped** (parent + 3 subtests), 35.38 s |
| `git diff --check` | PASS: exit 0; only existing LF/CRLF conversion warnings |

The earlier test-first failures and initial test-format lint/Ruff failures were
corrected before these final runs. Remaining warnings: Starlette/httpx
deprecation in Python tests and Node's experimental TypeScript-strip warning.

Four PostgreSQL integrations were SKIPPED, not PASS, because
`LAB2_TEST_POSTGRES_DSN` is absent: Lab2 catalog, Lab2 document mappings, Lab3
configuration options and Lab3 WeKnora provenance.

### Real Next → FastAPI local regression

The fixture uses production `next start`, actual FastAPI conversation services
and the existing demo deterministic workflow. It does not mock Next's router or
replace the production proxy handler. Two model calls each sleep 16 seconds.
The final run returned HTTP 200 after **32093 ms**, under the 135000 ms deadline.
A separate 300 ms configured deadline produced safe HTTP 504 against a slower
backend. Existing SSE streamed `workflow.completed`; repeated follow-ups kept
the real fixture store at one run. All spawned children were stopped afterward.

The gate requires a build whose generic rewrite points to
`http://127.0.0.1:8000`, checks the built manifest before requests, and fails if
port 8000 already belongs to another server. It never redirects the fixture at
live providers. Set the Next build process `BACKEND_URL` accordingly for this
fixture; no `.env` edit is required.

### Actual React/browser smoke

Production UI opened on the local LAN with the same isolated FastAPI fixture.
One complete conversation created a terminal run with 43 actual SSE events and
the stored-result explanation. "cảm ơn" and a conceptual inference follow-up
kept `run_count=1`. NEW CHAT cleared state, and another complete conversation
created a different ID with `run_count=2`. Captured console: zero errors/warnings.
The temporary browser tab and the two owned server processes were closed.
Screenshot evidence was saved outside the repository; no screenshot artifact
was added to Git. Chrome DevTools MCP is not configured here, so the available
browser-control/console surface was used instead.

## Fresh self-review (code-review-and-quality)

Reviewed regression tests first, then source across correctness, readability,
architecture, security and performance. No remaining Required/Critical finding
within the requested scope. The skill's two supplementary checklist files are
missing locally; the complete main checklist and explicit task checks were used.

1. Existing terminal/run ID blocks run #2 in server code, not LLM prose; tested
   with two repeated POSTs for both requested follow-ups.
2. Assistant-only suggestions do not establish facts by policy; clarification
   cases keep null values in typed boundary tests. Semantic provenance remains
   an LLM behavior to verify live, not a property proved by Pydantic.
3. Full context and explicit selection/correction rules reach the extractor;
   the six examples have deterministic model-boundary tests, not live claims.
4. A 4000-character explanation is reused with an existing ID without 422;
   oversized explanations fail safely in service, response and browser tests.
5. Actual Next routing no longer kills the valid 32-second conversation at 30 s;
   genuine deadlines remain finite, including a stalled response-body test.
6. Adapter transport assertions cover both schemas when enabled and absence of
   `response_format` when disabled.
7. Model output cannot contain execution authority or unsupported domain fields;
   both user/assistant injection cases fail before advisor/submission. The server
   still checks typed facts and computes completeness itself.
8. Initial SHA-256 snapshots confirm Lab2 plugin, SOUL, chat route/hook/contracts,
   tests and docs retain their exact pre-task contents; adapter/settings,
   workflow wiring, browser fixture and generic Next config were not changed.
9. Strict parsing, response bounds and sanitized errors remain; no dependencies,
   credentials, model tools or permissive retry were introduced.
10. No staged files, generated tracked additions or weight binaries. Lockfiles
    remain tracked and unchanged. Existing `.tmp/` and transfer archive untouched.

## Limitations and Git state

- No fresh GB300/Qwen/vLLM/PostgreSQL/WeKnora E2E or schema-capability verification.
  vLLM 0.30.0 is operator-expected, not independently verified by this pass.
- Mocked contextual responses prove prompt/history/validation plumbing, not
  real Qwen accuracy or a deterministic guarantee of semantic provenance.
- Lost acknowledgement of an initial submission without a returned run ID is
  not deduplicated. Existing-ID retries are protected; explicit rerun is outside
  scope. Proxy cancellation also does not promise cancellation of an already
  running backend model/workflow task.
- Existing run-store scope remains the trusted local runtime; no new persistent
  conversation store or multi-user authorization architecture was added.
- Hosting platforms must allow the 150-second route duration. Provider HTTP
  timeouts are transport limits, not an absolute semantic latency guarantee;
  the proxy's overall deadline is still enforced.

Branch: `codex/lab2-phase2.5-openclaw-runtime`; unchanged HEAD
`8d6a4b4a9d48ccc58ec3ed7213c94d3a081c73c7`; upstream
`origin/codex/lab2-phase2.5-openclaw-runtime`, ahead/behind **0/0**.
Working tree intentionally contains prior work plus these corrections; index
empty. No reset, stash, checkout, delete of user files, staging, commit or push.
Existing `.env` and `.tmp/` were not edited. No generated files were added to Git.
