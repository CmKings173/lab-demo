# lab demo

Nền tảng tư vấn cấu hình AI Server và AI Workstation chạy on-prem. Ba lab có
ranh giới riêng: Lab 1 huấn luyện hành vi, Lab 2 quản lý catalog/RAG/công cụ,
Lab 3 điều phối sizing, cấu hình, validation và proposal. Các lab chỉ chia sẻ
typed contracts và interfaces.

## Trạng thái hiện tại

Lab 2 Phase 2.5 is implemented in source: PostgreSQL catalog and product-document
repositories, WeKnora v0.8.0 search plus a one-file operator ingestion path, the
six-tool FastAPI Tool API, the OpenClaw plugin/runtime composition, and catalog
product comparison values. The OpenClaw agent does not receive ingestion, shell,
filesystem, browser, web-search, arbitrary MCP, or SQL tools.

This is not a live-deployment claim. PostgreSQL integration is verified only when
`LAB2_TEST_POSTGRES_DSN` is configured. OpenClaw Gateway loading on GB300, Qwen3-14B
tool use, and the full Gateway → Tool API → PostgreSQL/WeKnora/model response path
remain unverified. Lab 1 training and production catalog/pricing remain separate work.

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

The Lab2 Python package uses lightweight runtime dependencies; its PostgreSQL
driver, dotenv loader, and Uvicorn server are in the `lab2-runtime` extra. WeKnora
is a separate service expected at `127.0.0.1:8080`; the loopback Lab2 Tool API uses
`127.0.0.1:8090`. Lab2 does not build a parallel Docling/BGE/Qdrant ingestion stack.

From a clean checkout, install the exact Lab2 runtime extra before running the
ingestion CLI. Then import one file for an existing catalog product with an explicit
ID (never inferred from its filename):

```powershell
python -m pip install -e ".[lab2-runtime]"
python -m lab2_rag_agent.ingestion --product-id <catalog-product-id> --file <local-file-path>
```

See [Lab 2 overview](docs/lab2/overview.md), [ingestion](docs/lab2/ingestion.md),
the [OpenClaw plugin runbook](lab2_rag_agent/openclaw/plugin/README.md), and
`.env.example` for safe configuration placeholders.

Xem [trạng thái hiện tại](docs/current-state.md),
[kiến trúc](docs/architecture.md) và
[các quyết định còn mở](docs/open-decisions.md).
