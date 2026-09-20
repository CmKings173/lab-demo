# Thiết kế dataset Lab 1

Gold seed có 50 mẫu tiếng Việt thuộc đúng 25 scenario family, mỗi family hai
biến thể. Label gồm intent, scenario type, requirement đã trích xuất,
missing fields, nhu cầu gọi tool, tool mong đợi và cờ cấm bịa product fact.

Split dùng `scenario_family_id`, seed 42, cho kết quả train/validation/test là
40/4/6 mẫu. Một family xuất hiện ở nhiều split là lỗi release. Validator còn
kiểm tra id trùng, role order, tool definition/call/result và label-tool mismatch.

Nguồn chuẩn là `lab1_finetune/data/seed/gold_seed_vi.jsonl`; split và manifest
được tái tạo bằng `python -m lab1_finetune.data.build_artifacts`.
