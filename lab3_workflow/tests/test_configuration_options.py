from __future__ import annotations

from pathlib import Path

from adapters.real.configuration_options import PostgresConfigurationOptionRepository
from lab3_workflow.configuration.repository_builder import (
    RepositoryBackedProductConfigurationBuilder,
)
from lab3_workflow.sizing.service import DeterministicSizingService
from shared.contracts import (
    CustomerRequirement,
    GPUOption,
    Product,
    ProductType,
    RAMOption,
    SizingRequest,
    StorageOption,
    UsageType,
)


class FakeCursor:
    def __init__(self, rows_by_kind: dict[str, list[dict]]) -> None:
        self.rows_by_kind = rows_by_kind
        self.statements: list[tuple[str, object]] = []
        self.rows: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        self.statements.append((statement, params))
        self.rows = self.rows_by_kind.get(params[0], [])

    def fetchall(self) -> list[dict]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self) -> FakeCursor:
        return self._cursor


class CompatibilityCursor(FakeCursor):
    """Model option eligibility separately from the complete persisted link set."""

    links_by_option = {"option-x": {"product-a", "product-b"}}

    def __init__(self) -> None:
        super().__init__({})

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        super().execute(statement, params)
        option_type, requested_product_ids = params
        links = self.links_by_option["option-x"]
        if option_type != "gpu" or not links.intersection(requested_product_ids):
            self.rows = []
            return

        preserves_all_links = (
            "EXISTS (" in statement
            and "eligible_link" in statement
            and "array_agg(all_link.product_id" in statement
        )
        supported_ids = links if preserves_all_links else links.intersection(
            requested_product_ids
        )
        self.rows = [
            option_row(
                "option-x",
                name="GPU option",
                memory_gb=96,
                supported_product_ids=sorted(supported_ids),
            )
        ]


def option_row(option_id: str, **updates: object) -> dict:
    return {
        "option_id": option_id,
        "name": None,
        "memory_gb": None,
        "capacity_gb": None,
        "storage_type": None,
        "price_vnd": None,
        "source_urls": [f"https://example.invalid/{option_id}"],
        "supported_product_ids": ["product-a"],
        **updates,
    }


def test_postgres_repository_maps_typed_options_and_uses_product_parameters(monkeypatch):
    cursor = FakeCursor(
        {
            "gpu": [
                option_row(
                    "gpu-a",
                    name="GPU 96GB",
                    memory_gb=96,
                    price_vnd=12_000,
                )
            ],
            "ram": [option_row("ram-a", capacity_gb=256)],
            "storage": [
                option_row("storage-a", capacity_gb=2048, storage_type="NVMe")
            ],
        }
    )
    monkeypatch.setattr(
        PostgresConfigurationOptionRepository,
        "_connect",
        staticmethod(lambda _dsn: FakeConnection(cursor)),
    )
    repository = PostgresConfigurationOptionRepository("unused")

    gpu = repository.list_gpu_options(["product-a"])[0]
    ram = repository.list_ram_options(["product-a"])[0]
    storage = repository.list_storage_options(["product-a"])[0]

    assert gpu == GPUOption(
        gpu_id="gpu-a",
        name="GPU 96GB",
        memory_gb=96,
        supported_product_ids=["product-a"],
        price_vnd=12_000,
        source_urls=["https://example.invalid/gpu-a"],
    )
    assert ram == RAMOption(
        option_id="ram-a",
        capacity_gb=256,
        supported_product_ids=["product-a"],
        source_urls=["https://example.invalid/ram-a"],
    )
    assert storage == StorageOption(
        option_id="storage-a",
        capacity_gb=2048,
        storage_type="NVMe",
        supported_product_ids=["product-a"],
        source_urls=["https://example.invalid/storage-a"],
    )
    for statement, params in cursor.statements:
        assert "%s" in statement
        assert "product-a" not in statement
        assert params[1] == ["product-a"]
        assert 'ORDER BY config_option.option_id COLLATE "C" ASC' in statement


def test_postgres_repository_empty_scope_returns_no_options_without_query(monkeypatch):
    def unexpected_connect(_dsn):
        raise AssertionError("empty product scope should not query PostgreSQL")

    monkeypatch.setattr(
        PostgresConfigurationOptionRepository,
        "_connect",
        staticmethod(unexpected_connect),
    )
    repository = PostgresConfigurationOptionRepository("unused")

    assert repository.list_gpu_options([]) == []
    assert repository.list_ram_options([]) == []
    assert repository.list_storage_options([]) == []


def test_product_scope_selects_options_but_keeps_all_compatibility_links(monkeypatch):
    cursor = CompatibilityCursor()
    monkeypatch.setattr(
        PostgresConfigurationOptionRepository,
        "_connect",
        staticmethod(lambda _dsn: FakeConnection(cursor)),
    )
    repository = PostgresConfigurationOptionRepository("unused")

    options = repository.list_gpu_options(["product-a"])

    assert [option.supported_product_ids for option in options] == [
        ["product-a", "product-b"]
    ]
    assert repository.list_gpu_options(["unrelated-product"]) == []
    statement, params = cursor.statements[0]
    assert params == ("gpu", ["product-a"])
    assert "EXISTS (" in statement
    assert "eligible_link.product_id = ANY(%s)" in statement
    assert (
        'array_agg(all_link.product_id ORDER BY all_link.product_id COLLATE "C")'
        in statement
    )


def test_repository_backed_builder_loads_only_candidate_product_options():
    product = Product(
        id="product-a",
        name="Demo server",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=4,
        max_ram_gb=1024,
        max_storage_gb=8000,
        base_price_vnd=100_000,
    )
    gpu = GPUOption(
        gpu_id="gpu-a",
        name="GPU 96GB",
        memory_gb=96,
        supported_product_ids=[product.id],
        price_vnd=12_000,
    )
    ram = RAMOption(
        option_id="ram-a", capacity_gb=256, supported_product_ids=[product.id]
    )
    storage = StorageOption(
        option_id="storage-a", capacity_gb=2048, supported_product_ids=[product.id]
    )

    class Options:
        requested: list[list[str]] = []

        def list_gpu_options(self, product_ids):
            self.requested.append(list(product_ids))
            return [gpu]

        def list_ram_options(self, product_ids):
            self.requested.append(list(product_ids))
            return [ram]

        def list_storage_options(self, product_ids):
            self.requested.append(list(product_ids))
            return [storage]

    options = Options()
    builder = RepositoryBackedProductConfigurationBuilder(options)
    requirement = CustomerRequirement(
        model_size_b=14,
        usage=UsageType.INFERENCE,
        budget_vnd=500_000,
        storage_requirement_gb=1500,
    )
    sizing = DeterministicSizingService().estimate(
        SizingRequest(model_parameters_b=14, usage=UsageType.INFERENCE)
    )

    configurations = builder.build([product], sizing, requirement)

    assert len(configurations) == 1
    assert configurations[0].selected_gpu == gpu
    assert configurations[0].selected_ram == ram
    assert configurations[0].selected_storage == storage
    assert options.requested == [[product.id], [product.id], [product.id]]


def test_option_migration_is_additive_and_references_existing_products():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "infra/postgres/migrations/004_create_configuration_options.sql"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS configuration_options" in migration
    assert "CREATE TABLE IF NOT EXISTS configuration_option_products" in migration
    assert "REFERENCES products(id)" in migration
    assert "REFERENCES configuration_options(option_id)" in migration
    assert "PRIMARY KEY (option_id, product_id)" in migration
    assert "CREATE TABLE IF NOT EXISTS products" not in migration
    assert "CREATE TABLE IF NOT EXISTS lab3_products" not in migration
