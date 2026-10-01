# Lab 3: workflow cấu hình

Lab 3 biến requirement đầy đủ thành sizing, candidate configurations, validation,
document-backed fact resolution, comparison và proposal A/B đã verify. Workflow
stateless: khi thiếu thông tin, run kết thúc với câu hỏi; caller gửi requirement
mới ở run tiếp theo.

## Conversational entry point

Lab3 uses direct Qwen3-14B/vLLM, not OpenClaw. `POST /conversation/runs`
receives full user/assistant history. The same model first extracts strictly
validated user-established facts using assistant turns only as context, then
generates `AdvisorTurn {reply, requirement}`. A user may explicitly select,
confirm or correct an assistant option (for example, "the first one" after
inference/fine-tune, or "500" after 200/500 million VND). An assistant suggestion
without user selection/confirmation is not a fact. The second requirement must
exactly match the validated extraction.
Unknown fields stay null; newest explicit user corrections take precedence.
This adds a second model request per advisor turn, not another agent or workflow.

The server computes `missing_required_fields()`: incomplete facts return
`{status:"conversation", reply, requirement, missing_fields}` without a run.
Complete facts with no `workflow_run_id` return
`{status:"submitted", reply, requirement, run_id, run_status}` after one submission.
The optional request `workflow_run_id` is validated as UUID4 and looked up in the
server run store before model calls. An existing run always returns a
`conversation` response, even with complete facts (`missing_fields` may be empty);
it cannot automatically submit another run. The browser retains/sends the ID on
follow-ups and clears it on NEW CHAT. Invalid/unknown IDs fail safely. This is not
idempotency for an initial request whose submission acknowledgement was lost.
The browser appends the actual reply before attaching the
run; topology/SSE and the manual `/runs` form are unchanged. Terminal explanation
reads the actual stored snapshot/proposal, never an invented frontend result.
Replies, messages and explanations all have a 4000-character maximum. Oversized
model explanations fail safely; the UI never silently truncates them.

Next's explicit `POST /api/backend/conversation/runs` handler has a finite
135000 ms deadline, covering both model calls (60 s each) plus 15 s overhead.
The server-only `LAB3_CONVERSATION_TIMEOUT_MS` override must be a positive integer
at most 135000. The route declares `maxDuration=150`; the deployment platform must
allow this duration. Genuine expiry returns sanitized HTTP 504. Other routes,
including workflow SSE, retain the existing rewrite and timeout behavior.

The real vLLM adapter can request the documented OpenAI-compatible JSON-schema
`response_format` for both requirement extraction and the advisor turn, with
thinking disabled and no tools. The extractor schema requires the exact eight
nullable `CustomerRequirement` fields, with no additional properties.
`LAB3_LLM_JSON_SCHEMA_ENABLED=false` is the safe default: plain single-object JSON
with strict server validation. Set it to `true` only after verifying support on
the deployed vLLM version; no existing `.env` is changed by this correction.
All outputs are validated again: one bounded JSON object only, no prose/fences,
duplicate keys, non-finite numbers, extra fields, coerced types or incomplete
advisor requirements. Other injected ModelClient implementations may use plain
JSON, subject to the same strict validator; there is no permissive provider retry.

The operator expects vLLM 0.30.0, but this correction has not verified the live
version or structured-output support. Validate this format on GB300 before
opting in; opted-in unsupported
providers fail safely rather than silently retrying or relaxing the contract. Reference:
[vLLM structured outputs](https://docs.vllm.ai/en/stable/features/structured_outputs/).
Prior live infrastructure checks are operator-reported, not fresh verification
of this correction. Check greeting, clarification, partial facts, complete facts,
one run/SSE, actual terminal explanation and explicit corrections on the host.
Context-selection tests exercise the typed model boundary with deterministic
responses; they do not prove real Qwen semantic accuracy.
