# Demo scenarios

## 1. Complete workstation request

- **Input:** Vietnamese request with model size, inference usage, budget and concurrency.
- **Extracted requirement:** all required fields plus workstation preference.
- **Missing fields:** none.
- **Expected tool calls:** `estimate_ai_requirements`, `search_products`,
  `search_product_documents`, `compare_products`.
- **Expected workflow path:** ANALYZE → CHECK_MISSING_INFORMATION → SIZE →
  SEARCH_PRODUCTS → BUILD_CONFIGURATIONS → VALIDATE → READ_DOCUMENTS → COMPARE
  → GENERATE_PROPOSAL → VERIFY → COMPLETE.
- **Expected result:** verified workstation configuration with Option A and evidence.

## 2. Complete AI Server request with alternatives

- **Input:** English server request with model size, fine-tune usage, storage and budget.
- **Extracted requirement:** complete server workload and constraints.
- **Missing fields:** none.
- **Expected tool calls:** sizing, product search, product document search and comparison.
- **Expected workflow path:** complete path through document reading and comparison.
- **Expected result:** Option A and Option B when two configurations pass.

## 3. Missing budget

- **Input:** request includes model size and usage but no budget.
- **Extracted requirement:** model and usage only.
- **Missing fields:** `budget_vnd`.
- **Expected tool calls:** none.
- **Expected workflow path:** ANALYZE → CHECK_MISSING_INFORMATION → MISSING_INFORMATION.
- **Expected result:** missing-fields payload plus a question; current run ends.

## 4. Missing usage

- **Input:** request includes model size and budget but no intended usage.
- **Extracted requirement:** model and budget only.
- **Missing fields:** `usage`.
- **Expected tool calls:** none.
- **Expected workflow path:** ANALYZE → CHECK_MISSING_INFORMATION → MISSING_INFORMATION.
- **Expected result:** clarification question and no catalog search.

## 5. No catalog platform

- **Input:** complete constraints outside available platform capabilities.
- **Extracted requirement:** complete.
- **Missing fields:** none.
- **Expected tool calls:** sizing then `search_products`.
- **Expected workflow path:** ANALYZE → CHECK_MISSING_INFORMATION → SIZE →
  SEARCH_PRODUCTS → NO_SUITABLE_PRODUCT.
- **Expected result:** explicit no-platform result without invented alternatives.

## 6. Unknown catalog data

- **Input:** complete request; catalog candidate lacks GPU or RAM capability facts.
- **Extracted requirement:** complete.
- **Missing fields:** none in the customer request.
- **Expected tool calls:** sizing and product search.
- **Expected workflow path:** through BUILD_CONFIGURATIONS and VALIDATE, then
  INSUFFICIENT_PRODUCT_DATA.
- **Expected result:** UNKNOWN fields listed; no zero substitution and no proposal.

## 7. All configurations fail

- **Input:** complete request whose known constraints exceed every configuration.
- **Extracted requirement:** complete.
- **Missing fields:** none.
- **Expected tool calls:** sizing and product search.
- **Expected workflow path:** through VALIDATE → VALIDATION_FAILED.
- **Expected result:** definite failures with actual and required values.

## 8. Unsupported proposal claim

- **Input:** complete request with at least one valid configuration.
- **Extracted requirement:** complete.
- **Missing fields:** none.
- **Expected tool calls:** full sizing/search/document/comparison chain.
- **Expected workflow path:** full path to VERIFY → PROPOSAL_FAILED.
- **Expected result:** verifier rejects a claim without matching verified evidence.
