# System architecture

```mermaid
flowchart LR
  Customer[Customer requirement] --> Req[Requirement service]
  Req -->|missing| Ask[Ask for missing fields]
  Req -->|complete| Size[Sizing service]
  Size --> Catalog[Product catalog service]
  Catalog --> PG[(PostgreSQL catalog)]
  Catalog --> Validate[Rule validation service]
  Validate --> Docs[Document search service]
  Docs --> Q[(Qdrant future)]
  Docs --> Rerank[Future BGE reranker]
  Validate --> Proposal[Proposal service]
  Proposal --> Verify[Proposal verification]
  Agent[OpenClaw controlled tools] --> Catalog
  Agent --> Docs
  Model[Lab 1 model / future vLLM] --> Agent
```

## Dependency direction

`shared/contracts` depends only on Pydantic. `shared/interfaces` defines
protocols. `services` depend on contracts and interfaces. Adapters implement
interfaces. The workflow depends on services and interfaces, never on a
database client or model SDK. Lab 1 owns training concerns; Lab 2 owns catalog
and retrieval concerns; Lab 3 composes them.

## PostgreSQL versus Qdrant

PostgreSQL is authoritative for product identifiers, SKU, price, availability,
RAM, GPU count, VRAM, storage and other exact filters. Queries such as
`RAM >= 512GB`, `GPU count >= 4` and `price <= X` must remain numeric filters.

Qdrant is reserved for technical-document chunks and semantic/hybrid retrieval.
The document path may use Docling for ingestion, BGE-M3 for embeddings and a
local reranker. A vector result cannot override an exact catalog fact.

## Runtime placement

The future vLLM endpoint serves the Lab 1 model. OpenClaw is a controlled agent
surface, not a source of unrestricted SQL or arbitrary infrastructure actions.
The first phase runs all business logic with fakes and has no GPU assumption.
