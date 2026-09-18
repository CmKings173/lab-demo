# ADR 003: LoRA/PEFT is the default adaptation boundary

## Context
The first model experiment should be reversible and resource-conscious.

## Decision
Define LoRA/PEFT configuration with BF16 as the baseline; QLoRA is a measured fallback.

## Reason
Adapters preserve the base model and make evaluation/base-versus-adapter comparison straightforward.

## Alternatives considered
Full fine-tuning or default QLoRA.

## Consequences
The real training implementation waits for GPU and optimizer benchmarks.
