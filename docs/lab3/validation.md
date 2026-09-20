# Validation Lab 3

Validation trả `PASS`, `FAIL` hoặc `UNKNOWN`. Budget chỉ PASS/FAIL khi giá
`COMPLETE`; giá partial/unknown tạo UNKNOWN. Fact thiếu chỉ được cập nhật từ
`ResolvedProductFact` có document metadata khớp product, field, value và đã
verified, sau đó toàn bộ cấu hình được revalidate.
