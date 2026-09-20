# Ingestion Lab 2

Pipeline dự kiến: tài liệu hãng -> parse/chunk -> metadata product/source/page ->
dense+sparse embedding -> vector store. Mỗi chunk cần provenance đủ để evidence
verifier đối chiếu product id, field, value và trạng thái xác minh.

Foundation chỉ định nghĩa contract; chưa chạy parser, embedding hay Qdrant ingest.
