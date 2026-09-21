# Agent tools Lab 2

Tool contract dùng chung gồm `search_products`, `get_product`,
`search_product_documents`, `compare_products`, `compare_configurations` và
`estimate_ai_requirements`. Product comparison thuộc catalog; configuration
comparison thuộc workflow. OpenClaw tương lai chỉ được gọi các domain operation
này, không được cấp arbitrary SQL hoặc shell. JSON schema của cả sáu tool được
sinh từ `TOOL_ARG_MODELS`; OpenClaw binding, API wrapper và gold validator cùng
validate các field như `query`, `limit`, `top_k`, configuration IDs và toàn bộ
sizing context/concurrency/training method.
