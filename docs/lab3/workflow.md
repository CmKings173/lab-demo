# Workflow Lab 3

Luồng chính: `ANALYZE -> CHECK_MISSING_INFORMATION -> SIZE -> SEARCH_PRODUCTS ->
BUILD_CONFIGURATIONS -> VALIDATE_INITIAL`. Nếu có unknown fact, workflow chạy
`RESOLVE_UNKNOWN_FACTS -> READ_DOCUMENTS -> APPLY_VERIFIED_FACTS -> REVALIDATE`.
Chỉ configuration PASS mới đi qua compare, proposal và evidence verification.

Các terminal state bao gồm missing information, sizing failure, no suitable
product, insufficient product data, validation failure, proposal failure và complete.
