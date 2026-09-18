# Lab 2: catalog, RAG and local agent

## Two data planes

The product catalog is a PostgreSQL-backed exact data plane. It contains
product id, SKU, name, manufacturer, category, CPU, supported GPU, maximum GPU
count, VRAM, default and maximum RAM, storage, power, form factor, price,
availability and source URLs.

Technical documents form a separate retrieval data plane. Datasheets, product
pages, PDFs, guides and descriptions are ingested with Docling, chunked with
source/page metadata, embedded with BGE-M3, searched in Qdrant and optionally
reranked. Every answer must retain source references.

## Controlled tools

The agent receives domain operations, not SQL:

- `search_products(filters)` for exact numeric and categorical filters.
- `get_product(product_id)` for one authoritative record.
- `search_product_documents(query, product_id)` for evidence retrieval.
- `compare_products(product_ids)` for a bounded comparison.

The Phase 1 `CatalogTools` class rejects the idea of arbitrary SQL and the
document tool reports that its production backend is not configured. Unknown
fields remain unknown.

## OpenClaw

OpenClaw is an integration boundary for the future local agent. Its skills and
plugins must call the controlled contracts and must not create a direct SQL
channel. Production agent policy, NemoClaw/OpenShell and vLLM integration are
future waves.
