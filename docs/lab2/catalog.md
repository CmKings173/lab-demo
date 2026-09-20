# Catalog Lab 2

`Product` là platform AI Server/Workstation; `GPUOption` là lựa chọn GPU;
`ProductConfiguration` thuộc Lab 3 và mô tả cấu hình cụ thể. Unknown catalog
field giữ `None`, không đổi thành zero và không bị loại sớm khỏi candidate list.

`search_products` nhận structured filters: `product_type`, `min_ram_gb`,
`min_gpu_count`, `max_price_vnd`. Schema cấm filter lạ. `get_product` truy xuất
một product id. PostgreSQL adapter tương lai phải giữ đúng contract này.
