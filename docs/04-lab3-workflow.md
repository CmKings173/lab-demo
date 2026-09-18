# Lab 3: agentic workflow

```mermaid
stateDiagram-v2
  [*] --> RECEIVED
  RECEIVED --> ANALYZING_REQUIREMENT
  ANALYZING_REQUIREMENT --> MISSING_INFORMATION: required field absent
  ANALYZING_REQUIREMENT --> READY_FOR_SIZING: complete
  MISSING_INFORMATION --> ANALYZING_REQUIREMENT: user supplies fields
  READY_FOR_SIZING --> SIZING
  SIZING --> SIZING_FAILED: rule error
  SIZING --> SEARCHING_PRODUCTS: success
  SEARCHING_PRODUCTS --> NO_SUITABLE_PRODUCT: no candidates
  SEARCHING_PRODUCTS --> VALIDATING_PRODUCTS: candidates
  VALIDATING_PRODUCTS --> INSUFFICIENT_PRODUCT_DATA: unknown facts
  VALIDATING_PRODUCTS --> VALIDATION_FAILED: no valid candidate
  VALIDATING_PRODUCTS --> READING_DOCUMENTS: valid candidates
  READING_DOCUMENTS --> COMPARING_OPTIONS
  COMPARING_OPTIONS --> GENERATING_PROPOSAL
  GENERATING_PROPOSAL --> PROPOSAL_FAILED: service error
  GENERATING_PROPOSAL --> VERIFYING_PROPOSAL
  VERIFYING_PROPOSAL --> PROPOSAL_FAILED: missing evidence
  VERIFYING_PROPOSAL --> COMPLETED: verified
```

Required input is model size, usage (inference/fine-tune) and budget. Optional
input includes concurrent users, context length, storage and expansion. Derived
fields include estimated VRAM, recommended VRAM/RAM and minimum GPU count.

The workflow stops with `MISSING_INFORMATION` before search if a required value
is absent. It never invents a value. Product validation is code-driven and
returns failures, warnings and unknown fields. Proposal verification requires
selected products and sources. The deterministic orchestrator is deliberately
small so a future workflow engine can replace it without changing contracts.
