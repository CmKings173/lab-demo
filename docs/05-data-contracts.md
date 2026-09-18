# Shared data contracts

All contracts are Pydantic models with unknown fields forbidden. `None` means
unknown/not supplied; it never means zero or unsuitable.

## Requirement intake

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `CustomerRequirement.model_size_b` | float | no / yes | user | intake | sizing | Model parameter count in billions. |
| `CustomerRequirement.usage` | enum | no / yes | user | intake | sizing/workflow | `inference` or `fine_tune`. |
| `CustomerRequirement.budget_vnd` | int | no / yes | user | intake | search/validation | Maximum known budget. |
| `CustomerRequirement.concurrent_users` | int | no / yes | user | intake | sizing | Expected concurrent users. |
| `CustomerRequirement.context_length` | int | no / yes | user | intake | sizing | Expected token context. |
| `CustomerRequirement.storage_requirement_gb` | int | no / yes | user | intake | builder/validation | Requested usable storage. |
| `CustomerRequirement.expansion_requirement` | string | no / yes | user | intake | proposal | Free-form growth requirement. |
| `CustomerRequirement.training_method` | string | no / yes | user | intake | sizing | Fine-tuning method when applicable. |
| `MissingInformation.status` | string | yes / no | code | requirement service | API/agent | Stable missing-information status. |
| `MissingInformation.missing_fields` | list[string] | yes / no | derived | requirement service | caller | Required fields still absent. |
| `MissingInformation.question` | string | yes / no | derived | requirement service | caller | Question ending the stateless run. |

## Catalog and configuration

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `Product.id` | string | yes / no | catalog | repository | all labs | Stable platform id. |
| `Product.sku` | string | yes / no | catalog | repository | tools/UI | Manufacturer or reseller SKU. |
| `Product.name` | string | yes / no | catalog | repository | proposal | Platform name. |
| `Product.manufacturer` | string | yes / no | catalog | repository | search/proposal | Manufacturer. |
| `Product.product_type` | enum | yes / no | catalog | repository | search/workflow | AI server or workstation. |
| `Product.platform` | string | no / yes | catalog | repository | proposal | Chassis/platform family. |
| `Product.cpu_options` | list[string] | no / no | catalog | repository | builder | Supported CPU descriptions. |
| `Product.max_ram_gb` | int | no / yes | catalog | repository | validation | Maximum supported RAM. |
| `Product.max_gpu_slots` | int | no / yes | catalog | repository | builder/validation | Physical GPU slot capacity. |
| `Product.max_storage_gb` | int | no / yes | catalog | repository | validation | Maximum configured storage. |
| `Product.storage_slots` | int | no / yes | catalog | repository | proposal | Storage device slot count. |
| `Product.power_w` | int | no / yes | catalog | repository | proposal | Known platform power capacity. |
| `Product.form_factor` | string | no / yes | catalog | repository | proposal | Workstation/tower/rack form. |
| `Product.base_price_vnd` | int | no / yes | catalog | repository | builder/search | Platform price without selected GPU. |
| `Product.availability` | string | no / yes | catalog | repository | proposal | Availability snapshot. |
| `Product.source_urls` | list[string] | no / no | catalog/docs | repository | evidence | Product provenance URLs. |
| `Product.updated_at` | datetime | no / yes | catalog | repository | freshness checks | Source refresh time. |
| `GPUOption.gpu_id` | string | yes / no | catalog | repository/config | builder | Stable GPU option id. |
| `GPUOption.name` | string | yes / no | catalog | repository/config | proposal | Display name. |
| `GPUOption.memory_gb` | int | yes / no | catalog | repository/config | builder/validation | VRAM per actual GPU. |
| `GPUOption.supported_product_ids` | list[string] | no / no | catalog | repository/config | builder | Exact compatible platforms. |
| `GPUOption.supported_product_types` | list[enum] | no / no | catalog | repository/config | builder | Compatible platform classes. |
| `GPUOption.price_vnd` | int | no / yes | catalog | repository/config | builder | Optional unit price. |
| `GPUOption.source_urls` | list[string] | no / no | catalog/docs | repository/config | evidence | GPU provenance URLs. |
| `ProductConfiguration.configuration_id` | string | yes / no | derived | builder | validation/proposal | Stable configured option id. |
| `ProductConfiguration.product` | Product | yes / no | catalog | builder | validation/proposal | Selected platform. |
| `ProductConfiguration.selected_gpu` | GPUOption | no / yes | catalog | builder | validation/proposal | Selected GPU; unknown is explicit. |
| `ProductConfiguration.gpu_count` | int | no / yes | derived | builder | validation/proposal | Count calculated from actual GPU VRAM. |
| `ProductConfiguration.configured_ram_gb` | int | no / yes | derived | builder | validation/proposal | Proposed system RAM. |
| `ProductConfiguration.configured_storage_gb` | int | no / yes | derived | builder | validation/proposal | Proposed storage. |
| `ProductConfiguration.selected_cpu` | string | no / yes | catalog | builder | proposal | Selected CPU description. |
| `ProductConfiguration.estimated_price_vnd` | int | no / yes | derived | builder | validation/proposal | Price only when all components are known. |
| `ProductConfiguration.source_urls` | list[string] | no / no | catalog/docs | builder | evidence | Combined platform/GPU sources. |

