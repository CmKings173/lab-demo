# Sizing Lab 3

Sizing ước lượng demand, không chọn sản phẩm hay số GPU. GPU count được builder
tính từ `GPUOption.memory_gb` thật của từng candidate. Coefficients hiện là rule
deterministic để test được; chưa phải benchmark production.
`context_length=None` và `concurrent_users=None` tạm dùng 4096 token/1 user nhưng
phải xuất hiện trong `assumptions`. Giá trị đã cung cấp không bị ghi thành default.
Fine-tune thiếu `training_method` luôn có warning; confidence vẫn ở mức thấp cho
đến khi rule được benchmark.
