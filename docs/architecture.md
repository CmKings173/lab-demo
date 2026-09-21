# Kiến trúc

```mermaid
flowchart LR
  U[Customer requirement] --> L3[Lab 3 workflow]
  L3 --> S[Sizing + configuration + validation]
  L3 --> L2[Lab 2 catalog + RAG]
  L2 --> C[(Catalog adapter)]
  L2 --> D[(Document adapter)]
  L3 --> P[Comparison + proposal + evidence]
  L1[Lab 1 behavior model] -. future tool calls .-> L2
  OC[OpenClaw boundary] -. controlled tools .-> L2
```

## Ranh giới sở hữu

- `lab1_finetune`: dataset, training entry points và behavior evaluation.
- `lab2_rag_agent`: exact catalog, document retrieval/reranking, RAG và OpenClaw tools.
- `lab3_workflow`: requirement, sizing, concrete configuration, validation, comparison,
  proposal, evidence và workflow state machine.
- `shared`: contracts/interfaces ổn định; không chứa business flow của riêng một lab.
- `adapters/fake` và `adapters/real`: điểm thay thế hạ tầng, không đổi domain API.

PostgreSQL là nguồn authoritative cho fact có cấu trúc và numeric filter. Qdrant
chỉ phục vụ document retrieval; semantic hit không được ghi đè exact catalog fact.
OpenClaw chỉ gọi domain tools, không nhận quyền SQL hay shell tùy ý.

## Luồng phụ thuộc

Contracts không phụ thuộc implementation. Fake implementations dùng chung nằm ở
`adapters/fake`; Lab 2 không phụ thuộc Lab 1 và unit tool tests không phụ thuộc
concrete service của Lab 3. Các tool schema được sinh duy nhất từ Pydantic args
models trong `shared/tool_args.py`; runtime và dataset validator dùng cùng registry.

Dữ liệu chưa biết giữ nguyên `None`/`UNKNOWN`. Product fact resolver chỉ xử lý
technical fact; nó không biến URL bất kỳ thành giá cấu hình. Chỉ
`ResolvedProductFact` có evidence khớp product, field, value và `verified=true`
mới được áp dụng rồi revalidate.
