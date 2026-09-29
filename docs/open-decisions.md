# Các quyết định còn mở

## Lab2 retrieval decision already made

WeKnora v0.8.0 is the selected document-RAG service (ADR 011). Dense/sparse
weighting, reranker cutoffs, vector-store choice and retrieval `k` are not Lab2
application-stack decisions: they belong to the locally configured WeKnora
deployment and should be evaluated against the Lab2 retrieval benchmark. The old
retrieval bullets below are superseded to that extent. The six-tool OpenClaw
integration is implemented in source; keep the release/deployment policy and live
GB300 end-to-end verification open until the supported local interface is exercised.

Cho đến khi chính sách nguồn catalog/pricing authoritative được chốt, hai
technical facts đã verified nhưng khác giá trị cho cùng field sẽ không được
tự động resolve. Đây là cách xử lý an toàn hiện tại, chưa phải chính sách
conflict production-ready.

- Qwen3-14B là lựa chọn runtime hiện tại; vẫn cần chốt checkpoint cụ thể sau khi
  kiểm tra license và benchmark trên GB300.
- Calibrate sizing coefficients bằng model/context/batch/concurrency thực tế.
- Chọn nguồn catalog, pricing authoritative và chu kỳ refresh.
- Xác định field nào bắt buộc có evidence theo từng hãng.
- Calibrate WeKnora-local model/retrieval configuration against the Lab2 retrieval
  evaluation; do not implement a parallel application-level embedding/reranker stack.
- Chốt OpenClaw release/deployment policy và xác minh live E2E trên GB300; source
  integration hiện đã có nhưng chưa phải là bằng chứng deployment/runtime thực tế.
- Review thủ công 60 gold examples trước khi mở rộng lên dataset production.
- Chọn nguồn authoritative cho option price; thiếu bất kỳ selected component
  price nào thì tổng giá vẫn `PARTIAL/UNKNOWN`, không được suy diễn.
- Định nghĩa confidence interval và release threshold cho từng metric.
- Chọn UI sau khi API/workflow ổn định.
