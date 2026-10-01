# Chat UI refinement closeout — 2026-10-01

## Scope and preserved state

This pass refines the existing Lab 2/Lab 3 screens and finishes browser error
propagation. It does not add pages, dependencies, domain tools, schemas, agents,
or business/workflow logic. Branch: `codex/lab2-phase2.5-openclaw-runtime`;
baseline HEAD: `9c6e56a`. No staging, commit, or push was performed.

Existing dirty source, tests, docs, and the untracked composer/chat-experience
tests were retained. Real `.env`, `.tmp/`, `lab1-ui-artifacts.tgz`, and
`lab2_rag_agent/data/staging/` were not edited. Both npm lockfiles are unchanged.
`demo-ui/next-env.d.ts` already differed from HEAD; after verification its text
matches the pre-task snapshot. It is generated and is not an intended commit
candidate. Build/cache outputs remain ignored.

## Error boundary

- `ApiClientError` retains `status` and `code: string | null`.
- The generic API parser accepts only the exact public error envelope, a
  nonempty message of at most 2,000 characters, and an optional uppercase code
  of at most 64 characters. Nested/extra fields and malformed values fail closed.
  Existing message-only errors keep `code=null`.
- The existing Lab 3 Next proxy still replaces upstream prose with local text
  for allowlisted codes and discards provider/validation details. Its allowlist
  is now shared with the browser's public-message formatter.
- The Lab 3 hook renders only `[KNOWN_CODE] local message`; unknown codes and
  transport exceptions use a local generic fallback, never upstream `Error.message`.
  Lab 2 does not display newly introduced codes.
- Regression tests exercise the actual proxy/API-client boundary, hook error
  handling, and rendered conversation alert, including private-marker inputs.

## Existing Lab 2 screen: before and after

Before: persistent request-path/tool-contract/unavailable-trace cards occupied the
primary layout, alongside a narrower chat and technical header facts.

After: CNTTShop Advisor chat comes first, approximately 70% of desktop content
width; the compact runtime sidebar occupies approximately 30%. On small screens
chat remains first in a single column. Runtime shows configured agent/model/data
sources, actual chat request state, and a small unavailable-trace line. It does
not claim database health, current tools, timing, or result counts.

One initially closed native `details` control, **Architecture & tools**, retains
the request path and exactly these six domain tools:

1. `search_products`
2. `get_product`
3. `search_product_documents`
4. `compare_products`
5. `compare_configurations`
6. `estimate_ai_requirements`

The configuration/not-live-trace notice remains. No ingestion tool was added.

## Existing Lab 3 graph and persona

The current SVG/layout engine is unchanged. FIT scales its rendered width/height
using both container dimensions and 16px padding per side; a ResizeObserver
updates automatic FIT on size changes. Compact controls expose Zoom out,
percentage, Zoom in, and FIT with accessible labels. Manual zoom advances by
10 percentage points, is capped at 200%, and survives event rerenders/resizing
until FIT or a topology change. Selected-node scrolling scales both coordinates
and node dimensions. Inspector, timeline, proposal, status, duration, and edges
continue using existing real event data.

The nominal manual minimum is 30%, but the lower bound permits the calculated
FIT scale: the existing wide 21-node topology cannot fit at 30% on narrow panels.
In browser checks FIT was 6% at 320px and 17% on desktop. At these small scales
labels are not comfortably readable; FIT is the all-node overview and `+` is
needed for detail. This limitation is explicit rather than changing topology or
adding a camera/layout library. No optional event-summary aggregation was added.

The existing Lab 3 conversation label is CNTTShop Advisor, with technical context
secondary. The existing one-completion advisor turn, Python submission policy,
and separate explanation request remain unchanged; no OpenClaw/tools enter Lab 3.

## Files changed by this pass

This list is specific to this pass, not all pre-existing working-tree changes.

### Modified

- `demo-ui/app/stitch-ui.css`
- `demo-ui/components/lab2/hooks/use-lab2-chat.ts`
- `demo-ui/components/lab2/lab2-chat.tsx`
- `demo-ui/components/lab2/lab2-panel.module.css`
- `demo-ui/components/lab2/lab2-panel.tsx`
- `demo-ui/components/lab2/lab2-trace-status.tsx`
- `demo-ui/components/lab3/conversation-panel.tsx`
- `demo-ui/components/lab3/hooks/use-lab3-conversation.ts`
- `demo-ui/components/lab3/workflow-topology-panel.tsx`
- `demo-ui/components/workflow-graph.tsx`
- `demo-ui/lib/api/http.ts`
- `demo-ui/lib/lab3-advisor.test.mjs`
- `demo-ui/lib/lab3-proxy.test.mjs`
- `demo-ui/lib/server/lab3-conversation.ts`
- `demo-ui/package.json` (test command only; no dependency changes)
- `lab3_workflow/tests/browser_fixture.py` (explicit local invalid-response case)
- `demo-ui/lib/lab3-composer.test.mjs` (pre-existing untracked test retained/extended)

### Added

