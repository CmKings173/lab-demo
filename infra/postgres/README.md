# PostgreSQL boundary

PostgreSQL is Lab 2's structured, filterable product catalog. WeKnora will supply
document evidence; one OpenClaw agent will choose domain tools directly. There is
no intent router. The shared `product_id` is the join key between catalog rows and
future WeKnora documents. `NULL` means **UNKNOWN**, not zero. Numeric filters keep
unknown candidates for later evidence resolution; a matching row is not proof that
an unknown specification meets the requested threshold.

Local development (from the repository root):

1. Copy `.env.example` to `.env` and set a local-only PostgreSQL password there.
   `.env` is Git-ignored; never commit it. The same file holds the DSN used by
   the seed command and the isolated PostgreSQL integration test.
2. Install the optional PostgreSQL dependencies:
   `python -m pip install -e ".[postgres]"`.
3. Start the database with
   `docker compose --env-file .env -f infra/postgres/docker-compose.yml up -d`.
4. The first database initialization applies all numbered SQL migrations.
   For an existing volume, apply any unapplied migrations explicitly with `psql`;
   Compose init scripts do not rerun on an existing volume. The current mapping
   migration is `003_create_product_documents.sql`.
5. Run `python -m infra.postgres.seed`. It loads `LAB2_POSTGRES_DSN` from the
   repository-root `.env`, validates the JSON seed, and upserts by `id`.

The seed at `lab2_rag_agent/data/catalog/products.demo.json` contains ten curated
product-page entries from [CNTTShop's Workstation AI category](https://cnttshop.vn/workstation-ai-pc-ai).
Only directly supported structured values are populated. Two workstation pages
explicitly state 200 and 800 million VND as their configuration cost, so these
values are stored as `listed_price_vnd`, never as `base_price_vnd`. They are
source-page figures, not binding/current quotes; confirm with the seller before
purchase. `base_price_vnd` remains `NULL` without a separately sourced chassis
price, so Lab 3 cannot double-count the listed configuration. For a budget query,
use `max_listed_price_vnd`; a row with `listed_price_vnd = NULL` remains an UNKNOWN
candidate, **not** a verified within-budget match. An answer must distinguish
verified prices from unknowns. Unified memory in compact AI PCs is not silently mapped to
installed system RAM or discrete GPU VRAM. Recheck source pages before using price
or availability in a live presentation. `catalog_order` preserves insertion order
across both adapters.

The database and seed default `base_price_includes` to `["chassis"]`, matching
the shared `Product` contract. A source-confirmed different inclusion set can
override it. Frozen Lab 1 tool definitions and product-result models live in
`lab1_finetune/data/frozen_contracts.py` and its JSON schema snapshot; expanding
Lab 2's runtime filter must not change Lab 1's frozen hashes.

For a real adapter parity check, `LAB2_TEST_POSTGRES_DSN` in `.env` may point to
the local catalog database: the test creates and drops only a uniquely named
temporary schema. Run
`python -m pytest lab2_rag_agent/tests/test_postgres_integration.py -q`.
Without the variable it skips rather than claiming PostgreSQL was tested.

The seed distinguishes three `ai_workstation` entries from seven `ai_pc` entries;
`ai_pc` is a backward-compatible addition to the existing product-type enum.

This catalog database is separate from any PostgreSQL instance WeKnora uses
internally.

## Product-document mapping

`product_documents` records the Lab 2-owned relationship from a catalog
`product_id` to the provider identity `(knowledge_base_id, knowledge_id)`. It
does not store document bodies, chunks, or embeddings, and filenames are metadata
only—not product identity. `source_url` is optional and should be supplied only
when verified by the catalog/source system. `content_sha256` supports duplicate
lookup/reconciliation; provider parse status is kept as bounded raw text until a
provider adapter defines a mapping. On provider-identity upsert, omitted URL/hash
values preserve existing provenance and checksum. The migration uses `ON DELETE RESTRICT` so a
product with document mappings cannot be deleted and leave provider records untracked.

The mapping contract and repository are Lab 2-local:
`lab2_rag_agent.catalog.documents.ProductDocumentRepository` and
`lab2_rag_agent.catalog.document_repository.PostgresProductDocumentRepository`.
The repository lists mappings by product, resolves provider IDs by knowledge
base, finds an existing checksum for reconciliation, upserts on provider identity,
and updates parse status with parameterized SQL.
