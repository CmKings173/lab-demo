# Configuration Lab 3

Builder tạo `ProductConfiguration` cụ thể với selected GPU, GPU count, RAM,
storage, CPU và component prices. Không có fallback CPU đầu tiên hoặc storage
1000GB. Price status là `COMPLETE`, `PARTIAL` hoặc `UNKNOWN`; priced/missing
components được ghi rõ để downstream không hiểu nhầm tổng giá.
