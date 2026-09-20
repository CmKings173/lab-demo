# Lab 1: behavior fine-tuning

Lab 1 dạy hành vi: nhận diện intent, trích xuất requirement, hỏi dữ liệu thiếu,
chọn tool, xử lý tool result và từ chối suy đoán. Catalog fact và tài liệu sản
phẩm không được nhồi vào model weights. Chain-of-thought không được thu thập.

Code nằm trong `lab1_finetune/{data,training,evaluation}`. `ModelClient` chỉ thuộc
evaluation của Lab 1; orchestration Lab 2/3 sau này thuộc OpenClaw.
