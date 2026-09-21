# Trạng thái hiện tại

Phiên bản: foundation hardening v4 contract correctness.

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
- PostgreSQL, Qdrant, Docling, BGE-M3, reranker, vLLM hay OpenClaw runtime thật.
- Catalog/pricing production, UI, MCP hoặc cloud deployment.
- Dataset production quy mô khoảng 3.000 mẫu; Iteration 4 không train hoặc scale.

Các lựa chọn chưa khóa nằm tại `docs/open-decisions.md`.
