# Lab 2 OpenClaw catalog tools

This TypeScript ESM tool-only plugin registers the six Lab 2 domain tools. It forwards typed JSON to the local Python API; it does not connect to PostgreSQL or WeKnora directly. OpenClaw configuration contains only `toolApiBaseUrl`. PostgreSQL and WeKnora credentials stay in the Python runtime environment.

The basic demo has one OpenClaw agent that selects among these domain tools directly. There is no intent router or multi-agent orchestration.

The single-file WeKnora ingestion command is an operator/admin path and is not
registered in this plugin or exposed by the Tool API:

```powershell
python -m lab2_rag_agent.ingestion --product-id <catalog-product-id> --file <local-file-path>
```

The command requires both arguments, verifies the catalog product, and rejects a
directory. It reads server-side settings; the plugin receives no WeKnora or database
credential. Source build/validation does not establish that the plugin was loaded on
GB300; live Gateway/Qwen3-14B end-to-end verification remains pending.

### Restrict the Lab 2 agent to the six domain tools

Registering a six-tool plugin does not restrict the rest of OpenClaw's catalog. Merge [`examples/lab2-agent.json`](examples/lab2-agent.json) into the Gateway's existing OpenClaw configuration. For this agent, `agents.entries.lab2.tools.profile: "full"` explicitly establishes the base tool catalog even when a more restrictive global profile is configured. The non-empty `agents.entries.lab2.tools.allow` then narrows that base to exactly the six Lab 2 domain tools in the example; it does not grant other tools. As a result, `exec`/`process`, file tools (`read`, `write`, `edit`, `apply_patch`), `browser`, `web_search`/`web_fetch`, MCP tools, and Gateway/admin tools are not in this agent's allowlist. Do not add `alsoAllow` at this same scope. Higher-level deny, provider, or sandbox restrictions may still reduce the effective set. Bind the intended Lab 2 session/channel to agent ID `lab2`; do not replace unrelated Gateway configuration with the example fragment.

After applying the configuration and reloading the Gateway, inspect the effective policy and loaded plugin tools on the GB300:

```bash
openclaw sandbox explain --agent lab2 --json
openclaw plugins inspect lab2-catalog-tools --runtime --json
```

In the actual Lab 2 chat/session, `/tools verbose` shows the tools available to that active agent turn. Confirm it lists the six domain tools and none of the blocked built-ins or arbitrary MCP tools. Other global/provider/sandbox policy layers can further restrict this allowlist; an allowlist does not override a higher-level deny. See the OpenClaw [per-agent configuration](https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent), [tool policy](https://docs.openclaw.ai/gateway/config-tools/tool-policy), and [sandbox policy inspection](https://docs.openclaw.ai/gateway/sandbox-vs-tool-policy-vs-elevated) documentation.

The package pins the tested OpenClaw host and plugin SDK surface to `2026.9.6`, with TypeBox `1.1.38`. OpenClaw plugin APIs are experimental; upgrade the host pin only after running the build, plugin validation, and tests.

The npm package contains the compiled plugin, its manifest, and
`examples/lab2-agent.json`. It is built and packed separately from the Python wheel;
`node_modules/`, source tests, and generated caches are not release payloads.
See [release packaging](../../../docs/lab2/release-packaging.md) for artifact
contents and the external migration/seed assets needed at deployment.

## GB300 local demo

On the GB300, first use the existing Phase 2.1 PostgreSQL migration and seed procedure. Then install the Lab 2 runtime extra and provide the four secrets/configuration values to the Python process (for example through a permission-restricted `.env` file or the service manager's environment):

```bash
uv sync --extra lab2-runtime
export LAB2_POSTGRES_DSN='postgresql://...'
export WEKNORA_BASE_URL='http://127.0.0.1:8080'
export WEKNORA_API_KEY='...'
export WEKNORA_KNOWLEDGE_BASE_ID='...'
uv run --extra lab2-runtime uvicorn lab2_rag_agent.runtime.http.app:app --host 127.0.0.1 --port 8090
```

WeKnora remains on `127.0.0.1:8080`; the Lab 2 Tool API uses `127.0.0.1:8090` to avoid that port collision. The API intentionally binds to loopback in this runbook: it has no separate authentication layer. Keep OpenClaw Gateway on the same host. `/health` reports only HTTP process health, not database or WeKnora readiness.

Build and validate the plugin from this directory using Node `24.16+` (or `26.1+`) and OpenClaw `2026.9.6`:

```bash
npm ci
npm run plugin:build
npm run plugin:validate
npm test
openclaw plugins install .
openclaw plugins inspect lab2-catalog-tools --runtime
```

Set the plugin's non-secret `toolApiBaseUrl` to `http://127.0.0.1:8090` in the OpenClaw plugin entry configuration. The LLM provider remains configured using the operator's normal OpenClaw model-provider settings. For the demo, select the base-model alias `Qwen/Qwen3-14B`; do not configure an adapter/LoRA alias here. This phase does not alter vLLM or model-serving settings.

Smoke the API before asking the agent to use the tools:

```bash
curl -fsS http://127.0.0.1:8090/health
curl -fsS -X POST http://127.0.0.1:8090/tools/search_products \
  -H 'Content-Type: application/json' \
  -d '{"filters":{"product_type":"ai_server"},"limit":3}'
```

Then ask the configured single agent to find an AI server from the catalog, retrieve one exact product, compare two products, estimate sizing, and search mapped product documents. `compare_configurations` remains exposed; until a configuration repository exists it returns `configuration_repository_not_configured` rather than demo fixtures.
