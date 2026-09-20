# Trạng thái hiện tại

Phiên bản: foundation hardening v3 + Vietnamese gold dataset.

Đã có:

- Cấu trúc package theo ba lab, shared contracts và fake/real adapter boundary.
- Sizing theo rule, cấu hình cụ thể theo GPU option thật, không tự chọn CPU/storage.
- Giá `COMPLETE/PARTIAL/UNKNOWN` và validation `PASS/FAIL/UNKNOWN`.
- Workflow resolve unknown fact từ verified documents rồi revalidate.
- So sánh theo concrete configuration; product comparison riêng cho Lab 2.
- Dataset vàng tiếng Việt: 50 mẫu, 25 family, đủ 25 scenario type, split 40/4/6.
- Validator, manifest/hash, Qwen JSONL export và 9 nhóm evaluation metric.
- Offline test suite và Ruff gate.

Chưa có:

- Download/train/merge model thực tế hoặc benchmark base-vs-adapter.
- PostgreSQL, Qdrant, Docling, BGE-M3, reranker, vLLM hay OpenClaw runtime thật.
- Catalog/pricing production, UI, MCP hoặc cloud deployment.
- Dataset production quy mô khoảng 3.000 mẫu.

Các lựa chọn chưa khóa nằm tại `docs/open-decisions.md`.
