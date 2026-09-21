# Workflow Lab 3

Luồng chính: `ANALYZE -> CHECK_MISSING_INFORMATION -> SIZE -> SEARCH_PRODUCTS ->
BUILD_CONFIGURATIONS -> VALIDATE_INITIAL`. Nếu có unknown fact, workflow chạy
`RESOLVE_UNKNOWN_FACTS -> READ_DOCUMENTS -> APPLY_VERIFIED_FACTS -> REVALIDATE`.
Chỉ configuration PASS mới đi qua compare, proposal và evidence verification.

Document resolution chỉ nhận technical unknown fields. Price `PARTIAL/UNKNOWN`
không được gửi sang product fact resolver và sẽ kết thúc ở
`INSUFFICIENT_PRODUCT_DATA` nếu không có pricing data. Storage không được yêu cầu
không tạo unknown và workflow có thể `COMPLETE` khi các fact/price còn lại đầy đủ.

Các terminal state bao gồm missing information, sizing failure, no suitable
product, insufficient product data, validation failure, proposal failure và complete.
