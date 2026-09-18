# Project scope

## Business problem

The system is an on-prem assistant for advising customers on an AI Server or
AI Workstation. A request such as “I need a local 32B model for 5-10 users,
light fine-tuning and a 350 million VND budget” must become a traceable,
evidence-backed proposal.

The assistant must extract requirements, identify missing mandatory data, size
resources with code, search structured catalog data, retrieve technical
evidence, reject unsuitable products, compare options, generate a proposal and
verify it before completion.

## In scope

- AI Server and AI Workstation only.
- One future on-prem workstation with an NVIDIA RTX PRO 5000 48GB target.
- Lab 1: Qwen3-8B LoRA/PEFT dataset, training and evaluation contracts.
- Lab 2: PostgreSQL product catalog, document retrieval and controlled tools.
- Lab 3: deterministic workflow contracts and orchestration seams.
- CPU-only fake adapters and tests for every boundary.

## Non-goals for Phase 0-1

No production fine-tuning, production RAG, live vLLM, live Qdrant, live
PostgreSQL, OpenClaw runtime, MCP, LangGraph, cloud inference, SaaS, Tavily,
full ITShop catalog ingestion or UI delivery is included here. No laptop or
other product category is introduced.

## Labs

Lab 1 teaches behavior such as requirement extraction, missing information,
tool decisions and structured output. Catalog facts remain Lab 2 data.

Lab 2 separates exact product facts in PostgreSQL from technical-document
evidence in a future Docling/BGE-M3/Qdrant pipeline.

Lab 3 enforces the sequence from requirement completeness through sizing,
product validation, proposal generation and proposal verification.

## Hard rules

- Required fields are model size, usage and budget.
- Missing required information stops product search.
- LLM output never decides final sizing or final validity.
- Unknown product data is returned as `unknown`, never inferred.
- Numeric catalog constraints are evaluated by repository code, not vectors.
