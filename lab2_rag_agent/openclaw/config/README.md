# OpenClaw integration boundary

The Lab2 OpenClaw plugin and Python Tool API are implemented in source. Configure
one agent with `tools.profile: "full"` and an explicit non-empty allowlist containing
exactly the six names in `plugin/examples/lab2-agent.json`. Do not add shell,
filesystem, browser, web-search, arbitrary MCP, raw SQL, or Gateway/admin tools.

The plugin knows only `toolApiBaseUrl` and should point to the loopback Lab2 Tool API
at `http://127.0.0.1:8090`. WeKnora runs separately at `http://127.0.0.1:8080`;
PostgreSQL and WeKnora credentials stay in the Python runtime. The operator-only
single-file ingestion CLI is not an OpenClaw capability.

## Natural advisor instructions (OpenClaw 2026.9.6)

The pinned runtime supports per-agent `workspace`, `model`, `contextInjection`
and `skills`; it does **not** support an agent `systemPrompt` property. Its
workspace bootstrap injects `SOUL.md` into the native embedded agent's system
context without a filesystem tool. The example selects `vllm/Qwen/Qwen3-14B`,
`contextInjection: "always"`, no skills, and the same exact six-tool allowlist.
No filesystem, shell, ingestion or admin capability is granted by this setup.

On the Gateway host, merge `plugin/examples/lab2-agent.json` into the existing
config (do not replace unrelated agents/provider configuration), create the
dedicated `~/.openclaw/workspace-lab2` directory, and copy
`plugin/examples/lab2-workspace/SOUL.md` there as `SOUL.md`. If a file already
exists, inspect/preserve its unrelated contents rather than blindly overwrite.
Keep this workspace separate from other agents and remove conflicting bootstrap
instructions only with operator approval. Restart/reload the existing Gateway
and start a fresh Lab2 conversation to check the updated instructions.

The prompt permits natural greetings/concepts without tool calls, requires tool
grounding for catalog/specification/price/document/sizing/comparison claims, and
explains unavailable configuration comparisons without inventing results.

Mechanism reference: the installed 2026.9.6 agent schema and bundled docs
`docs/concepts/system-prompt.md`, `docs/concepts/agent-workspace.md`, and
`docs/gateway/config-agents/workspace-and-bootstrap.md`. The regression test
validates the example against that pinned schema. See also
[workspace bootstrap](https://docs.openclaw.ai/gateway/config-agents/workspace-and-bootstrap)
and [system context](https://docs.openclaw.ai/concepts/system-prompt).

The operator reports prior live GB300 infrastructure/tool round trips verified.
This source change does not reverify live prompt loading or model behavior.
See the plugin README for build, validation and installation commands.