`total_vram_gb` is a computed property: `selected_gpu.memory_gb * gpu_count`.
It is never calculated from the platform's maximum slot count.

## Sizing and validation

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `SizingRequest.model_parameters_b` | float | yes / no | requirement | workflow | sizing | Model size in billions. |
| `SizingRequest.usage` | enum | yes / no | requirement | workflow | sizing | Inference or fine-tune. |
| `SizingRequest.quantization` | string | no / yes | user/default | workflow | sizing | Requested quantization. |
| `SizingRequest.context_length` | int | no / yes | requirement | workflow | sizing | Token context. |
| `SizingRequest.concurrent_users` | int | no / yes | requirement | workflow | sizing | Concurrency target. |
| `SizingRequest.training_method` | string | no / yes | requirement | workflow | sizing | Fine-tuning method. |
| `SizingRequest.additional_overhead` | float | no / no | policy | workflow | sizing | Explicit memory overhead factor. |
| `SizingResult.estimated_model_memory_gb` | float | yes / no | derived | sizing | proposal/eval | Estimated model/workload memory. |
| `SizingResult.recommended_total_vram_gb` | float | yes / no | derived | sizing | builder/validation | Required aggregate VRAM. |
| `SizingResult.recommended_system_ram_gb` | int | yes / no | derived | sizing | builder/validation | Required system RAM. |
| `SizingResult.recommended_storage_gb` | int | no / yes | derived | sizing | builder | Storage recommendation if known. |
| `SizingResult.assumptions` | list[string] | no / no | policy | sizing | proposal/eval | Explicit estimator assumptions. |
| `SizingResult.warnings` | list[string] | no / no | policy | sizing | proposal | Benchmark/certainty warnings. |
| `SizingResult.confidence` | float | yes / no | policy | sizing | proposal/eval | Confidence from 0 to 1. |
| `ValidationFailure.field` | string | yes / no | derived | validator | workflow/UI | Failed field. |
| `ValidationFailure.message` | string | yes / no | derived | validator | workflow/UI | Failure explanation. |
| `ValidationFailure.actual` | any | no / yes | config | validator | UI/eval | Observed value. |
| `ValidationFailure.required` | any | no / yes | sizing/requirement | validator | UI/eval | Required value. |
| `ValidationResult.status` | enum | yes / no | derived | validator | workflow | `PASS`, `FAIL` or `UNKNOWN`. |
| `ValidationResult.failures` | list | no / no | derived | validator | workflow/UI | Definite constraint failures. |
| `ValidationResult.warnings` | list[string] | no / no | derived | validator | proposal/UI | Non-terminal cautions. |
| `ValidationResult.unknown_fields` | list[string] | no / no | derived | validator | workflow/UI | Facts required but unavailable. |

