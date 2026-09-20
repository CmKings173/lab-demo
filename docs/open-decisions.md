# Các quyết định còn mở

- Chọn checkpoint Qwen3-8B cụ thể sau khi kiểm tra license và benchmark.
- Calibrate sizing coefficients bằng model/context/batch/concurrency thực tế.
- Chọn nguồn catalog, pricing authoritative và chu kỳ refresh.
- Xác định field nào bắt buộc có evidence theo từng hãng.
- Chọn dense/sparse weighting, reranker cutoff và giá trị `k` từ retrieval eval.
- Chọn OpenClaw release/deployment policy; runtime hiện chưa được tích hợp.
- Review thủ công 50 gold examples trước khi mở rộng lên dataset production.
- Định nghĩa confidence interval và release threshold cho từng metric.
- Chọn UI sau khi API/workflow ổn định.
