# Validation Lab 3

## Evidence và dữ liệu chưa biết

Document metadata sai kiểu hoặc ngoài miền của `Product` bị bỏ qua trước khi
apply. Nếu các document đã verified đưa ra giá trị khác nhau cho cùng field,
không tự chọn theo thứ tự hay rank: field vẫn `UNKNOWN` cho đến khi có chính sách
nguồn authoritative. Product và ProductConfiguration được validate lại sau apply.

## Giá cấu hình

`PriceBreakdown` là nguồn giá canonical. `price_status`, `estimated_price_vnd`,
`priced_components` và `missing_price_components` chỉ là các trường phản chiếu.
Validator và proposal verifier cùng kiểm tra chúng khớp với breakdown đã được
validate lại. Mâu thuẫn nội bộ là `FAIL price_contract`; giá thực sự còn thiếu
hoặc `PARTIAL` là `UNKNOWN price` khi có budget. Chỉ giá `COMPLETE` có total
mới được so với budget, bằng `price_breakdown.total_vnd`.

Validation trả `PASS`, `FAIL` hoặc `UNKNOWN`. Budget chỉ PASS/FAIL khi giá
`COMPLETE`; giá partial/unknown tạo UNKNOWN. Fact thiếu chỉ được cập nhật từ
`ResolvedProductFact` có document metadata khớp product, field, value và đã
verified, sau đó toàn bộ cấu hình được revalidate.

Storage là optional: nếu customer và sizing đều không đưa target thì không sinh
unknown storage. Khi có target, validator dùng giá trị lớn hơn giữa hai nguồn,
kiểm tra selected option, configured capacity và platform maximum. Tương tự, RAM
phải là option thật; max platform không đủ là `FAIL`, catalog option chưa đủ là
`UNKNOWN ram_option`.