## Retrieval and embeddings

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `DocumentChunk.id` | string | yes / no | ingestion | document adapter | retrieval/evidence | Stable chunk id. |
| `DocumentChunk.text` | string | yes / no | document | ingestion | retrieval | Chunk text. |
| `DocumentChunk.source_url` | string | no / yes | document | ingestion | evidence | Source URL. |
| `DocumentChunk.product_id` | string | no / yes | catalog mapping | ingestion | filtered search | Related product id. |
| `DocumentChunk.page` | int | no / yes | document | ingestion | evidence | Source page. |
| `DocumentChunk.metadata` | map[string,string] | no / no | ingestion | ingestion | debug/eval | Extra non-authoritative metadata. |
| `DocumentHit.chunk` | DocumentChunk | yes / no | retrieval | search/reranker | workflow | Retrieved chunk. |
| `DocumentHit.retrieval_score` | float | no / yes | retriever | search | eval/debug | Initial retrieval score. |
| `DocumentHit.rerank_score` | float | no / yes | reranker | reranker | eval/debug | Reranker score. |
| `DocumentHit.rank` | int | yes / no | retrieval | search/reranker | workflow/eval | One-based final rank. |
| `DocumentHit.retrieval_method` | string | yes / no | retriever | search | eval/debug | Dense/sparse/hybrid/fake method. |
| `DocumentSearchRequest.query` | string | yes / no | workflow/tool | caller | search | Search text. |
| `DocumentSearchRequest.product_id` | string | no / yes | workflow/tool | caller | search | Optional product constraint. |
| `DocumentSearchRequest.top_k` | int | no / no | caller/default | caller | search | Maximum hit count. |
| `DocumentSearchResult.hits` | list[DocumentHit] | no / no | retrieval | search/RAG | workflow/tool | Ranked evidence hits. |
| `DocumentSearchResult.total` | int | no / no | retrieval | search/RAG | eval | Returned hit count. |
| `EmbeddingVector.dense` | list[float] | no / no | embedder | embedding adapter | vector store | Dense component. |
| `EmbeddingVector.sparse_indices` | list[int] | no / no | embedder | embedding adapter | vector store | Sparse token indices. |
| `EmbeddingVector.sparse_values` | list[float] | no / no | embedder | embedding adapter | vector store | Sparse weights aligned to indices. |

