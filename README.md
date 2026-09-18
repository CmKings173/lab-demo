# lab demo

Foundation for an on-prem AI configuration advisor. The product scope
is deliberately limited to AI Server and AI Workstation recommendations. The
repository is designed so Lab 1, Lab 2 and Lab 3 can evolve independently while
sharing typed contracts and replaceable adapters.

## Current phase

This increment separates product platforms from GPU-backed configurations,
provides deterministic sizing plus PASS/FAIL/UNKNOWN validation, and implements
an offline end-to-end workflow through retrieval, comparison, proposal A/B and
evidence verification. Lab 1 uses a family-isolated chat/tool-calling dataset
contract with validators and review seed data. It does not train a model or run
production infrastructure.

## Development

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
python -m compileall agent api adapters lab1 services shared workflow
```

The first implementation uses only lightweight dependencies. PyTorch,
Transformers, TRL, PEFT, Docling, BGE-M3, Qdrant and vLLM remain future adapter
choices and are not required to run the foundation tests.

See [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) for the implemented boundary
and [docs/OPEN_DECISIONS.md](docs/OPEN_DECISIONS.md) for unresolved choices.
