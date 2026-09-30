# Trạng thái hiện tại

> **Lab2 backend/runtime update (2026-09-29):** source now includes the PostgreSQL
> catalog and product-document repositories, WeKnora v0.8.0 search and single-file
> operator ingestion, the six-tool FastAPI boundary, and the OpenClaw plugin/runtime
> composition. This records source implementation only; it does not claim that live
> PostgreSQL integration or the GB300/OpenClaw end-to-end path was verified.

> **Lab 3 Phase 3.2 source status (2026-09-30):** the real-data composition reads
> `products` and typed GPU/RAM/storage options directly from that same PostgreSQL
> database. Option compatibility is an explicit product relation; the existing
> offline demo remains the default app. No live PostgreSQL verification is claimed
> unless `LAB2_TEST_POSTGRES_DSN` integration tests actually run successfully.

Foundation baseline: hardening v4 contract correctness. The Lab2 status below is
updated for Phase 2.5; foundation notes are retained as historical project context.

Đã có:

- Cấu trúc package theo ba lab, shared contracts và fake/real adapter boundary.
- Sizing theo rule với default được ghi thành assumption; cấu hình chọn GPU,
  RAM và storage option thật, không tự chọn CPU.
- Giá `COMPLETE/PARTIAL/UNKNOWN` và validation `PASS/FAIL/UNKNOWN`.
- Workflow resolve unknown fact từ verified documents rồi revalidate.
- So sánh theo concrete configuration; product comparison riêng cho Lab 2.
- Dataset hành vi vàng tiếng Việt: 60 mẫu, 25 family, gồm 50 core và 10
  multi-tool trajectory; catalog/result đều là dữ liệu DEMO hư cấu.
- Split theo family hiện là 46/8/6 examples trên 20/2/3 families.
- Validator dùng cùng Pydantic tool args/result contracts với runtime; evaluator
  tự tính sequence/name/schema/exact/semantic tool metrics từ prediction thật.
- Direct document evidence được tách khỏi deterministic derived claims.
- Offline test suite và Ruff gate.

Chưa có:

- Download/train/merge model thực tế hoặc benchmark base-vs-adapter.
- Catalog/pricing production, Lab2 UI, MCP hoặc cloud deployment.
- Dataset production quy mô khoảng 3.000 mẫu; Iteration 4 không train hoặc scale.

Lab2 implementation in source:

- PostgreSQL migrations, curated seed, catalog repository, and product-document mapping.
- WeKnora search adapter and operator-only one-file ingestion CLI/service.
- Lab2 runtime composition, FastAPI Tool API, TypeScript OpenClaw plugin, and an
  explicit six-tool agent allowlist.
- Product comparison returns catalog facts; configuration comparison reports
  `configuration_repository_not_configured` until a repository is supplied.

Lab 3 Phase 3.2 implementation in source:

- Additive migration 004 creates typed `configuration_options` and explicit
  `configuration_option_products` links to the existing `products` table.
- The existing catalog seed idempotently upserts three clearly DEMO options for
  the existing `cntt-ws-rtxpro6000-maxq` product; it does not add product rows.
- A product-scoped PostgreSQL option repository supplies typed options to the
  deterministic configuration builder. The real Lab 3 composition directly
  reuses the Lab 2 PostgreSQL product adapter and does not call Lab 2 HTTP.
- `LAB3_POSTGRES_DSN` is a separate process setting intended to point to the
  same database as `LAB2_POSTGRES_DSN`. The existing offline demo app is unchanged.

Lab 3 Phase 3.3 implementation in source:

- The real app composes the existing PostgreSQL product-document mapping repository
  and WeKnora search adapter directly, using the same Lab2 database/KB settings.
- A provider-neutral Lab3 provenance interface is backed by the completed mapping
  in `product_documents`; a separate deterministic resolver handles only
  `max_ram_gb`, `max_gpu_slots`, and `max_storage_gb`.
- Facts require exact configured-KB/document/product/source provenance, explicit
  supported capacity wording, and `Product` validation. Conflicts remain unknown;
  retrieval score is not a verification gate. `verified=true` records these
  application checks, not independent proof of real-world truth.
- The real FastAPI lifespan closes the workflow executor first, then runtime-owned
  WeKnora and model clients; injected provider clients remain caller-owned.

Lab 3 Phase 3.4 implementation in source:

- Lab 3 uses a direct Qwen3-14B/vLLM adapter through the shared `ModelClient`
  interface. The adapter uses OpenAI-compatible models and chat-completions
  endpoints; thinking is disabled and tool calls are not used.
- `POST /conversation/runs` extracts only the eight `CustomerRequirement` fields,
  validates them with the shared contract, and fails closed when required values
  are missing or model output is invalid. Valid requests use the existing
  `WorkflowRunService`; the deterministic workflow does not depend on the LLM.
- `POST /runs/{run_id}/explanation` reads only the server-side run record and its
  safe result/proposal summary. Conversation support is configured only by the
  explicit real-data app; the default offline app remains infrastructure-free.
- The Lab 3 runtime closes its executor, WeKnora client, and model client in order.
  Injected provider clients remain caller-owned.

Still unverified live: PostgreSQL integration when its dedicated test DSN is
absent; live WeKnora service verification; Lab 2 OpenClaw Gateway/plugin loading on
GB300; and a direct Qwen3-14B/vLLM conversation-to-workflow round trip on GB300.

Not yet verified live: PostgreSQL integration unless its dedicated test DSN is set;
the live WeKnora service; OpenClaw Gateway/plugin loading on GB300 for Lab 2; a
direct Qwen3-14B/vLLM conversation round trip on GB300;
and the complete
OpenClaw → `127.0.0.1:8090` → PostgreSQL/WeKnora/model response path.

Các lựa chọn chưa khóa nằm tại `docs/open-decisions.md`.
