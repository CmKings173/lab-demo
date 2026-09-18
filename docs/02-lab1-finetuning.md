# Lab 1: model fine-tuning

## Objective

Fine-tune Qwen3-8B with LoRA/PEFT so the model improves requirement
understanding, structured extraction, missing-field questions, tool decisions
and uncertainty behavior. It must not memorize the product catalog; product
facts belong to Lab 2.

## Dataset strategy

Each example contains an id, user request, expected structured output, source
and tags. The future dataset should include complete requests, incomplete
requests, inference versus fine-tune usage, budget and user-count variation,
tool-needed decisions, unsupported-product questions and explicit unknowns.

Split train/validation/test by stable example id. Prevent leakage by keeping
near-duplicate customer scenarios in one split and keeping catalog/datasheet
content out of the training labels.

## Baseline configuration

The skeleton defaults to Qwen3-8B, LoRA rank 16, alpha 32, dropout 0.05,
BF16 enabled and QLoRA disabled. The exact Qwen3 variant, sequence length,
batching and optimizer remain open until hardware benchmarking. QLoRA is only a
fallback after a measured memory need.

## Future pipeline

1. Validate and normalize dataset examples.
2. Split deterministically into train, validation and test.
3. Train with Transformers, TRL, PEFT and Accelerate.
4. Record loss, wall time, VRAM and configuration.
5. Evaluate extraction, missing information, structure, tool choice and
   unsupported-field behavior.
6. Merge the adapter only after evaluation and preserve base/adapter artifacts.

`lab1/src/train.py` and `merge.py` are interfaces only in this task. No GPU
training is run here.
