# Lab 2: catalog, RAG và agent tools

Lab 2 tách exact catalog plane khỏi document retrieval plane. Catalog xử lý id,
loại máy, GPU/RAM/storage/price/availability và numeric filters. RAG xử lý chunk,
dense+sparse retrieval, reranking và evidence metadata.

Hiện implementation dùng fake in-memory adapters, chạy deterministic/offline.
PostgreSQL, Qdrant, Docling, BGE-M3 và OpenClaw thật là công việc tiếp theo.
