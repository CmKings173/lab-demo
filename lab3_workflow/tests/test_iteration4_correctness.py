import pytest
from pydantic import ValidationError

from adapters.fake.evidence import option_documents
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.service import ProductConfigurationBuilder
from lab3_workflow.evidence.service import DeterministicProductFactResolver
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.sizing.service import DeterministicSizingService
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    DocumentHit,
    EvidenceKind,
    GPUOption,
    PriceStatus,
    Product,
    ProductConfiguration,
    ProductType,
    RAMOption,
    ResolvedProductFact,
    SizingRequest,
    SizingResult,
    StorageOption,
    UsageType,
    ValidationStatus,
)


def _product(*, max_ram_gb: int | None = 512, max_storage_gb: int | None = 4000) -> Product:
    return Product(
        id="p-1",
        sku="P-1",
        name="Demo server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=4,
        max_ram_gb=max_ram_gb,
        max_storage_gb=max_storage_gb,
        base_price_vnd=100_000_000,
        base_price_includes={"chassis", "cpu"},
    )


def _gpu() -> GPUOption:
    return GPUOption(
        gpu_id="gpu-48",
        name="GPU 48GB",
        memory_gb=48,
        supported_product_ids=["p-1"],
        price_vnd=40_000_000,
    )


def _ram(capacity: int) -> RAMOption:
    return RAMOption(
        option_id=f"ram-{capacity}",
        capacity_gb=capacity,
        supported_product_ids=["p-1"],
        price_vnd=capacity * 100_000,
    )


def _storage(capacity: int) -> StorageOption:
    return StorageOption(
        option_id=f"storage-{capacity}",
        capacity_gb=capacity,
        supported_product_ids=["p-1"],
        price_vnd=capacity * 10_000,
    )


def _sizing(*, storage: int | None = None) -> SizingResult:
    return SizingResult(
        estimated_model_memory_gb=80,
        recommended_total_vram_gb=96,
        recommended_system_ram_gb=176,
        recommended_storage_gb=storage,
        confidence=0.5,
    )


def _requirement(*, storage: int | None = None) -> CustomerRequirement:
    return CustomerRequirement(
        model_size_b=32,
        usage=UsageType.INFERENCE,
        storage_requirement_gb=storage,
    )


def _fact_hit(value: str, *, doc_id: str = "doc-1", rerank: float | None = None,
              retrieval: float | None = 0.8) -> DocumentHit:
    return DocumentHit(
        chunk=DocumentChunk(
            id=doc_id,
            product_id="p-1",
            source_url=f"https://example.invalid/{doc_id}",
            text="Verified platform RAM specification",
            metadata={"field_name": "max_ram_gb", "value": value, "verified": "true"},
        ),
        rank=1,
        retrieval_method="fake",
        rerank_score=rerank,
        retrieval_score=retrieval,
    )


def _unknown_ram_configuration() -> ProductConfiguration:
    return ProductConfiguration(configuration_id="cfg", product=_product(max_ram_gb=None))


@pytest.mark.parametrize("raw", ["512", '"512"'])
def test_numeric_verified_fact_is_normalized_and_applied(raw: str) -> None:
    resolver = DeterministicProductFactResolver()
    configuration = _unknown_ram_configuration()
    facts = resolver.resolve(configuration, ["max_ram_gb"], [_fact_hit(raw)])

    assert len(facts) == 1
    assert facts[0].value == 512
    assert type(facts[0].value) is int
    assert resolver.apply(configuration, facts).product.max_ram_gb == 512


@pytest.mark.parametrize("raw", ['"abc"', "-1", "true", "null"])
def test_invalid_verified_fact_is_ignored(raw: str) -> None:
    resolver = DeterministicProductFactResolver()
    configuration = _unknown_ram_configuration()
    facts = resolver.resolve(configuration, ["max_ram_gb"], [_fact_hit(raw)])

    assert facts == []
    assert resolver.apply(configuration, facts).product.max_ram_gb is None


def test_duplicate_same_verified_value_is_not_conflict() -> None:
    resolver = DeterministicProductFactResolver()
    facts = resolver.resolve(_unknown_ram_configuration(), ["max_ram_gb"], [
        _fact_hit("512"), _fact_hit('"512"', doc_id="doc-2")
    ])

    assert len(facts) == 1
    assert facts[0].value == 512


def test_same_value_selects_highest_scoring_evidence_only() -> None:
    resolver = DeterministicProductFactResolver()
    facts = resolver.resolve(_unknown_ram_configuration(), ["max_ram_gb"], [
        _fact_hit("512", doc_id="unscored", retrieval=None),
        _fact_hit("512", doc_id="first", rerank=0.2),
        _fact_hit("512", doc_id="best", rerank=0.9),
        _fact_hit("512", doc_id="last", rerank=0.9),
    ])
    assert len(facts) == 1
    assert facts[0].document_id == "best"


