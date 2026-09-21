from shared.contracts import DocumentChunk, GPUOption, Product


def option_documents(product: Product, gpu: GPUOption, ram_capacity: int) -> list[DocumentChunk]:
    return [DocumentChunk(
        id=f"{product.id}-{owner}-{field}", text=f"Verified {field} {value}",
        product_id=product.id, source_url=f"https://example.invalid/{owner}/{field}",
        metadata={"field_name": field, "value": str(value),
                  "verified": "true", "option_id": owner},
    ) for owner, field, value in (
        (product.id, "max_gpu_slots", product.max_gpu_slots),
        (product.id, "max_ram_gb", product.max_ram_gb),
        (gpu.gpu_id, "memory_gb", gpu.memory_gb),
        (f"ram-{ram_capacity}", "capacity_gb", ram_capacity),
    )]
