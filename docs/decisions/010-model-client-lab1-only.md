# ADR 010: ModelClient is limited to Lab 1 evaluation

## Context
The original `ModelClient` accepted `prompt: str` and returned `str`. Lab 1
needs chat messages and tool calls, while the planned OpenClaw integration will
own the model runtime for Labs 2 and 3.

## Decision
`ModelClient.complete` accepts typed chat messages and tool definitions and
returns a typed model response. It is an evaluation seam for Lab 1 only.
OpenClaw will own future Lab 2/3 runtime orchestration.

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
- Actual vLLM and OpenClaw implementations remain out of scope.
