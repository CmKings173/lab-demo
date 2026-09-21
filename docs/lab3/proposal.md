# Proposal Lab 3

Comparison nhận concrete configuration ids và hiển thị GPU, count, VRAM, RAM,
storage, price status, price và unknown facts. Proposal có thể sinh Option A/B.
Verifier từ chối configuration không tồn tại, constraint không đạt, budget chưa
xác định hoặc claim thiếu evidence khớp. `DIRECT` evidence liên kết verified
document fact; `DERIVED` evidence (ví dụ total VRAM) ghi rule/dependencies và
được recompute từ selected option + configuration facts, không đòi datasheet có
sẵn literal tổng.

Derived evidence được tạo ở trạng thái chưa verified và chỉ được verifier chấp
nhận sau khi recompute cùng chuỗi direct facts. Nếu customer có budget, final
verifier cũng từ chối mọi configuration chưa có `COMPLETE` price.
