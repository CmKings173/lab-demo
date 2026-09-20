# lab demo

Nền tảng tư vấn cấu hình AI Server và AI Workstation chạy on-prem. Ba lab có
ranh giới riêng: Lab 1 huấn luyện hành vi, Lab 2 quản lý catalog/RAG/công cụ,
Lab 3 điều phối sizing, cấu hình, validation và proposal. Các lab chỉ chia sẻ
typed contracts và interfaces.

## Trạng thái hiện tại

Foundation v3 chạy hoàn toàn offline bằng fake adapters. Workflow không biến
dữ liệu thiếu thành giá trị mặc định: giá có `COMPLETE/PARTIAL/UNKNOWN`, kết quả
validation có `PASS/FAIL/UNKNOWN`, và fact sản phẩm chỉ được bổ sung từ tài liệu
đã xác minh. Dataset Lab 1 có 50 mẫu tiếng Việt thuộc 25 scenario family, split
theo family để tránh leakage. Chưa có model training hay hạ tầng production.

## Development

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
python -m lab1_finetune.data.build_artifacts
python -m compileall adapters lab1_finetune lab2_rag_agent lab3_workflow shared
```

The first implementation uses only lightweight dependencies. PyTorch,
Transformers, TRL, PEFT, Docling, BGE-M3, Qdrant and vLLM remain future adapter
choices and are not required to run the foundation tests.

Xem [trạng thái hiện tại](docs/current-state.md),
[kiến trúc](docs/architecture.md) và
[các quyết định còn mở](docs/open-decisions.md).
