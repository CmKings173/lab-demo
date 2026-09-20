# Training Lab 1

`lab1_finetune/training` chứa config, train và merge entry points. Foundation
chưa tải checkpoint, chưa huấn luyện LoRA/PEFT và chưa merge adapter. Khi triển
khai phải cố định model id, dataset hash, seed, hyperparameters và môi trường.

Exporter hiện tạo Qwen-compatible JSONL gồm `messages` và `tools`. Chỉ bắt đầu
training sau khi gold seed được human-review và production split được khóa.
