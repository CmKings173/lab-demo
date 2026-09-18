# Lab 1: behavior fine-tuning

## Objective

Lab 1 fine-tunes behavior only: requirement extraction, missing-information
questions, structured responses, tool choice, tool-result handling and explicit
uncertainty. Catalog facts and document content remain outside model weights.
Chain-of-thought is not collected or trained.

## Dataset contract

Every `FineTuneExample` contains `example_id`, `scenario_family_id`,
`scenario_summary`, `task_type`, `difficulty`, `language`, `source_type`,
`messages`, `tools` and `labels`. Messages support `system`, `user`, `assistant`
and `tool`; assistant messages may contain typed tool calls.

Required labels are `intent`, `missing_fields`, `should_call_tool`,
`expected_tool` and `must_not_invent_product_fact`. The old `user_input` /
`expected_output` pair is not a valid primary schema.

## Split and validation

The split unit is `scenario_family_id`, never `example_id`. The deterministic
target is 80% of families for train, 10% for validation and 10% for test. A
family appearing in more than one split is a hard validation failure.

The validator rejects duplicate ids, inconsistent or duplicate family
metadata, invalid role order, undefined tools, invalid tool arguments,
unmatched tool response ids, empty messages, unsupported labels, malformed
structured output and split leakage. It emits a manifest with example, family,
task, language and split counts.

`lab1.data.seed.build_seed_examples()` currently provides 20 reviewable
families with two variants each. It is a review seed, not the planned 3,000
example production dataset.

## Runtime boundary

`ModelClient.complete(messages, tools)` exists only for Lab 1 evaluation.
OpenClaw owns future Lab 2/3 model orchestration; this repository does not add a
second partial agent runtime. See ADR 010.
