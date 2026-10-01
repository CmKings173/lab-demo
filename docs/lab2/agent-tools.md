# Agent tools Lab 2

## Current implementation boundary

Keep the six existing public tool names and their shared Pydantic argument/result
contracts. OpenClaw may call only these allow-listed domain operations; it must not
receive arbitrary SQL, shell, direct WeKnora SDK types, or web search. Structured
filters go through `ProductRepository` to PostgreSQL; document evidence goes through
`DocumentSearch` to WeKnora. The older tool contract notes below remain applicable
unless superseded by ADR 011.

`compare_products()` returns the requested product records and explicitly identifies
unknown catalog fields. `compare_configurations()` remains an honest
`configuration_repository_not_configured` result in the standalone Lab2 runtime;
configuration ownership belongs to Lab3.

Tool contract dùng chung gồm `search_products`, `get_product`,
`search_product_documents`, `compare_products`, `compare_configurations` và
`estimate_ai_requirements`. Product comparison thuộc catalog; configuration
comparison thuộc workflow. OpenClaw chỉ được gọi đúng sáu domain operation này;
plugin source và allowlist đã được triển khai, nhưng live Gateway/plugin loading
trên GB300 vẫn chưa được xác minh. Agent không được cấp arbitrary SQL, shell hoặc
ingestion tool. JSON schema của cả sáu tool được
sinh từ `TOOL_ARG_MODELS`; OpenClaw binding, API wrapper và gold validator cùng
validate các field như `query`, `limit`, `top_k`, configuration IDs và toàn bộ
sizing context/concurrency/training method.
