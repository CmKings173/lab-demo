# Shared data contracts

All domain models are Pydantic models with extra fields forbidden and JSON
serialization enabled.

| Contract | Required core fields | Produced by | Consumed by |
|---|---|---|---|
| `CustomerRequirement` | model size, usage, budget may be absent during intake | requirement input | sizing, validation, proposal |
| `MissingInformation` | missing fields, question | requirement service | workflow/agent |
| `Product` | id, SKU, name, manufacturer, product type | catalog | validation, proposal |
| `ProductFilter` | all optional filter fields | catalog tool | repository |
| `ProductSearchRequest/Result` | request filters; result products | catalog service | workflow/agent |
| `DocumentChunk` | id and text | document ingestion | document search |
| `DocumentSearchRequest/Result` | query; chunks | RAG service | agent/proposal evidence |
| `SizingRequest/Result` | model parameters and usage; calculated resources | sizing service | validation/proposal |
| `ProductCandidate` | product | workflow validation | proposal/comparison |
| `ValidationFailure/Result` | validity and failures | validation service | workflow/proposal |
| `ComparisonResult` | product ids and summary | comparison service | proposal |
| `ProposalOption/Proposal` | requirement, sizing, products, sources | proposal service | verification/UI |
| `WorkflowState/Context` | state and requirement | workflow | API/agent/tests |
| `ToolResult` | ok plus data/error | controlled tools | OpenClaw |

Nullable fields mean the source did not provide a value. They must not be
silently defaulted into a product claim. The workflow records who produced a
value through state and sources; later revisions can add explicit provenance
objects without changing the service seams.
