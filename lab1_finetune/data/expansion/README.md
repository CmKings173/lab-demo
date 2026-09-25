# Pipeline mở rộng dữ liệu Lab 1

Thư mục này chứa pipeline sinh dữ liệu cục bộ, deterministic và không gọi LLM/API.
`gold_specs.json` là 60 mẫu seed đã curate; pipeline không đọc để mutate hoặc nhân bản
các mẫu đó. Seed chỉ đóng vai trò behavioral reference ở các test/regression hiện có.

## Các bước

1. `spec.py` định nghĩa 12 nhóm tình huống, quota, personas, difficulty và tỷ lệ
   single/multi-turn. Tổng quota mặc định là 1.200 mẫu.
2. `personas.py` cung cấp bảy persona: người không chuyên, quản lý, mua sắm,
   IT tổng quát, developer, ML engineer và solution architect.
3. `scenarios.py` tạo context đa dạng về model, mục đích dùng, ngân sách, số người
   dùng, context length và training method.
4. `generator.py` sinh các hội thoại cùng tool call/result hợp lệ. Product ID trong
   fixture là synthetic và được xoay vòng; assistant không được nêu một product fact
   nếu fact đó không có trong tool result.
5. `diversity.py` kiểm tra contract, duplicate ID, exact duplicate, near-duplicate,
   legacy wording và product claim. Near-duplicate dùng blocking token trigram,
   giao nhau token trigram và `SequenceMatcher` cùng ngưỡng 0.92; tỷ lệ mẫu
   near-user phải dưới 2%.
6. `build_expanded.py` split theo semantic group trong từng scenario family, không random từng row, rồi xuất
   JSONL và Qwen JSONL từ exporter dùng chung.

Artifacts mở rộng nằm dưới `lab1_finetune/data/generated/` để không ghi đè các
artifact seed hiện có:

```text
generated/
├── train.jsonl
├── validation.jsonl
├── manifest.json
└── exports/
    ├── train_qwen.jsonl
    └── validation_qwen.jsonl
```

Benchmark độc lập không sinh từ generator này. Nó có recipe, wording, giá trị và
template ID riêng; được freeze tại `lab1_finetune/evaluation/gold_eval.jsonl` cùng
`eval_manifest.json`. Isolation gate so sánh benchmark với cả training corpus và
reject exact/near overlap ở ngưỡng 0.92.

Chạy lại artifacts:

```bash
python -m lab1_finetune.data.build_expanded
python -m lab1_finetune.evaluation.build_benchmark
```

`source_type` của dữ liệu mở rộng là `synthetic_expansion_unreviewed`; chưa được gọi
là dữ liệu human-reviewed cho tới khi có review thủ công rõ ràng.

## Quy tắc corrective hiện tại

- Mỗi dòng giữ `semantic_template_id` ổn định theo recipe và có thêm
  `semantic_group_id`. Split train/validation theo nhóm ngữ nghĩa, không tách các
  biến thể cùng nhóm sang hai phía; cả hai split vẫn phủ đủ 12 family.
- Wording dùng nhiều cấu trúc theo persona và bối cảnh. Không dùng hậu tố chung
  kiểu `VARIATION_NOTES`; các khác biệt phải đến từ mục tiêu, cách dùng, model,
  quy mô người dùng, ràng buộc hoặc bước tool thực tế.
- `difficulty` được suy ra bởi `infer_difficulty()` từ số tool, multi-turn,
  missing fields, abstention và tool failure; không suy ra từ số thứ tự dòng.
- Audit duplicate tách riêng user hiện tại, history + user, final và toàn hội
  thoại. Near-duplicate dùng blocking token trigram kết hợp giao nhau token
  trigram và `SequenceMatcher` cùng ngưỡng 0.92; quality gate yêu cầu exact user/
  conversation bằng 0 và tỷ lệ mẫu near-user dưới 2%.
- `review_sample.jsonl` có 84 dòng stratified (12 family × 7 persona), kèm
  `review_manifest.json`; các dòng vẫn giữ nhãn `synthetic_expansion_unreviewed`.

## Benchmark độc lập

`lab1_finetune/evaluation/gold_eval.jsonl` có 120 case được sinh từ recipe và
namespace template riêng. Benchmark được kiểm tra cả leakage với training lẫn
duplicate nội bộ; difficulty dùng cùng `infer_difficulty()` với expansion.
Manifest ghi rõ exact/near nội bộ và số template giao nhau (mục tiêu là 0).
