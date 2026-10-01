# OpenClaw integration

Lab2 source includes a TypeScript plugin, a Python Tool API, and a six-domain-tool
agent allowlist. The plugin forwards only to the local Tool API; PostgreSQL and
WeKnora credentials remain in the Python runtime. The operator ingestion CLI is
separate and is not exposed to OpenClaw.

Use `lab2_rag_agent/openclaw/plugin/README.md` for install, build, and Gateway
configuration instructions, and `lab2_rag_agent/openclaw/plugin/examples/lab2-agent.json`
for the explicit allowlist. WeKnora is expected on `127.0.0.1:8080`; the Lab2 Tool
API is `127.0.0.1:8090` and should remain loopback-only unless a separate
authentication boundary is added.

Source implementation is not live deployment verification. Loading the plugin in
the GB300 OpenClaw Gateway, Qwen3-14B tool use, and the complete Gateway → Tool API →
PostgreSQL/WeKnora → model response path remain unverified.
