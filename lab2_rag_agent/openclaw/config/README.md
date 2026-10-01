# OpenClaw integration boundary

The Lab2 OpenClaw plugin and Python Tool API are implemented in source. Configure
one agent with `tools.profile: "full"` and an explicit non-empty allowlist containing
exactly the six names in `plugin/examples/lab2-agent.json`. Do not add shell,
filesystem, browser, web-search, arbitrary MCP, raw SQL, or Gateway/admin tools.

The plugin knows only `toolApiBaseUrl` and should point to the loopback Lab2 Tool API
at `http://127.0.0.1:8090`. WeKnora runs separately at `http://127.0.0.1:8080`;
PostgreSQL and WeKnora credentials stay in the Python runtime. The operator-only
single-file ingestion CLI is not an OpenClaw capability.

This configuration is source/runbook guidance, not proof that the GB300 Gateway has
loaded the plugin or completed a live tool/model round trip. See the plugin README
for install, build, validation, and verification commands.
