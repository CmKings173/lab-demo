# Lab 2 release packaging

The Python `lab-demo` distribution and the OpenClaw plugin are separate artifacts.
Building them proves artifact contents and installability, not a live GB300 or
WeKnora deployment.

## Python distribution

From a clean checkout with Python 3.11+, install the build frontend and create a
wheel and source distribution:

```powershell
python -m pip install build
python -m build
```

Install the wheel with the runtime extra before starting the Tool API **or** the
operator ingestion CLI:

```powershell
python -m pip install "dist/lab_demo-0.1.0-py3-none-any.whl[lab2-runtime]"
python -m lab2_rag_agent.ingestion --product-id <catalog-product-id> --file <local-file-path>
python -m uvicorn lab2_rag_agent.runtime.http.app:app --host 127.0.0.1 --port 8090
```

The wheel contains the Python runtime, shared contracts, and
`lab2_rag_agent/data/catalog/products.demo.json`. The source distribution contains
the Python source and source tests. Because this is still one monorepo distribution,
the wheel also carries internal Lab 1/Lab 3 Python modules; that does not assert
Lab 3 release readiness. Neither distribution bundles the compiled
OpenClaw plugin, `node_modules/`, `.env`, or deployment-generated files. Build
outputs are intentionally ignored rather than committed.

Database setup is an **external infrastructure bundle** from this repository:
`infra/postgres/migrations/*.sql`, `infra/postgres/seed.py`, and
`infra/postgres/docker-compose.yml`, plus `.env.example` as a safe configuration
template. Apply migrations to the catalog database before running the seed or API.
The seed command `python -m infra.postgres.seed` requires the external `infra/`
directory to remain importable (for example by running from an unpacked checkout
or bundle root); it is not installed by the wheel. Supply credentials through a
permission-restricted environment. Never ship a populated `.env` file. The
WeKnora service itself is deployed and configured separately.

## OpenClaw plugin

From `lab2_rag_agent/openclaw/plugin`:

```powershell
npm ci
npm run build
npm run typecheck
npm run plugin:validate
npm test
npm pack --dry-run --json
npm pack
```

The npm package includes the compiled ESM entry point, plugin manifest,
`examples/lab2-agent.json`, package metadata, and README. The agent example
allowlists exactly six domain tools and no ingestion tool. Keep the Python Tool
API on loopback; the plugin receives only its non-secret `toolApiBaseUrl`.
Installing/loading this package in an actual OpenClaw Gateway and the
Qwen3-14B round trip on GB300 remain live verification tasks.
