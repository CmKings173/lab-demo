# Lab 3: configuration proposal workflow

```mermaid
stateDiagram-v2
  [*] --> ANALYZE
  ANALYZE --> CHECK_MISSING_INFORMATION
  CHECK_MISSING_INFORMATION --> MISSING_INFORMATION: required field absent
  CHECK_MISSING_INFORMATION --> SIZE: complete
  SIZE --> SIZING_FAILED: rule error
  SIZE --> SEARCH_PRODUCTS: success
  SEARCH_PRODUCTS --> NO_SUITABLE_PRODUCT: no platforms
  SEARCH_PRODUCTS --> BUILD_CONFIGURATIONS: platforms found
  BUILD_CONFIGURATIONS --> VALIDATE
  VALIDATE --> INSUFFICIENT_PRODUCT_DATA: no PASS, at least one UNKNOWN
  VALIDATE --> VALIDATION_FAILED: all configurations FAIL
  VALIDATE --> READ_DOCUMENTS: at least one PASS
  READ_DOCUMENTS --> COMPARE
  COMPARE --> GENERATE_PROPOSAL
  GENERATE_PROPOSAL --> PROPOSAL_FAILED: service error
  GENERATE_PROPOSAL --> VERIFY
  VERIFY --> PROPOSAL_FAILED: evidence or constraint failure
  VERIFY --> COMPLETE: verified
```

Sizing returns resource demand and never chooses a GPU count. Configuration
building calculates GPU count from each actual `GPUOption.memory_gb`. Validation
uses `PASS`, `FAIL` and `UNKNOWN`; unknown data is never converted to zero.

The workflow is stateless in v1. `MISSING_INFORMATION` returns
`missing_fields` plus a question and ends the current run. When the user
answers, the caller creates a new enriched `CustomerRequirement` and starts a
new run. There is no resume-state protocol.

Document search is an injected interface and is called for every passing
configuration before comparison. Proposal generation can emit Option A and
Option B. Verification checks configuration existence, sizing, known budget,
claims and matching verified evidence.
