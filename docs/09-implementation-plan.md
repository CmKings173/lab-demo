# Parallel implementation plan

## Wave 1: foundation

Documentation, shared Pydantic contracts, interfaces, deterministic fakes,
project configuration and GPU-free tests. This task implements Wave 1.

## Wave 2: lab services

Lab 1 dataset/evaluation work, Lab 2 catalog and document ingestion/search,
and Lab 3 sizing/validation/proposal hardening can proceed in parallel behind
the current interfaces.

## Wave 3: integration

Add OpenClaw controlled plugins, local service composition and a demo UI. Keep
the agent behind allow-listed domain tools.

## Wave 4: real hardware

Benchmark Qwen3-8B LoRA/PEFT, then vLLM, BGE-M3 and reranker placement on the
RTX PRO 5000. Decide whether QLoRA is necessary from measurements.

## Wave 5: end-to-end evaluation

Run the eight scenarios, harden evidence/provenance, test failure recovery and
freeze a demo baseline. Do not start these waves as part of the Phase 0-1 task.
