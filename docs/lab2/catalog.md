# Catalog Lab 2

`Product` là platform AI Server/Workstation; `GPUOption` là lựa chọn GPU;
`ProductConfiguration` thuộc Lab 3 và mô tả cấu hình cụ thể. Unknown catalog
field giữ `None`, không đổi thành zero và không bị loại sớm khỏi candidate list.

`search_products` nhận structured filters: `product_type`, `min_ram_gb`,
`min_gpu_count`, `max_base_price_vnd`. Đây là giá nền/platform, không phải giá
full configured solution. `ProductSearchResult.total` là số match trước `limit`.
Schema cấm filter lạ; `query` và `limit` chạy xuyên suốt schema/runtime/API.

`compare_configurations` chỉ nhận IDs rồi lookup qua `ConfigurationRepository`;
agent không được gửi raw arbitrary configuration JSON.
