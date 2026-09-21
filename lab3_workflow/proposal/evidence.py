from shared.contracts import DocumentHit, Evidence, ProductConfiguration
from shared.contracts.models import EvidenceKind


def build_evidence(configurations: list[ProductConfiguration],
                   hits: list[DocumentHit]) -> list[Evidence]:
    evidence = []
    for cfg in configurations:
        product = cfg.product
        facts = [(product.id, "max_gpu_slots", product.max_gpu_slots),
                 (product.id, "max_ram_gb", product.max_ram_gb)]
        if cfg.selected_gpu:
            facts.append((cfg.selected_gpu.gpu_id, "memory_gb", cfg.selected_gpu.memory_gb))
        if cfg.selected_ram:
            facts.append((cfg.selected_ram.option_id, "capacity_gb", cfg.selected_ram.capacity_gb))
        for owner, field, value in facts:
            hit = next((hit for hit in hits if hit.chunk.product_id == product.id
                        and hit.chunk.source_url
                        and hit.chunk.metadata.get("field_name") == field
                        and hit.chunk.metadata.get("option_id", product.id) == owner
                        and hit.chunk.metadata.get("value") == str(value)
                        and hit.chunk.metadata.get("verified") == "true"), None)
            if hit:
                evidence.append(Evidence(
                    claim=f"{owner}.{field}", value=value, product_id=product.id,
                    source_url=hit.chunk.source_url, document_id=hit.chunk.id,
                    chunk_id=hit.chunk.id, page=hit.chunk.page, verified=True,
                ))
        if cfg.selected_gpu:
            evidence.append(Evidence(
                claim=f"{cfg.configuration_id}.total_vram_gb", value=cfg.total_vram_gb,
                product_id=product.id, kind=EvidenceKind.DERIVED,
                derivation_rule="selected_gpu.memory_gb * gpu_count",
                depends_on=[f"{cfg.selected_gpu.gpu_id}.memory_gb",
                            f"{cfg.configuration_id}.gpu_count"],
                verified=False,
            ))
        if cfg.selected_ram:
            evidence.append(Evidence(
                claim=f"{cfg.configuration_id}.configured_ram_gb", value=cfg.configured_ram_gb,
                product_id=product.id, kind=EvidenceKind.DERIVED,
                derivation_rule="selected_ram.capacity_gb",
                depends_on=[f"{cfg.selected_ram.option_id}.capacity_gb"],
                verified=False,
            ))
    return evidence


def verify_derived(item: Evidence, cfg: ProductConfiguration,
                   evidence: list[Evidence]) -> bool:
    pid = cfg.product.id
    if item.claim == f"{cfg.configuration_id}.total_vram_gb":
        gpu = cfg.selected_gpu
        if not gpu or not gpu.supports(cfg.product) or cfg.gpu_count is None:
            return False
        if cfg.product.max_gpu_slots is None or cfg.gpu_count > cfg.product.max_gpu_slots:
            return False
        dependencies = {f"{gpu.gpu_id}.memory_gb": gpu.memory_gb}
        configuration_dependencies = {f"{cfg.configuration_id}.gpu_count": cfg.gpu_count}
        compatibility_facts = {f"{pid}.max_gpu_slots": cfg.product.max_gpu_slots}
        value = cfg.total_vram_gb
        rule = "selected_gpu.memory_gb * gpu_count"
    elif item.claim == f"{cfg.configuration_id}.configured_ram_gb":
        ram = cfg.selected_ram
        if not ram or not ram.supports(cfg.product):
            return False
        if cfg.product.max_ram_gb is None or ram.capacity_gb > cfg.product.max_ram_gb:
            return False
        dependencies = {f"{ram.option_id}.capacity_gb": ram.capacity_gb}
        configuration_dependencies = {}
        compatibility_facts = {f"{pid}.max_ram_gb": cfg.product.max_ram_gb}
        value = ram.capacity_gb
        rule = "selected_ram.capacity_gb"
    else:
        return False
    expected_dependencies = set(dependencies) | set(configuration_dependencies)
    if (
        item.value != value
        or item.derivation_rule != rule
        or set(item.depends_on) != expected_dependencies
    ):
        return False
    required_direct_facts = dependencies | compatibility_facts
    return all(any(e.claim == claim and e.value == expected and e.product_id == pid
                   and e.kind == EvidenceKind.DIRECT and e.verified
                   and e.document_id and e.source_url for e in evidence)
               for claim, expected in required_direct_facts.items())
