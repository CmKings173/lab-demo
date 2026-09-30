# ADR 011: WeKnora owns Lab 2 document RAG

- Status: Accepted
- Date: 2026-09-24
- Supersedes: the document-retrieval portion of [ADR 004](004-postgresql-and-qdrant.md)
- Source pin: Tencent WeKnora `v0.8.0`, commit `1edcd54b43606d9079bb36650efe3f68707a79ea`; see [`references/weknora/SOURCE.md`](../../references/weknora/SOURCE.md).

## Context

Lab 2 needs exact numeric filtering for products and evidence retrieval over
unstructured manufacturer documents. The earlier Lab2 direction proposed a custom
Docling + BGE-M3 + Qdrant + reranker pipeline. WeKnora v0.8.0 provides a self-hostable
document-ingestion and knowledge-search service with a file-ID-scoped search API.

## Decision

1. PostgreSQL is the authoritative store for structured product/catalog fields and
   numeric product filters. The Lab2 product database is separate from any database
   used internally by WeKnora.
2. WeKnora is the Lab2 document/RAG backend. It owns document parsing, chunking,
   embedding, indexing, retrieval and its configured ranking pipeline. Lab2 does not
   implement a parallel Qdrant/BGE/Docling retrieval stack.
3. Pin the integration target to WeKnora `v0.8.0` at commit
   `1edcd54b43606d9079bb36650efe3f68707a79ea` until a separately reviewed ADR changes
   the version.
4. Preserve the existing `DocumentSearch` / `DocumentSearchRequest` /
   `DocumentSearchResult` contracts as the Lab2 integration boundary. The
   `WeKnoraDocumentSearch` adapter translates provider HTTP payloads;
   WeKnora-specific types must not leak into shared/domain contracts.
5. Keep `product_id -> product_documents -> WeKnora knowledge_ids` resolution in
   Lab2. Product-scoped retrieval sends the configured knowledge-base ID and only
   completed mappings for that product to `/api/v1/knowledge-search`. Unscoped
   retrieval also sends only completed mapped knowledge IDs in the configured KB;
   it never searches the whole KB. An empty eligible set is no evidence, not a
   provider outage. Provider hits outside the allowlist fail closed.
6. OpenClaw sees only allow-listed Lab domain tools. PostgreSQL remains behind the
   repository and WeKnora behind `DocumentSearch`; the agent gets no raw SQL, shell,
   direct vector-store access or web-search tool.
7. Preserve the current in-memory catalog behavior for unknown numeric fields:
   `None` remains a candidate when a numeric filter is present so a later document
   evidence step can resolve it. The PostgreSQL implementation must match this parity
   deliberately.

## Alternatives considered

- Direct Qdrant + custom parsing, embeddings and reranking in Lab2: rejected because
  it duplicates the ingestion/retrieval stack delegated to WeKnora.
- WeKnora as the agent runtime: rejected; OpenClaw remains the agent boundary.
- Replacing shared document contracts with provider payload types: rejected because
  it couples domain and Lab3 consumers to one vendor API.

## Implementation status

Implemented in source as of 2026-09-29:

- PostgreSQL catalog repository and schema;
- the `product_documents` mapping between catalog products and WeKnora knowledge IDs;
- `WeKnoraDocumentSearch`, with local result truncation because the pinned provider
  request has no `top_k` and no corpus-wide total-count response field, and with
  completed-mapping allowlisting for scoped and unscoped retrieval;
- a one-file WeKnora ingestion service and operator CLI with explicit `product_id`,
  byte-level SHA-256 reuse, safe duplicate reconciliation and bounded polling;
- actual product comparison values in `compare_products()`;
- the loopback FastAPI Tool API;
- the OpenClaw plugin with an exact six-domain-tool allowlist and no ingestion tool.

Still not live verified:

- real PostgreSQL integration unless `LAB2_TEST_POSTGRES_DSN` is present and the
  isolated integration tests run;
- communication with a live WeKnora service;
- OpenClaw Gateway/plugin loading on GB300;
- a Qwen3-14B end-to-end tool round trip through OpenClaw, the Tool API and the
  PostgreSQL/WeKnora backends.

Source implementation and deterministic contract tests are not evidence that these
deployment checks have passed.

## Consequences and compatibility gaps

- Existing fake adapters remain useful for deterministic tests alongside the source
  implementations listed above.
- The pinned `/api/v1/knowledge-search` request has no `top_k`, and its response has
  no total-count field. The adapter truncates locally and must not claim a
  corpus-wide total.
- The provider returns a single final rerank-normalized score, not distinct raw
  retrieval and rerank scores. Keep that score as provider metadata until a reviewed
  mapping exists; do not mislabel it.
- The search result schema does not guarantee `page` or `source_url`. Leave those
  citation fields unset unless actual evidence or a verified Lab2 mapping supplies
  them.
- `compare_products()` returns the compared product records and explicitly identifies
  unknown catalog fields so an agent can explain the comparison from returned data.
- WeKnora's self-host deployment can be configured with external providers. The
  project's on-prem requirement therefore also requires local model/embedding/rerank/
  storage configuration and disabling cloud/web integrations; a local container is
  not by itself proof of an offline deployment.

## Implementation boundary

The implemented source keeps PostgreSQL behind repositories, WeKnora behind the
document-search/ingestion boundaries, and OpenClaw behind the six-tool Tool API.
Ingestion remains an operator/admin path and is not an OpenClaw tool. Live service
deployment and GB300 end-to-end verification remain operational follow-up work, not
missing application source.
