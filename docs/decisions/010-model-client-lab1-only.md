# ADR 010: ModelClient is limited to Lab 1 evaluation

## Context
The original `ModelClient` accepted `prompt: str` and returned `str`. Lab 1
needs chat messages and tool calls, while OpenClaw is the selected model-runtime
boundary for Labs 2 and 3.

## Decision
`ModelClient.complete` accepts typed chat messages and tool definitions and
returns a typed model response. It is an evaluation seam for Lab 1 only.
OpenClaw owns the Lab 2/3 runtime boundary. Its six-tool plugin and Tool API are
implemented in source, while live GB300 Gateway/plugin loading and a Qwen3-14B
end-to-end tool round trip remain unverified.

## Reason
This keeps tool-calling evaluation realistic without building a second partial
agent runtime or coupling domain workflow code to vLLM.

## Alternatives considered
- Keep `prompt -> str`: rejected because it cannot evaluate tool-calling data.
- Use `ModelClient` as the full agent runtime: rejected because it duplicates
  the selected OpenClaw boundary.

## Consequences
- Fake and future vLLM adapters implement the same chat/tool contract.
- Labs 2/3 call controlled domain tools and do not call `ModelClient` directly.
- A separate vLLM-backed `ModelClient` for Labs 2/3 remains out of scope. The
  OpenClaw source integration exists, but deployment and live model verification do not.
