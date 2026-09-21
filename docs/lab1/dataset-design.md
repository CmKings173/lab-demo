# Thiết kế dataset Lab 1

Gold seed là Vietnamese behavior dataset, không phải catalog knowledge. Nó có 60
mẫu thuộc 25 scenario family: 50 core utterances và 10 multi-tool trajectories.
Mọi product, giá và tool result đều dùng ID `DEMO-*` hư cấu để dạy cách đọc
evidence mà không ghi nhớ catalog thật.

Mỗi tool-calling sample khai báo explicit arguments, typed `ToolResult`, final
answer và ordered `expected_tool_calls`; không có default filter/query/result hay
generic final fallback. Label còn giữ intent per-example, structured-output và
abstention expectation.

Split dùng `scenario_family_id`, seed 42: 20/2/3 families, hiện tương ứng 46/8/6
examples. Một family xuất hiện ở nhiều split là lỗi release. Validator dùng chung
Pydantic argument/result contracts với runtime và so cả sequence lẫn normalized args.

Nguồn authoring chuẩn là `lab1_finetune/data/gold_specs.json`. File seed JSONL,
splits và manifest là generated artifacts được tái tạo bằng
`python -m lab1_finetune.data.build_artifacts`; build chạy semantic validator
trước khi ghi bất kỳ release artifact nào.
