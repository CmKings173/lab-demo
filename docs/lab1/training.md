# Training Lab 1 trên GB300

Trainer dùng Qwen3-14B và LoRA BF16. Dữ liệu đầu vào là các Qwen export đã freeze:
`lab1_finetune/data/generated/exports/train_qwen.jsonl` và
`lab1_finetune/data/generated/exports/validation_qwen.jsonl`. Benchmark
`gold_eval.jsonl` chỉ dùng sau huấn luyện, không đưa vào trainer.

Lựa chọn Qwen3-14B cho lần chạy này thay thế baseline Qwen3-8B ghi trong
ADR 002; ADR cũ được giữ nguyên như lịch sử quyết định.

## Chuẩn bị môi trường

Chọn PyTorch/CUDA image đã được kiểm tra trên GB300 và ghi lại phiên bản PyTorch
của image đó. Sau đó cài project với extra `lab1-train`, gồm các phiên bản cố
định của Transformers, TRL, PEFT, Datasets và Accelerate:

```bash
python -m pip install -e '.[lab1-train]'
```

Model có thể là một snapshot local, ví dụ `/models/Qwen3-14B`, hoặc
`Qwen/Qwen3-14B` với `--model-revision` là commit SHA 40 ký tự. Cả model và
tokenizer được nạp từ cùng snapshot. Mặc định trainer chỉ đọc file local hoặc
cache; `--allow-download` phải được bật rõ ràng nếu cần tải model.

## Kiểm dữ liệu trước khi train

Chạy preflight trên GB300 bằng đúng tokenizer của model:

```bash
python -m lab1_finetune.training.train \
  --model-name /models/Qwen3-14B \
  --output-dir artifacts/lab1/qwen3-14b-run-001 \
  --preflight-only
```

Preflight xác thực JSONL, liên kết giữa tool call và tool result, rồi tính độ
dài token của mọi hội thoại sau chat template. Nếu có dòng vượt
`max_seq_length` (mặc định 4096), lệnh dừng và báo số dòng bị ảnh hưởng.
Chỉ tăng `--max-seq-length` sau khi kiểm khả năng bộ nhớ; trainer hiện giới hạn
tối đa 32768 token theo context native của Qwen3-14B.

## Huấn luyện

Sau khi preflight sạch, bỏ `--preflight-only` để chạy cùng cấu hình:

```bash
python -m lab1_finetune.training.train \
  --model-name /models/Qwen3-14B \
  --output-dir artifacts/lab1/qwen3-14b-run-001
```

Mỗi run cần output directory mới. Cấu hình ban đầu là LoRA `all-linear`, rank
16, alpha 32, dropout 0.05, BF16, learning rate 2e-4, cosine scheduler,
warmup 5%, weight decay 0.01 và tối đa 3 epoch. Trainer đánh giá và lưu mỗi
epoch, chọn checkpoint có validation loss thấp nhất. Sau khi tạo trainer,
preflight kiểm tra assistant-only mask: model phải học các assistant tool call
và câu trả lời, không học tool result như output của assistant.

Adapter tốt nhất được lưu dưới `best_adapter/`; `run_manifest.json` ghi config,
hash của hai export, độ dài token, phiên bản thư viện và metric training.
Đọc validation loss và kiểm hành vi tool/abstention trước khi quyết định giữ
checkpoint. Chạy independent benchmark trên `gold_eval.jsonl` sau cùng.

Máy Windows phát triển hiện tại không có GPU hoặc các thư viện training;
việc tương thích PyTorch/CUDA và chạy end-to-end phải được smoke-test trên GB300.
