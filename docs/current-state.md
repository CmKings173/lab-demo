# Trạng thái hiện tại

> **Lab2 backend/runtime update (2026-09-29):** source now includes the PostgreSQL
> catalog and product-document repositories, WeKnora v0.8.0 search and single-file
> operator ingestion, the six-tool FastAPI boundary, and the OpenClaw plugin/runtime
> composition. This records source implementation only; it does not claim that live
> PostgreSQL integration or the GB300/OpenClaw end-to-end path was verified.

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

Not yet verified live: PostgreSQL integration unless its dedicated test DSN is set;
OpenClaw Gateway loading on GB300; Qwen3-14B tool calls; and the complete
OpenClaw → `127.0.0.1:8090` → PostgreSQL/WeKnora/model response path.

Các lựa chọn chưa khóa nằm tại `docs/open-decisions.md`.
