# Lab2 operator ingestion

`WeKnoraDocumentIngestion` imports one explicitly selected local file for one
explicit catalog `product_id`. The service verifies the product, hashes the actual
file bytes, reuses an existing `(product_id, knowledge_base_id, SHA-256)` mapping,
uploads through the pinned WeKnora v0.8.0 file endpoint when needed, persists the
provider identity/status, and polls parsing with a finite attempt limit.

From a clean checkout, install the Lab2 runtime extra. Then run from the repository
root after configuring PostgreSQL and WeKnora settings:

```powershell
python -m pip install -e ".[lab2-runtime]"
python -m lab2_rag_agent.ingestion --product-id <catalog-product-id> --file <local-file-path>
```

Each invocation accepts one file only. Product identity is never inferred from a
filename; directories are rejected and are never traversed. A duplicate HTTP 409 is
reconciled only when the response identifies the existing knowledge record and the
configured knowledge base; otherwise the operation fails without guessing. The
API key is sent only in the server-side `X-API-Key` header and is not logged or
included in returned errors.

`pending`, `processing`, and `finalizing` remain non-terminal; only `completed`
becomes searchable. `failed`, `cancelled`, malformed responses, provider failures,
and exhausted polling limits fail safely. Tests use `httpx.MockTransport`; they do
not require a live WeKnora service. WeKnora-specific request/response fields remain
inside this ingestion boundary and do not enter shared contracts or OpenClaw tools.