@pytest.mark.parametrize("values", [("512", "1024"), ("1024", "512")])
def test_conflicting_verified_values_remain_unknown(values: tuple[str, str]) -> None:
    resolver = DeterministicProductFactResolver()
    configuration = _unknown_ram_configuration()
    hits = [_fact_hit(value, doc_id=f"doc-{index}") for index, value in enumerate(values)]
    assert resolver.resolve(configuration, ["max_ram_gb"], hits) == []
    direct_facts = [
        ResolvedProductFact(product_id="p-1", field_name="max_ram_gb", value=int(value),
                            source_url=hit.chunk.source_url, document_id=hit.chunk.id,
                            chunk_id=hit.chunk.id, evidence_text=hit.chunk.text, verified=True)
        for value, hit in zip(values, hits)
    ]
    assert resolver.apply(configuration, direct_facts).product.max_ram_gb is None


@pytest.mark.parametrize("rerank,retrieval", [(0.0, 0.8), (None, 0.0)])
def test_zero_evidence_score_remains_zero(rerank: float | None, retrieval: float) -> None:
    facts = DeterministicProductFactResolver().resolve(
        _unknown_ram_configuration(), ["max_ram_gb"],
        [_fact_hit("512", rerank=rerank, retrieval=retrieval)],
    )
    assert facts[0].confidence == 0.0


def test_evidence_without_scores_defaults_to_one() -> None:
    facts = DeterministicProductFactResolver().resolve(
        _unknown_ram_configuration(), ["max_ram_gb"],
        [_fact_hit("512", retrieval=None)],
    )
    assert facts[0].confidence == 1.0


def test_apply_revalidates_existing_configuration() -> None:
    resolver = DeterministicProductFactResolver()
    configuration = _unknown_ram_configuration()
    facts = resolver.resolve(configuration, ["max_ram_gb"], [_fact_hit("512")])
    forged = configuration.model_copy(update={"configured_ram_gb": -1})
    with pytest.raises(ValidationError):
        resolver.apply(forged, facts)


def test_apply_ignores_untyped_direct_fact() -> None:
    configuration = _unknown_ram_configuration()
    invalid = ResolvedProductFact(
        product_id="p-1", field_name="max_ram_gb", value=True,
        source_url="https://example.invalid/doc", document_id="doc", chunk_id="doc",
        evidence_text="Incorrect boolean RAM value", verified=True,
    )
    result = DeterministicProductFactResolver().apply(configuration, [invalid])
    assert result.product.max_ram_gb is None


def _priced_configuration(*, complete: bool = True) -> ProductConfiguration:
    return ProductConfigurationBuilder(
        [_gpu()], [_ram(256)], [_storage(2000)] if complete else []
    ).build([_product()], _sizing(storage=1500 if complete else None),
            _requirement(storage=1500 if complete else None))[0]


def _budget_requirement(budget: int = 500_000_000) -> CustomerRequirement:
    return _requirement(storage=1500).model_copy(update={"budget_vnd": budget})


def test_validator_rejects_price_mirror_mismatch() -> None:
    configuration = _priced_configuration()
    forged = configuration.model_copy(update={"estimated_price_vnd": 1})
    result = RuleBasedConfigurationValidator().validate(
        _budget_requirement(), _sizing(storage=1500), forged
    )
    assert result.status == ValidationStatus.FAIL
    assert any(f.field == "price_contract" for f in result.failures)


def test_validator_rejects_price_status_mismatch() -> None:
    forged = _priced_configuration().model_copy(update={"price_status": PriceStatus.PARTIAL})
    result = RuleBasedConfigurationValidator().validate(
        _budget_requirement(), _sizing(storage=1500), forged
    )
    assert result.status == ValidationStatus.FAIL
    assert any(f.field == "price_contract" for f in result.failures)


def test_validator_uses_breakdown_total_for_budget() -> None:
    configuration = _priced_configuration()
    breakdown_data = configuration.price_breakdown.model_dump(mode="python")
    breakdown_data["base_chassis_vnd"] += 600_000_000 - breakdown_data["total_vnd"]
    breakdown_data["total_vnd"] = 600_000_000
    configuration = ProductConfiguration.model_validate({
        **configuration.model_dump(mode="python"), "price_breakdown": breakdown_data,
    })
    result = RuleBasedConfigurationValidator().validate(
        _budget_requirement(), _sizing(storage=1500), configuration
    )
    assert result.status == ValidationStatus.FAIL
    assert any(f.field == "estimated_price_vnd" and f.actual == 600_000_000
               for f in result.failures)


