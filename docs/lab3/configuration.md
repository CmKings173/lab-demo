# Configuration Lab 3

Builder tạo `ProductConfiguration` từ selected GPU và RAM/storage option có thật.
Nó chọn option nhỏ nhất đủ capacity (ví dụ 176GB chọn 256GB); storage chỉ được
chọn khi customer/sizing có target. CPU giữ `None`, không tự lấy lựa chọn đầu tiên.

Typed `PriceBreakdown` lấy giá từ platform và chính các selected options.
`base_price_includes` cho biết CPU/RAM/storage nào đã nằm trong giá nền. Thiếu
một component cần thiết thì giá giữ `PARTIAL/UNKNOWN`; `COMPLETE` không thể còn
missing components. Storage không có capacity target chỉ được tính chi phí tăng
thêm bằng 0 khi base price xác nhận đã gồm storage; nếu không, component này vẫn
unknown dù validation capacity được phép bỏ qua.
