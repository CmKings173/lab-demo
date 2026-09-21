# Các quyết định còn mở

Cho đến khi chính sách nguồn catalog/pricing authoritative được chốt, hai
technical facts đã verified nhưng khác giá trị cho cùng field sẽ không được
tự động resolve. Đây là cách xử lý an toàn hiện tại, chưa phải chính sách
conflict production-ready.

- Chọn checkpoint Qwen3-8B cụ thể sau khi kiểm tra license và benchmark.
- Calibrate sizing coefficients bằng model/context/batch/concurrency thực tế.
- Chọn nguồn catalog, pricing authoritative và chu kỳ refresh.
- Xác định field nào bắt buộc có evidence theo từng hãng.
- Chọn dense/sparse weighting, reranker cutoff và giá trị `k` từ retrieval eval.
- Chọn OpenClaw release/deployment policy; runtime hiện chưa được tích hợp.
- Review thủ công 60 gold examples trước khi mở rộng lên dataset production.
- Chọn nguồn authoritative cho option price; thiếu bất kỳ selected component
  price nào thì tổng giá vẫn `PARTIAL/UNKNOWN`, không được suy diễn.
- Định nghĩa confidence interval và release threshold cho từng metric.
- Chọn UI sau khi API/workflow ổn định.