- `demo-ui/components/lab2/lab2-runtime-panel.tsx`
- `demo-ui/components/lab3/hooks/use-workflow-viewport.ts`
- `demo-ui/lib/api/http.test.mjs`
- `demo-ui/lib/graph-viewport.ts`
- `demo-ui/lib/graph-viewport.test.mjs`
- `demo-ui/lib/lab2-layout.test.mjs`
- `demo-ui/lib/lab3-errors.ts`
- `demo-ui/lib/workflow-viewport.test.mjs`
- `docs/lab3/ui-refinement-closeout.md`

All test files referenced by `package.json` exist. Newly added/untracked test
files must be included in any future clean-checkout commit; none are staged now.

## Verification executed in this pass

Python was the installed Python 3.11.9 at
`C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe`; uv was
not used or repaired. Every PASS below returned exit code 0.

| Working directory | Exact command | Result |
| --- | --- | --- |
| repository root | `python -m pytest -q -ra -o addopts=''` | PASS: 626 passed, 4 skipped, 1 warning in 226.62s |
| repository root | `ruff check lab3_workflow adapters shared` | PASS: All checks passed! |
| `demo-ui` | `npm test` | PASS: 64 tests, 64 passed, 0 failed, 0 skipped |
| `demo-ui` | `npm run lint` | PASS: eslint exit 0 |
| `demo-ui` | `npm run typecheck` | PASS: tsc --noEmit exit 0 |
| `demo-ui` | `$env:BACKEND_URL='http://127.0.0.1:8000'; npm run build` | PASS: Next 16.3.5 production compilation, TypeScript and route generation |
| `demo-ui` | `npm run test:lab3-proxy` | PASS: 7 tests, 7 passed, 0 failed, 0 skipped |
| `lab2_rag_agent/openclaw/plugin` | `npm run typecheck` | PASS: exit 0 |
| `lab2_rag_agent/openclaw/plugin` | `npm run plugin:validate` | PASS: build succeeded; Plugin lab2-catalog-tools is valid. |
| `lab2_rag_agent/openclaw/plugin` | `npm test` | PASS: 5 tests, 5 passed, 0 failed, 0 skipped |
| repository root | `git diff --check` | PASS: exit 0; Git emitted LF/CRLF notices only |

The final UI test/lint/typecheck/build were rerun after the last source cleanup.
The proxy integration uses an actual local FastAPI fixture and production Next
server. Both ~32-second advisor and explanation responses succeeded, genuine
deadline failures returned sanitized 504s, SSE carried real local workflow
events, and terminal/missing/not-ready cases were checked.

Warnings: pytest reported Starlette's httpx/TestClient deprecation. OpenClaw
validation could not append its Windows temp log, but validation itself returned
0. Node test transpilation emitted its experimental TypeScript-transform warning.
No unrelated dependency/environment repair was attempted.

### SKIPPED integrations — not PASS

`LAB2_TEST_POSTGRES_DSN` was absent. These four PostgreSQL integration tests
skipped in the full suite:

- `lab2_rag_agent/tests/test_postgres_integration.py:71`
- `lab2_rag_agent/tests/test_product_documents_integration.py:21`
- `lab3_workflow/tests/test_configuration_options_integration.py:29`
- `lab3_workflow/tests/test_weknora_provenance_integration.py:20`

## Real-browser smoke: PASS with local fixtures only

The existing app was exercised in the Codex in-app browser against a temporary
local Next dev server and the local FastAPI browser fixture, not real providers.

- Lab 2: measured desktop chat/runtime ratio 70/30; the single architecture
  disclosure defaults closed and contains exactly six tools; Shift+Enter keeps a
  newline, Enter sends, and actual request state changes idle → sending → received.
- Lab 2/Lab 3: widths 320, 768, 1024, 1440 had no page horizontal overflow.
- Lab 3 FIT: all 21 nodes fit without horizontal graph scrolling at every width;
  zoom and FIT work, and node selection updates Inspector.
- Invalid advisor response: UI shows
  `[LLM_ADVISOR_RESPONSE_INVALID] The model could not produce a valid advisor response.`
  without the fixture's private provider marker/URL.
- A workflow produced 43 real local events; manual 37% zoom survived those events.
  Timeline/Inspector/proposal remained rendered. The fixture's incomplete proposal
  was truthfully labeled **UNVERIFIED DRAFT / PROPOSAL FAILED**, not a valid quote.
- Follow-up kept run `50a09f7802084a3082fc67ca5874e92a`. Fixture observations show
  one advisor completion per normal turn and `run_count=1`, plus a distinct
  explanation request. Browser warning/error console entries were empty.

Screenshots were saved outside the repository as `lab2-ui-refinement.jpg` and
`lab3-ui-refinement.jpg` in the task's Codex visualization directory. The temporary
fixture servers/tab were closed and the viewport override was reset afterward.

## Self-review and remaining live checks

Self-review followed `code-review-and-quality` across correctness, readability,
architecture, security, and performance. Its two referenced supplemental
checklists were missing locally; the skill's main checklist, source inspection,
regression tests and browser observations were used instead. No blocking defect
was found in this pass; the FIT label-readability tradeoff above remains visible.
This is self-review, not independent approval or a production security audit.

Still NOT verified live in this pass: PostgreSQL with a real test DSN, live
WeKnora provenance/search, OpenClaw Gateway/plugin loading on GB300, and a real
Qwen3-14B/vLLM conversation/tool round trip. Local browser/proxy fixtures do not
establish those claims. No commit. No push.
