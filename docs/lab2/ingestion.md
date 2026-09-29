# Ingestion Lab 2

## Current ingestion ownership

WeKnora v0.8.0 is responsible for document parsing, chunking, embedding, indexing
and retrieval. Lab2 is responsible for validating/importing structured catalog rows,
uploading only the one file explicitly supplied to its operator CLI, and maintaining the
`product_id -> product_documents -> (knowledge_base_id, knowledge_id)` mapping.
The documented upload endpoint is
`POST /api/v1/knowledge-bases/{kb_id}/knowledge/file`; poll
`GET /api/v1/knowledge/{knowledge_id}` and treat `pending`, `processing`, and
`finalizing` as non-terminal. Only `completed` is indexed-ready; `failed` and
`cancelled` are terminal non-success states.
The pinned upload API documents HTTP `409` for duplicate file content; the importer
must reconcile the returned existing knowledge record with its mapping.

The legacy custom parse/chunk/embedding/vector-store description below is superseded
by ADR 011. Lab2 must not implement a second chunker or BGE/Qdrant ingestion path.
The exact v0.8.0 request fields and local-deployment caveats are in
`references/weknora/SOURCE.md`.

Import one file after the PostgreSQL product catalog and WeKnora environment are
configured; the product ID is always explicit and is checked before upload:

```powershell
python -m pip install -e ".[lab2-runtime]"
python -m lab2_rag_agent.ingestion --product-id <catalog-product-id> --file <local-file-path>
```

The CLI does not accept directories, recurse, infer product identity from a filename,
or add an ingestion endpoint/tool to the six-tool OpenClaw boundary. It stores the
source file's SHA-256 and provider identity/status in `product_documents`. Existing
completed mappings with the same `(product_id, knowledge_base_id, SHA-256)` are reused.
Polling is finite; `pending`, `processing`, and `finalizing` remain ineligible for
search until the mapping reaches `completed`.

Each uploaded document must have a Lab2 product-document mapping so evidence can be
scoped back to a product. WeKnora owns parsing, chunking, embedding and indexing;
Lab2 stores the provider knowledge ID and does not infer page/source metadata that
the provider did not return.