## Comparison, proposal and evidence

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `ComparisonResult.product_ids` | list[string] | yes / no | configs | comparison | proposal/tool | Compared product ids. |
| `ComparisonResult.configuration_ids` | list[string] | no / no | configs | comparison | proposal | Compared configuration ids. |
| `ComparisonResult.dimensions` | list[string] | no / no | policy | comparison | proposal/UI | Exact comparison dimensions. |
| `ComparisonResult.summary` | string | yes / no | derived | comparison | proposal/UI | Bounded comparison summary. |
| `Evidence.claim` | string | yes / no | proposal claim | proposal | verifier | Claim/field key. |
| `Evidence.value` | any | yes / yes | config/document | proposal | verifier | Claimed value. |
| `Evidence.source_url` | string | yes / no | catalog/document | proposal | verifier/UI | Evidence URL. |
| `Evidence.product_id` | string | yes / no | config | proposal | verifier | Related product. |
| `Evidence.document_id` | string | no / yes | retrieval | proposal | verifier/debug | Related chunk/document id. |
| `Evidence.page` | int | no / yes | retrieval | proposal | verifier/UI | Source page. |
| `Evidence.verified` | bool | no / no | code | proposal/verifier | verifier/UI | Whether evidence is accepted. |
| `ProposalOption.name` | string | yes / no | policy | proposal | UI | Option A/B label. |
| `ProposalOption.configuration` | ProductConfiguration | yes / no | workflow | proposal | verifier/UI | Proposed configuration. |
| `ProposalOption.rationale` | string | yes / no | code | proposal | UI | Selection rationale. |
| `ProposalOption.estimated_price_vnd` | int | no / yes | config | proposal | verifier/UI | Known estimated price. |
| `ProposalOption.limitations` | list[string] | no / no | sizing | proposal | UI | Known limitations. |
| `ProposalOption.evidence` | list[Evidence] | no / no | catalog/docs | proposal | verifier/UI | Option evidence. |
| `Proposal.customer_requirement` | CustomerRequirement | yes / no | intake | proposal | verifier/UI | Original requirement. |
| `Proposal.interpreted_workload` | string | yes / no | requirement | proposal | UI | Human-readable workload. |
| `Proposal.sizing_result` | SizingResult | yes / no | sizing | proposal | verifier/UI | Resource target. |
| `Proposal.selected_configurations` | list | no / no | workflow | proposal | verifier/UI | Proposed configurations. |
| `Proposal.options` | list[ProposalOption] | no / no | workflow | proposal | verifier/UI | A/B alternatives. |
| `Proposal.comparison` | ComparisonResult | no / yes | comparison | proposal | UI | Comparison used for selection. |
| `Proposal.technical_claims` | map[string,any] | no / no | config | proposal | verifier | Claims requiring evidence. |
| `Proposal.evidence` | list[Evidence] | no / no | catalog/docs | proposal | verifier/UI | Aggregate evidence. |
| `Proposal.technical_reasoning` | list[string] | no / no | code | proposal | UI | Explainable rule summary, not chain-of-thought. |
| `Proposal.limitations` | list[string] | no / no | sizing | proposal | UI | Limitations. |
| `Proposal.unknown_information` | list[string] | no / no | validation | proposal | UI | Unresolved facts. |
| `Proposal.sources` | list[string] | no / no | evidence | proposal | UI | Deduplicated source URLs. |
| `Proposal.estimated_price_vnd` | int | no / yes | option A | proposal | UI | Primary option price. |
| `Proposal.created_at` | datetime | no / yes | application | caller | audit/UI | Creation time if assigned. |

## Lab 1 and tool-calling

| Contract.field | Type | Required / nullable | Source | Producer | Consumer | Meaning |
|---|---|---|---|---|---|---|
| `FineTuneExample.example_id` | string | yes / no | dataset | author | validator/trainer | Unique example id. |
| `FineTuneExample.scenario_family_id` | string | yes / no | dataset | author | splitter | Leakage boundary. |
| `FineTuneExample.scenario_summary` | string | yes / no | dataset | author | validator/reviewer | Family metadata. |
| `FineTuneExample.task_type` | string | yes / no | dataset | author | manifest/eval | Task category. |
| `FineTuneExample.difficulty` | string | yes / no | dataset | author | manifest/eval | Difficulty band. |
| `FineTuneExample.language` | string | yes / no | dataset | author | manifest/eval | `vi`, `mixed` or `en`. |
| `FineTuneExample.source_type` | string | yes / no | dataset | author | audit | Synthetic/reviewed source. |
| `FineTuneExample.messages` | list[ChatMessage] | yes / no | dataset | author | trainer/validator | Conversation/tool sequence. |
| `FineTuneExample.tools` | list[ToolDefinition] | no / no | shared schema | author | trainer/validator | Available tools. |
| `FineTuneExample.labels` | DatasetLabels | yes / no | dataset | author | evaluator | Behavioral gold labels. |
| `DatasetLabels.intent` | string | yes / no | review | author | evaluator | Expected intent. |
| `DatasetLabels.missing_fields` | list[string] | no / no | review | author | evaluator | Expected missing fields. |
| `DatasetLabels.should_call_tool` | bool | yes / no | review | author | evaluator | Tool-needed gold label. |
| `DatasetLabels.expected_tool` | string | no / yes | review | author | evaluator | Expected tool when applicable. |
| `DatasetLabels.must_not_invent_product_fact` | bool | no / no | policy | author | evaluator | Grounding constraint. |

`ChatMessage` fields are `role`, nullable `content`, `tool_calls` and nullable
`tool_call_id`. `ToolCall` fields are `id`, `name` and object `arguments`.
`ToolDefinition` fields are `name`, `description` and JSON-schema `parameters`.
