# AI Engineering Console — Lab Demo UI

Next.js App Router interface for the three project labs. The three screens follow the approved Stitch references; values come from saved Lab 1 artifacts or the configured Lab 2/Lab 3 services.

## Screens and data flow

- **Lab 1 — Model development:** the server reads the fixed run manifest, final trainer state, paired Base/LoRA evaluation reports, the split exports whose SHA-256 values match the manifest, and the gold seed authoring specs. The browser receives run/evaluation summaries and the selected benchmark case, not local paths or arbitrary file contents. Token-length estimates are not displayed.
- **Lab 2 — Grounded agent:** the browser calls same-origin `/api/lab2/chat`. The Next.js server forwards the conversation to the configured OpenClaw Gateway; its credential stays server-side. The Gateway plugin calls the private Lab 2 Tool API, whose active boundary remains exactly six domain tools. The chat endpoint does not expose per-tool events or prove provider health.
- **Lab 3 — Deterministic workflow:** chat history goes to `POST /conversation/runs`. A `needs_information` answer is displayed without creating a run. A `submitted` answer opens the existing SSE stream; after completion the UI reads the terminal snapshot and requests `POST /runs/{run_id}/explanation`. The structured `POST /runs` route remains available from the secondary form.

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

Open `http://localhost:3000`. The existing Next.js rewrite sends `/api/backend/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`), so Lab 3 requests remain same-origin in the browser. Lab 2 Gateway settings are read by the Next.js server from `demo-ui/.env.local`; use the placeholders in `demo-ui/.env.example`.

Lab 1 displays an unavailable state when required artifacts are missing or their paired benchmark data is inconsistent. Split row counts are shown only when the local bytes match the manifest SHA-256; curated seed counts come from `lab1_finetune/data/gold_specs.json`. Lab 2 needs a reachable, privately hosted Gateway, plugin, Tool API, PostgreSQL, and WeKnora. Lab 3 needs PostgreSQL, WeKnora, and the configured Qwen/vLLM endpoint. This source/UI implementation does not claim those live services or an end-to-end round trip have been verified.
