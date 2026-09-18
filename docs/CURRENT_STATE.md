# Current state

Phase: Foundation / Phase 0+1

Completed in this task:

- Project scope and architecture documentation.
- Typed Pydantic shared contracts and stable interfaces.
- In-memory catalog, fake documents, embeddings, reranker and model adapters.
- Deterministic sizing, rule validation, proposal and workflow skeletons.
- Lab 1 dataset/config/evaluation/train/merge skeletons.
- Controlled catalog tool contract for future OpenClaw integration.
- GPU-free integration and missing-information tests.

Not started:

- Real model training and GPU benchmarks.
- Production RAG, PostgreSQL, Qdrant or vLLM integration.
- OpenClaw runtime and MCP.
- Demo UI and deployment automation.

Open decisions are listed in `docs/decisions/` and include exact Qwen3 variant,
OpenClaw version, retrieval parameters, sizing formulas, catalog source and
frontend framework.
