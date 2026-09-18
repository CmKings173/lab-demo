# ADR 008: Rule-based sizing in the foundation

## Context
Sizing is a safety-critical decision for recommendations and no benchmark data exists yet.

## Decision
Use a deterministic, documented rule with explicit assumptions and low confidence.

## Reason
The LLM must not freely calculate VRAM, RAM or GPU count.

## Alternatives considered
Ask an LLM to estimate or wait for production benchmarks.

## Consequences
The formula is a replaceable service; production sizing requires measured validation.
