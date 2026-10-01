# Lab 3 Phase 3.4 — Direct Qwen Conversation Boundary

## Scope

Implement the approved Phase 3.4 brief in the current working tree. Preserve existing changes. Do not touch `.tmp/`, `.env`, `demo-ui/`, Lab 2 OpenClaw, Lab 1 production code, or workflow state-machine behavior. Do not commit or push.

## Incremental plan

- [x] Add regression tests for a strict vLLM `ModelClient` adapter using mocked HTTP transport; implement the adapter and safe settings.
- [x] Add fake-model tests for strict `CustomerRequirement` extraction, missing required fields, malformed/invalid output, and no submission on rejection; implement the narrow conversation service and response contracts.
- [x] Add server-side run requirement metadata without changing `/runs` output; test `/conversation/runs` and explanation behavior across terminal, nonterminal, and missing runs.
- [x] Extend real runtime composition and shutdown ownership; test caller-owned versus runtime-owned clients and retain offline app behavior.
- [x] Update `.env.example` and current architecture/status docs; run the complete requested Python, lint, compile, and diff gates.
- [x] Audit the final diff, protected paths, OpenClaw absence in Lab 3, and report exact live-verification limits.

## Acceptance gates

The deterministic workflow remains LLM-unaware. The model can only extract the eight approved requirement fields and explain a safe summary of a server-stored terminal result. Invalid or incomplete extraction never submits a run. No raw provider body, exception, credential, or arbitrary client-supplied result enters the explanation prompt or public error. The default offline app remains independent of PostgreSQL, WeKnora, and vLLM.
