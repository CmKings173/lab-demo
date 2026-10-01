# Lab 2: catalog, RAG và agent tools

## Current architecture decision (2026-09-24)

The target stack is PostgreSQL for structured product facts, WeKnora v0.8.0 for
document ingestion and retrieval, and OpenClaw as the agent boundary over the
existing allow-listed Lab tools. Product-specific document lookup resolves
`product_id` through a Lab2 product-document mapping to WeKnora knowledge IDs.
WeKnora owns parsing, chunking, embedding, indexing and retrieval/ranking; Lab2
does not build a parallel Qdrant/BGE/Docling pipeline. Existing foundation notes
below are historical where they conflict with this decision; ADR 011 and
`references/weknora/SOURCE.md` are authoritative.

The PostgreSQL schema, curated seed, and repository adapter are now implemented;
live database integration still requires a running local PostgreSQL instance.
The WeKnora search and ingestion adapters, Lab2 runtime, FastAPI Tool API, and
OpenClaw plugin are implemented in source. Their connection to a real WeKnora and
an OpenClaw Gateway on GB300 has not yet been verified end to end.

For the basic demo, PostgreSQL owns structured/filterable facts and WeKnora owns
document evidence. One OpenClaw agent selects among the six allow-listed Lab2
domain tools directly—there is no intent router. `product_id` joins catalog rows
to imported WeKnora documents through `product_documents`. Numeric `NULL`
means UNKNOWN and stays in search candidates until evidence can resolve it.
See `infra/postgres/README.md` for local setup and seed provenance.

Lab 2 tách exact catalog plane khỏi document retrieval plane. PostgreSQL xử lý
structured catalog filters; WeKnora xử lý document parsing, chunking, indexing,
retrieval and ranking, returning evidence chunks rather than an agent answer.

Deterministic tests use fakes; the standalone runtime composes the PostgreSQL
repository and WeKnora adapter from server-side settings. The single-file ingestion
CLI is an operator path, not an agent tool. The six-tool API uses port `8090`;
WeKnora uses `8080`. Live service and GB300/OpenClaw verification remain pending.
