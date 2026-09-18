# Evaluation metrics

All metrics are calculated on a versioned, family-isolated test split. A result
is reported with numerator, denominator, dataset manifest hash and confidence
interval where applicable.

## Lab 1 behavior

- **Intent accuracy** = examples with exact intent label / evaluated examples.
- **Missing-field micro F1** uses field-level true/false positives/negatives
  across all examples: `2PR/(P+R)`.
- **Tool-needed accuracy** = exact `should_call_tool` matches / examples.
- **Expected-tool accuracy** = exact tool-name matches / examples where a tool
  is required.
- **Tool-argument validity** = schema-valid calls / emitted calls.
- **Structured-output validity** = parseable, schema-valid outputs / outputs
  expected to be structured.
- **Unsupported product-fact rate** = unsupported catalog claims / all product
  claims. Target is zero.
- **Family leakage rate** = families present in multiple splits / all families.
  Target is zero and any non-zero result fails dataset release.

Compare base versus adapter on the same test families. Record model id, adapter
id, seed, training config, loss, wall time and peak VRAM; do not record hidden
chain-of-thought.

## Lab 2 retrieval

- **Recall@k** = relevant document ids retrieved in top k / all relevant ids.
- **Precision@k** = relevant hits in top k / k.
- **MRR** = mean reciprocal rank of the first relevant hit.
- **nDCG@k** uses graded relevance and log-discounted rank.
- **Product filter precision/recall** is calculated separately on exact catalog
  constraints; unknown fields are excluded from definite-failure counts.
- **Grounded claim precision** = claims backed by matching evidence / claims.
- **Source correctness** = evidence URLs/pages matching the gold source / all
  cited evidence.
- **Unknown handling accuracy** = unknown facts returned as unknown / gold
  unknown facts.

Report dense, sparse and hybrid retrieval independently, including retrieval
and rerank scores retained in each `DocumentHit`.

## Lab 3 workflow

- **Path accuracy** = runs whose state sequence exactly matches gold / runs.
- **Missing-information stop accuracy** = incomplete runs ending before catalog
  search / incomplete runs.
- **Sizing agreement** = resource fields within the approved rule tolerance /
  sizing cases; report each field separately.
- **Validation status accuracy** = exact PASS/FAIL/UNKNOWN matches / configs.
- **Configuration feasibility** = verified configs / proposed configs.
- **Proposal completion rate** = verified `COMPLETE` runs / complete-input runs.
- **Budget violation rate** = proposals above a known budget / priced proposals.
- **Unsupported proposal claim rate** = claims without matching verified
  evidence / proposal claims. Target is zero.
- **Evidence coverage** = required proposal fields with verified evidence /
  required proposal fields.

Any proposal with an unsupported claim, invalid configuration or missing
required evidence is a failed run even when prose quality is high.
