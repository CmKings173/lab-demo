# Lab 1 dataset/evaluation freeze

Date: 2026-09-24
Status: **FROZEN**
Scope: dataset and evaluation artifacts only; no model training was run.

## Version, seeds and hashes

| Item | Value |
| --- | --- |
| Expanded dataset version / seed | `1.0.0-vi-expansion` / `20260922` |
| Expanded dataset manifest content hash | `e39e3b451fa8cf651a5ed896ef0503b2b7a6dcd518c9ac257219e885af52ec6d` |
| Training JSONL SHA-256 | `CFCF8B869FD120D1EE7F247937576EB3BB425929893EE55858C978730921688A` |
| Validation JSONL SHA-256 | `881D9CB80272D2AE36CCECC0786DDE8B0DFD5F9A35E7F11CDF723BAE2E1A96D9` |
| Evaluation version / seed | `lab1-evaluation-v1` / `20260923` |
| Evaluation manifest content hash | `5674ef64a0092f14dde2ecde1bfe4f26aca630f60318fc88c6fa013528026781` |
| Evaluation JSONL SHA-256 | `EE38AC3FF58358126F1A4115311DDC779114B5A3F2744930FABDA9DD7EFC17D7` |
| Gold seed SHA-256 before / after | `5EFEC138E4E27D7832E70AA4A335BDAD1927560D590CD92538BF9358B098B76D` / same |

The gold seed is a separate 60-spec source file. Expanded training data and the independent 120-case evaluation benchmark remain separate artifacts.

## Dataset and split

| Metric | Result |
| --- | ---: |
| Expanded examples | 1200 |
| Train | 961 |
| Validation | 239 (19.92%) |
| Evaluation cases | 120 |
| Semantic templates / groups | 35 / 138 |
| Review sample | 84 (12 families × 7 personas) |

| Family | Total | Train | Validation |
| --- | ---: | ---: | ---: |
| `expanded_solution_design` | 160 | 130 | 30 |
| `expanded_missing_information` | 160 | 128 | 32 |
| `expanded_novice_users` | 120 | 99 | 21 |
| `expanded_product_search` | 110 | 88 | 22 |
| `expanded_comparison` | 90 | 72 | 18 |
| `expanded_multi_tool` | 110 | 88 | 22 |
| `expanded_technical_questions` | 90 | 74 | 16 |
| `expanded_lora_inference` | 80 | 67 | 13 |
| `expanded_requirement_change` | 80 | 64 | 16 |
| `expanded_contradictory` | 60 | 51 | 9 |
| `expanded_failure_abstention` | 90 | 75 | 15 |
| `expanded_out_of_scope` | 50 | 25 | 25 |

Persona distribution: IT_GENERALIST 172, DEVELOPER 172, ML_ENGINEER 172, SOLUTION_ARCHITECT 171, NON_TECHNICAL_USER 171, MANAGER 171, PURCHASING 171. Both splits contain all seven personas.

Difficulty: easy 569 (train 444 / validation 125), medium 464 (375 / 89), hard 167 (142 / 25). Turns: single 843 (668 / 175), multi 357 (293 / 64). Tool patterns: no-tool 433 (355 / 78), single-tool 627 (495 / 132), multi-tool 110 (88 / 22), failure 30 (23 / 7).

## Quality and isolation

| Gate / metric | Result |
| --- | ---: |
| Exact user duplicates | 0 |
| Exact conversation duplicates | 0 |
| Near-user pairs / affected-example ratio | 201 / 24.0% |
| Near-conversation pairs / affected-example ratio | 2016 / 66.17% |
| Near-duplicate threshold | 0.92 |
| Exact final duplicates / unique finals / duplicate ratio | 423 / 777 / 35.25% |
| Family leakage / semantic-group leakage | 0 / 0 |
| Train↔validation near-user / near-conversation pairs | 0 / 0 |
| Semantic / label-text / encoding / Python-repr errors | 0 / 0 / 0 / 0 |
| Eval internal exact / canonical-near user duplicates | 0 / 0 |
| Eval↔train exact / canonical-near overlap | 0 / 0 |
| Eval↔train semantic-template overlap | 0 |
| Eval semantic errors | 0 |
| GENERAL_VRAM semantic audit | 18 / 18 pass |

Internal training near-duplicate counts are diagnostic metrics, not automatic correctness failures. Cross-split canonical near overlap is zero. The evaluation benchmark does not claim persona robustness (`persona_robustness_assessed=false`).

## Verification

Executed successfully:

- `python -m lab1_finetune.data.build_expanded` — twice.
- `python -m lab1_finetune.evaluation.build_benchmark` — twice.
- `python -m pytest lab1_finetune/tests -q -p no:cacheprovider` — exit 0.
- `ruff check lab1_finetune shared --no-cache` — exit 0, all checks passed.
- `python -m compileall lab1_finetune shared` — exit 0.
- `git diff --check` — exit 0 (Git emitted CRLF conversion warnings only).
- Pydantic validation of all 961 training, 239 validation and 120 evaluation rows — pass.
- Semantic validation of generated training and independent evaluation records — zero errors.
- Qwen export JSON/role/tool-call-order validation of 961 training and 239 validation rows — pass.
- Direct UTF-8 code-point check of generated exports — no Unicode replacement characters or literal `B?n` corruption; the earlier PowerShell `Get-Content` display was a terminal encoding issue, not file content.
- Representative manual sweep of all 35 semantic templates across the 12 families — no correctness blocker found.

Determinism: the second build produced identical SHA-256 hashes for the train/validation JSONL, both Qwen exports, both manifests, review sample and evaluation benchmark. The gold seed hash remained unchanged. The repository was not committed or tagged, and no model training was started.

FINAL: `LAB1_FROZEN = true`
