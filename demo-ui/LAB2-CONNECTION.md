# Lab2 chat connection

The Lab2 panel sends same-origin requests to the Next.js route at
`POST /api/lab2/chat`. That server route calls the OpenClaw Gateway HTTP Chat
Completions endpoint; browser code never receives the Gateway credential.

Copy `demo-ui/.env.example` to the ignored `demo-ui/.env.local`, then set these
variables in the **Next.js server process**:

```text
LAB2_OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
LAB2_OPENCLAW_GATEWAY_TOKEN=<the OpenClaw gateway.auth.token>
```

The URL must be the Gateway origin, without a path, query, or fragment. Plain
HTTP is accepted only for a loopback Gateway; use HTTPS when the app and Gateway
are on separate hosts. The token must remain server-side. OpenClaw treats this shared token as an
owner/operator credential, so keep the Gateway and this app on loopback or a
trusted private network; do not expose the Gateway HTTP endpoint publicly.

Enable the HTTP endpoint in the Gateway configuration:

```json5
{
  gateway: {
    http: {
      endpoints: {
        chatCompletions: { enabled: true },
      },
    },
  },
}
```

The route targets agent `lab2` and model `Qwen/Qwen3-14B`. A random per-conversation
identifier is sent in OpenClaw's `user` field so turns share a dedicated agent
session. The Gateway must have
that model available, load the Lab2 plugin, and apply the six-tool agent policy
in `lab2_rag_agent/openclaw/plugin/examples/lab2-agent.json`. The plugin's
`toolApiBaseUrl` must point to the private Lab2 Tool API. PostgreSQL and WeKnora
credentials remain in their existing Python runtime; they are not copied into
the web app.

The route accepts messages up to 4,000 characters, fixes the agent, model, and
Gateway endpoint path, and bounds both the upstream response body and displayed reply.
It rejects cross-origin requests and returns
generic upstream errors. OpenClaw's HTTP chat response does not expose per-tool
events, so the panel cannot show tool timings or claim database/WeKnora health.
This source change does not verify the live Gateway, plugin policy, Tool API,
PostgreSQL, or WeKnora services. The Next.js route also does not provide
end-user authentication; keep the demo app inside a trusted network.
