# Lab 2: catalog, RAG and OpenClaw boundary

## Exact catalog plane

`Product` describes an AI Server or AI Workstation platform. `GPUOption`
describes a selectable GPU. `ProductConfiguration` combines a platform, GPU,
count, RAM, storage, CPU and optional estimated price. Unknown platform values
remain `None`; catalog search keeps unknown candidates for validation.

PostgreSQL is a future adapter. No database is deployed in this increment.

## Document retrieval plane

Documents are represented as source-aware chunks and returned as `DocumentHit`
objects with retrieval score, rerank score, rank and retrieval method. The
embedding contract contains both a dense vector and sparse indices/values so a
future BGE-M3 adapter can implement hybrid retrieval without changing callers.

The current fake search/reranker is deterministic and offline. Qdrant, Docling,
BGE-M3 and the BGE reranker remain future adapters.

## Controlled tools

Lab 1 examples, Lab 2 and Lab 3 share exactly these names and schemas:

- `search_products`
- `get_product`
- `search_product_documents` (supports optional `product_id`)
- `compare_products` (returns `ComparisonResult`)
- `estimate_ai_requirements`

Tools expose domain operations, never arbitrary SQL. OpenClaw is the future
agent runtime and must consume these contracts. No OpenClaw runtime, MCP or
cloud integration is implemented here.
