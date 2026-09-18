# lab demo

Phase 0-1 foundation for an on-prem AI configuration advisor. The product scope
is deliberately limited to AI Server and AI Workstation recommendations. The
repository is designed so Lab 1, Lab 2 and Lab 3 can evolve independently while
sharing typed contracts and replaceable adapters.

## Current phase

This increment provides documentation, Pydantic domain contracts, stable
interfaces, deterministic fake adapters, sizing/validation/proposal services,
an explicit workflow state machine, Lab 1 training/evaluation skeletons, and
GPU-free tests. It does not train a model or run production RAG.

## Development

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

The first implementation uses only lightweight dependencies. PyTorch,
Transformers, TRL, PEFT, Docling, BGE-M3, Qdrant and vLLM remain future adapter
choices and are not required to run the foundation tests.

See [docs/09-implementation-plan.md](docs/09-implementation-plan.md) for the
parallel delivery waves and [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) for
the current boundary.