def test_partial_breakdown_with_budget_is_unknown_not_fail() -> None:
    configuration = _priced_configuration(complete=False)
    result = RuleBasedConfigurationValidator().validate(
        _budget_requirement(), _sizing(storage=1500), configuration
    )
    assert result.status == ValidationStatus.UNKNOWN
    assert "price" in result.unknown_fields
    assert not any(f.field == "price_contract" for f in result.failures)


def test_complete_canonical_price_within_budget_passes() -> None:
    result = RuleBasedConfigurationValidator().validate(
        _budget_requirement(), _sizing(storage=1500), _priced_configuration()
    )
    assert result.status == ValidationStatus.PASS


def test_builder_selects_smallest_real_ram_and_storage_options() -> None:
    configuration = ProductConfigurationBuilder(
        [_gpu()],
        [_ram(128), _ram(256), _ram(512)],
        [_storage(1000), _storage(2000)],
    ).build([_product()], _sizing(), _requirement(storage=1500))[0]

    assert configuration.selected_ram.capacity_gb == 256
    assert configuration.configured_ram_gb == 256
    assert configuration.selected_storage.capacity_gb == 2000
    assert configuration.configured_storage_gb == 2000
    assert configuration.selected_cpu is None


def test_base_inclusion_does_not_make_selected_ram_or_storage_free() -> None:
    product = _product().model_copy(
        update={"base_price_includes": {"chassis", "cpu", "ram", "storage"}}
    )
    configuration = ProductConfigurationBuilder(
        [_gpu()], [_ram(256)], [_storage(2000)]
    ).build([product], _sizing(storage=1500), _requirement(storage=1500))[0]

    assert configuration.price_breakdown.ram_vnd == _ram(256).price_vnd
    assert configuration.price_breakdown.storage_vnd == _storage(2000).price_vnd


def test_missing_ram_option_is_unknown_when_platform_can_support_requirement() -> None:
    configuration = ProductConfigurationBuilder([_gpu()]).build(
        [_product()], _sizing(), _requirement()
    )[0]

    result = RuleBasedConfigurationValidator().validate(
        _requirement(), _sizing(), configuration
    )

    assert result.status == ValidationStatus.UNKNOWN
    assert "ram_option" in result.unknown_fields


def test_platform_ram_limit_below_requirement_is_definite_failure() -> None:
    configuration = ProductConfigurationBuilder([_gpu()], [_ram(256)]).build(
        [_product(max_ram_gb=128)], _sizing(), _requirement()
    )[0]

    result = RuleBasedConfigurationValidator().validate(
        _requirement(), _sizing(), configuration
    )

    assert result.status == ValidationStatus.FAIL
    assert any(failure.field == "max_ram_gb" for failure in result.failures)


def test_optional_storage_neither_selects_option_nor_creates_unknown() -> None:
    configuration = ProductConfigurationBuilder(
        [_gpu()], [_ram(256)], [_storage(1000)]
    ).build([_product()], _sizing(), _requirement())[0]

    result = RuleBasedConfigurationValidator().validate(
        _requirement(), _sizing(), configuration
    )

    assert configuration.selected_storage is None
    assert configuration.configured_storage_gb is None
    assert configuration.price_status.value == "partial"
    assert "storage" in configuration.missing_price_components
    assert not {"storage_option", "configured_storage_gb", "max_storage_gb"} & set(
        result.unknown_fields
    )


def test_customer_storage_requirement_is_enforced_when_sizing_has_none() -> None:
    configuration = ProductConfigurationBuilder(
        [_gpu()], [_ram(256)], [_storage(1000)]
    ).build([_product()], _sizing(), _requirement(storage=2000))[0]
    configuration.selected_storage = _storage(1000)
    configuration.configured_storage_gb = 1000

    result = RuleBasedConfigurationValidator().validate(
        _requirement(storage=2000), _sizing(), configuration
    )

    assert result.status == ValidationStatus.FAIL
    assert any(failure.field == "configured_storage_gb" for failure in result.failures)


def _proposal_fixture():
    product = _product()
    gpu = _gpu()
    configuration = ProductConfiguration(
        configuration_id="cfg-a",
        product=product,
        selected_gpu=gpu,
        gpu_count=2,
        selected_ram=_ram(256),
    )
    sizing = _sizing()
    requirement = _requirement()
    comparison = RuleBasedComparisonService().compare_configurations([configuration])
    hits = FakeDocumentSearch(option_documents(product, gpu, 256)).search(
        __import__("shared.contracts", fromlist=["DocumentSearchRequest"]).DocumentSearchRequest(
            query="max_gpu_slots max_ram_gb memory_gb capacity_gb", product_id="p-1"
        )
    ).hits
    proposal = RuleBasedProposalService().create(
        requirement, sizing, [configuration], comparison, hits
    )
    return proposal


