# Evaluation plan

## Lab 1

Measure requirement extraction accuracy, missing-information detection,
structured-output validity, tool-needed decisions, unsupported-field rate and
regression against a fixed scenario set. Compare base and adapter behavior;
record loss, training time, VRAM and configuration.

## Lab 2

Measure exact product retrieval precision/recall, document retrieval quality,
answer grounding, source correctness and explicit unknown/no-data behavior.
Numeric filter cases must be evaluated independently from semantic retrieval.

## Lab 3

Measure completed workflow rate, correct missing-information stops, sizing rule
agreement, product validity, proposal validity and zero invented specifications.
Any proposal without source evidence is a failure.

## Minimum scenarios

The test suite includes a complete GPU-free path and a missing-budget path.
The demo suite should add the eight scenarios in `docs/08-demo-scenarios.md`.
