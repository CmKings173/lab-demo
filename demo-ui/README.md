# AI Engineering Console — Lab Demo UI

Next.js App Router interface for the three project labs. The three screens follow the approved Stitch references; values come from saved Lab 1 artifacts or the configured Lab 2/Lab 3 services.

## Screens and data flow

- **Lab 1 — Model development:** the server reads the fixed run manifest, final trainer state, paired Base/LoRA evaluation reports, the split exports whose SHA-256 values match the manifest, and the gold seed authoring specs. The browser receives run/evaluation summaries and the selected benchmark case, not local paths or arbitrary file contents. Token-length estimates are not displayed.
- **Lab 2 — Grounded agent:** the browser calls same-origin `/api/lab2/chat`. The Next.js server forwards the conversation to the configured OpenClaw Gateway; its credential stays server-side. The Gateway plugin calls the private Lab 2 Tool API, whose active boundary remains exactly six domain tools. The chat endpoint does not expose per-tool events or prove provider health.
- **Lab 3 — Deterministic workflow:** full user/assistant history goes to `POST /conversation/runs`. Qwen Advisor returns a natural `reply` and a cumulative, validated `requirement`. A `conversation` response displays the reply without creating a run. A `submitted` response displays the advisor reply before attaching one run and opening the existing SSE stream; after completion the UI reads the actual terminal snapshot and requests `POST /runs/{run_id}/explanation`. The structured `POST /runs` route remains available from the secondary form. No OpenClaw or model tools are used by Lab3.

The default Lab 3 `lab3_workflow.runtime.http.app:app` is an offline demonstration app: it serves topology but has no conversation model configured. Conversation and explanation calls return an explicit unavailable response. Use the real-app factory when the PostgreSQL, WeKnora, and Qwen/vLLM services are configured.

## Local setup

Use Python 3.11 or newer and Node.js compatible with the lockfile. From the repository root, install the backend runtime extras:

```powershell
python -m pip install -e ".[lab2-runtime,lab3-runtime]"
```

Configure the backend process using the placeholders in the repository-root `.env.example` (or equivalent process environment variables). Keep real credentials local. Start the Lab 2 Tool API in its own terminal:

```powershell
python -m uvicorn lab2_rag_agent.runtime.http.app:app --host 127.0.0.1 --port 8090
```

The OpenClaw Gateway must load the Lab 2 plugin and six-tool allowlist from `lab2_rag_agent/openclaw/plugin/examples/lab2-agent.json`; point its `toolApiBaseUrl` at the private Tool API. The Next.js server calls the Gateway, not the Tool API directly. See [`LAB2-CONNECTION.md`](./LAB2-CONNECTION.md) for the Gateway endpoint and server-only UI settings.

Start the configured Lab 3 API in a separate terminal:

```powershell
python -m uvicorn lab3_workflow.runtime.real_app:create_real_app --factory --host 127.0.0.1 --port 8000
```

In `demo-ui/`, install the locked JavaScript dependencies and run Next.js:

```powershell
npm ci
npm run dev
```

Open `http://localhost:3000`. The existing Next.js rewrite sends `/api/backend/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`), with explicit POST handlers for conversation and explanation. The conversation handler at `/api/backend/conversation/runs` reads `BACKEND_URL` at runtime and allows 135000 ms for the two sequential model calls; workflow SSE and other rewrites are unchanged. Set the server-only `LAB3_CONVERSATION_TIMEOUT_MS` in the Next process environment (or `demo-ui/.env.local`) only to a positive integer at most 135000. The deployment must allow the route's 150-second `maxDuration`. Genuine timeout returns sanitized HTTP 504, not a provider body. Lab 2 Gateway settings use the placeholders in `demo-ui/.env.example`.

The explicit POST handler at `/api/backend/runs/[runId]/explanation` also reads `BACKEND_URL` server-side at runtime. Next checks `afterFiles` rewrites before dynamic filesystem routes, so a precise `beforeFiles` exception maps this URL to `/api/lab3/runs/[runId]/explanation`, which re-exports the same handler. The original generic rewrite stays in `afterFiles` with its source/destination unchanged; SSE and conversation keep their existing routing. The handler forwards only `/runs/{runId}/explanation`, with a separate 75000 ms deadline and 90-second `maxDuration`. `LAB3_EXPLANATION_TIMEOUT_MS` overrides must be positive integer milliseconds at most 75000 (short overrides support regression tests). The proxy validates a bounded, safe run-ID segment, relays backend 404/409 statuses with sanitized errors, bounds JSON responses to 32 KiB, and accepts terminal explanations of at most 4000 characters. It does not forward browser credentials or follow backend redirects.

Lab3 retains the submitted `workflow_run_id` in chat state and sends it on every follow-up. The backend validates the ID against its actual run store and never automatically submits again when an existing ID is present, even if requirements remain complete. NEW CHAT clears the ID. All messages, advisor replies and terminal explanations are at most 4000 characters; oversized explanations are rejected, not truncated. Contextual user selections/confirmations can establish requirements; assistant text alone cannot.

From `demo-ui/`, run `npm test`, `npm run lint`, `npm run typecheck` and `npm run build`. For the proxy fixture, build with the Next process environment `BACKEND_URL=http://127.0.0.1:8000`. Then `npm run test:lab3-proxy` starts real production Next servers and a local FastAPI fixture, checks 32-second conversation and explanation responses, sanitized deadlines, missing/not-ready explanation semantics, SSE and run reuse, then stops its own servers. Python and free local port 8000 are required. The gate rejects a build with a different rewrite target before making requests, so it cannot accidentally test live providers. These tests use deterministic local model/data fixtures, not live Qwen, PostgreSQL or WeKnora.

Lab 1 displays an unavailable state when required artifacts are missing or their paired benchmark data is inconsistent. Split row counts are shown only when the local bytes match the manifest SHA-256; curated seed counts come from `lab1_finetune/data/gold_specs.json`. Lab 2 needs a reachable, privately hosted Gateway, plugin, Tool API, PostgreSQL, and WeKnora. Lab 3 needs PostgreSQL, WeKnora, and the configured Qwen/vLLM endpoint. This source/UI implementation does not claim those live services or an end-to-end round trip have been verified.