def test_derived_vram_and_ram_evidence_recomputes_from_verified_direct_facts() -> None:
    proposal = _proposal_fixture()
    evidence = {item.claim: item for item in proposal.evidence}

    assert evidence["cfg-a.total_vram_gb"].kind == EvidenceKind.DERIVED
    assert evidence["cfg-a.total_vram_gb"].value == 96
    assert evidence["cfg-a.total_vram_gb"].source_url is None
    assert evidence["cfg-a.total_vram_gb"].verified is False
    assert RuleBasedProposalVerifier().verify(proposal).valid is True


def test_validator_rejects_incompatible_gpu_and_storage_options() -> None:
    product = _product()
    wrong_gpu = _gpu().model_copy(update={"supported_product_ids": ["other"]})
    wrong_storage = _storage(2000).model_copy(update={"supported_product_ids": ["other"]})
    configuration = ProductConfiguration(
        configuration_id="incompatible",
        product=product,
        selected_gpu=wrong_gpu,
        gpu_count=2,
        selected_ram=_ram(256),
        selected_storage=wrong_storage,
    )

    result = RuleBasedConfigurationValidator().validate(
        _requirement(storage=1500), _sizing(), configuration
    )

    assert result.status == ValidationStatus.FAIL
    assert {failure.field for failure in result.failures} >= {
        "selected_gpu",
        "storage_option",
    }


def test_proposal_verifier_rejects_incomplete_price_when_budget_exists() -> None:
    proposal = _proposal_fixture()
    proposal.customer_requirement = proposal.customer_requirement.model_copy(
        update={"budget_vnd": 500_000_000}
    )

    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("incomplete price" in error for error in result.errors)


def test_budget_verifier_rejects_complete_claim_without_breakdown() -> None:
    proposal = _proposal_fixture()
    forged = proposal.selected_configurations[0].model_copy(
        update={"price_status": "complete", "estimated_price_vnd": 1}
    )
    proposal.selected_configurations[0] = forged
    proposal.options[0].configuration = forged
    proposal.options[0].estimated_price_vnd = 1
    proposal.customer_requirement = proposal.customer_requirement.model_copy(
        update={"budget_vnd": 500_000_000}
    )

    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("incomplete price" in error for error in result.errors)


def test_proposal_verifier_rejects_inconsistent_pricing_without_budget() -> None:
    proposal = _proposal_fixture()
    forged = proposal.selected_configurations[0].model_copy(
        update={"priced_components": ["gpu"]}
    )
    proposal.selected_configurations[0] = forged
    proposal.options[0].configuration = forged

    result = RuleBasedProposalVerifier().verify(proposal)
    assert result.valid is False
    assert any("incomplete price" in error for error in result.errors)


def test_verifier_rejects_wrong_derived_total() -> None:
    proposal = _proposal_fixture()
    item = next(e for e in proposal.evidence if e.claim == "cfg-a.total_vram_gb")
    item.value = 80

    assert RuleBasedProposalVerifier().verify(proposal).valid is False


def test_verifier_rejects_wrong_product_unverified_fact_and_ram_mismatch() -> None:
    for mutation in ("product", "verified", "ram"):
        proposal = _proposal_fixture()
        direct = next(
            e for e in proposal.evidence if e.claim == "gpu-48.memory_gb"
        )
        if mutation == "product":
            direct.product_id = "wrong-product"
        elif mutation == "verified":
            direct.verified = False
        else:
            ram = next(e for e in proposal.evidence if e.claim == "ram-256.capacity_gb")
            ram.value = 128

        assert RuleBasedProposalVerifier().verify(proposal).valid is False


def test_verifier_rejects_mutated_option_with_same_configuration_id() -> None:
    proposal = _proposal_fixture()
    option = proposal.options[0]
    option.configuration = option.configuration.model_copy(
        update={"configured_ram_gb": 128}
    )

    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("does not match selected configuration" in error for error in result.errors)


def test_sizing_defaults_are_explicit_but_not_claimed_when_supplied() -> None:
    service = DeterministicSizingService()
    defaulted = service.estimate(SizingRequest(model_parameters_b=32, usage=UsageType.INFERENCE))
    supplied = service.estimate(
        SizingRequest(
            model_parameters_b=32,
            usage=UsageType.INFERENCE,
            context_length=8192,
            concurrent_users=5,
        )
    )
    missing_method = service.estimate(
        SizingRequest(model_parameters_b=32, usage=UsageType.FINE_TUNE)
    )

    assert any("4096" in assumption for assumption in defaulted.assumptions)
    assert any("1 user" in assumption for assumption in defaulted.assumptions)
    assert not any("4096" in assumption for assumption in supplied.assumptions)
    assert not any("1 user" in assumption for assumption in supplied.assumptions)
    assert any("training method" in warning for warning in missing_method.warnings)
