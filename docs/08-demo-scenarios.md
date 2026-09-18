# Demo scenarios

| # | Scenario | Expected path | Expected final status |
|---|---|---|---|
| 1 | Complete workstation request | analyze → size → search → validate → proposal | completed |
| 2 | Complete AI Server request | same path with server candidates | completed |
| 3 | Missing budget | analyze → ask user | missing_information |
| 4 | Missing usage | analyze → ask user | missing_information |
| 5 | No product meets exact filters | size → catalog search | no_suitable_product |
| 6 | Candidate lacks VRAM or RAM facts | search → validation | insufficient_product_data |
| 7 | Several products fit | validate → compare → proposal options | completed |
| 8 | Products exceed budget | search → validation | validation_failed or no_suitable_product |

Each scenario should preserve the original input, extracted required/optional
fields, derived sizing, controlled tool calls, product/document evidence and
final state. A missing-field scenario must show no product search call. An
unknown product field must be displayed as unknown rather than inferred.
