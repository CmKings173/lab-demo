# Validation Lab 3

Validation trả `PASS`, `FAIL` hoặc `UNKNOWN`. Budget chỉ PASS/FAIL khi giá
`COMPLETE`; giá partial/unknown tạo UNKNOWN. Fact thiếu chỉ được cập nhật từ
`ResolvedProductFact` có document metadata khớp product, field, value và đã
verified, sau đó toàn bộ cấu hình được revalidate.

Storage là optional: nếu customer và sizing đều không đưa target thì không sinh
unknown storage. Khi có target, validator dùng giá trị lớn hơn giữa hai nguồn,
kiểm tra selected option, configured capacity và platform maximum. Tương tự, RAM
phải là option thật; max platform không đủ là `FAIL`, catalog option chưa đủ là
`UNKNOWN ram_option`.
