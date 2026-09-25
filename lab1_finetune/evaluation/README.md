# Lab 1 model evaluation (GB300)

This evaluates the frozen 120-case `gold_eval.jsonl` without changing it or
calling real product/document tools. Each assistant turn is evaluated against
the preceding benchmark conversation prefix. Earlier assistant tool calls and
tool results are replayed from the gold fixture (teacher forcing); the current
gold assistant turn and final answer are never included in the model request.

The client uses vLLM's [OpenAI-compatible Chat Completions API](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html).
Qwen3 tool calls require vLLM's automatic tool choice and Hermes parser, per
[Qwen's vLLM guide](https://qwen.readthedocs.io/en/v3.0/deployment/vllm.html).
The evaluator sends `temperature=0` and disables Qwen3 thinking by default for
both Base and LoRA. Use the same evaluator flags for both runs.

Run these commands from the repository root on the GB300. In terminal 1:

```bash
vllm serve Qwen/Qwen3-14B --host 127.0.0.1 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser hermes
```

In terminal 2, after the server is ready:

```bash
python -m lab1_finetune.evaluation.run_model_eval \
  --base-url http://127.0.0.1:8000/v1 \
  --model Qwen/Qwen3-14B \
  --output artifacts/lab1/eval/base.json
```

Stop the Base server. Find and select the *actual* trained adapter directory:

```bash
find artifacts/lab1/runs -mindepth 2 -maxdepth 2 -type d -name best_adapter -print
read -r -p 'Paste the selected best_adapter path: ' ADAPTER_PATH
ADAPTER_PATH="$(realpath "$ADAPTER_PATH")"
test -f "$ADAPTER_PATH/adapter_config.json"
```

Restart terminal 1 with the same base model and the selected adapter:

```bash
vllm serve Qwen/Qwen3-14B --host 127.0.0.1 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --enable-lora --lora-modules "qwen3-14b-lora=$ADAPTER_PATH"
```

The `--lora-modules name=path` syntax and model-name selection are documented
by [vLLM's LoRA serving guide](https://docs.vllm.ai/en/latest/features/lora/).
In terminal 2:

```bash
python -m lab1_finetune.evaluation.run_model_eval \
  --base-url http://127.0.0.1:8000/v1 \
  --model qwen3-14b-lora \
  --output artifacts/lab1/eval/lora.json

python -m lab1_finetune.evaluation.compare_results \
  --base artifacts/lab1/eval/base.json \
  --candidate artifacts/lab1/eval/lora.json
```

If your local vLLM server requires an API key, set `LAB1_EVAL_API_KEY` in the
shell before evaluating. Do not put the key in the command line or results.
`--timeout`, `--max-tokens`, and `--enable-thinking` are optional; keep them
identical for both runs. Comparison rejects differing benchmark hashes, case
orders, or decoding configurations.

Each result JSON stores per-case inputs, gold labels, model outputs, tool calls,
metrics and errors. A bad case does not stop later cases; `failed_cases` is
reported separately. Aggregate metric denominators include only successful
cases and are shown as `count`. Tool-call/name/argument/sequence metrics are
deterministic comparisons against the frozen labels; `unexpected_tool_call_rate`
and `missing_tool_call_rate` are case rates. `abstention_accuracy` uses a small
Vietnamese phrase matcher, so it is **only a proxy**, not semantic answer
quality. The runner does not score free-form factual correctness or perform an
LLM-as-judge assessment. Teacher forcing does not measure how the model would
recover from its own earlier tool mistakes in a live agent loop.
