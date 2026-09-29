# RAG Lab 2

## Current retrieval boundary

The real document backend selected for Lab2 is WeKnora v0.8.0, called through
`POST /api/v1/knowledge-search`; it returns evidence chunks rather than an agent
answer. For a product-scoped query, resolve the product's mapped WeKnora knowledge
IDs and send them together with the configured knowledge-base ID. If the mapping is
empty, return no evidence instead of broadening the request. The older dense/sparse/
hybrid evaluation notes below are historical and do not authorize a Lab-owned
embedding, vector-store or reranking implementation.

The pinned API has no request `top_k` and no total count. The adapter therefore
truncates to the shared contract's `top_k`, and reports only the received result count.
Its `score` is a final rerank-normalized score, not separate raw retrieval and
reranking scores. Preserve it as provider metadata rather than mislabeling either
shared score field. Search results do not guarantee `page` or `source_url`; leave
them unknown unless actual hit metadata or a verified Lab2 document mapping supplies
them. See `references/weknora/SOURCE.md` for the field-by-field contract mapping.

The shared `DocumentHit` shape remains the Lab boundary; map only score/provenance
that WeKnora actually returns. Retrieval configuration is owned by WeKnora and is
evaluated through the Lab2 retrieval benchmark. Semantic result
không được ghi đè exact catalog fact; nó chỉ cung cấp evidence để resolve unknown
technical fields như max RAM/GPU/storage. Aggregate configuration price và option
price thiếu không phải document-resolvable facts.
