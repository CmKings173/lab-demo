from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from infra.postgres.seed import SeedProduct, load_seed, upsert_products
from lab2_rag_agent.catalog.repository import InMemoryProductRepository, PostgresProductRepository
from shared.contracts import Product, ProductFilter, ProductSearchRequest, ProductType
from shared.tool_contracts import TOOL_DEFINITIONS_BY_NAME


def test_unknown_facts_remain_candidates_in_memory() -> None:
    unknown = Product(id="u", sku="U", name="Unknown", manufacturer="Demo",
                      product_type=ProductType.AI_WORKSTATION)
    known = unknown.model_copy(update={"id": "k", "sku": "K", "max_ram_gb": 256,
                                      "max_gpu_slots": 2, "base_price_vnd": 500})
    repository = InMemoryProductRepository([unknown, known])
    result = repository.search(ProductSearchRequest(filters=ProductFilter(
        min_ram_gb=512, min_gpu_count=4, max_base_price_vnd=300,
    )))
    assert [product.id for product in result.products] == ["u"]


def test_in_memory_text_search_uses_postgres_lowercase_semantics() -> None:
    product = Product(
        id="unicode",
        name="Stra\u00dfe Server",
        product_type=ProductType.AI_SERVER,
    )
    result = InMemoryProductRepository([product]).search(
        ProductSearchRequest(query="STRASSE")
    )
    assert result.products == []


def test_postgres_repository_is_implemented() -> None:
    assert callable(PostgresProductRepository.get)
    assert callable(PostgresProductRepository.search)
    assert "NotImplementedError" not in PostgresProductRepository.get.__code__.co_names
    assert "NotImplementedError" not in PostgresProductRepository.search.__code__.co_names


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.statements: list[tuple[str, object]] = []
        self.selected: list[dict] = []
        self.count = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.statements.append((sql, params))
        self.count = "COUNT(*)" in sql
        self.selected = self.rows

    def fetchone(self):
        if self.count:
            return {"total": len(self.selected)}
        return self.selected[0] if self.selected else None

    def fetchall(self):
        return self.selected


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


def test_postgres_query_uses_parameters_and_unknown_disjunction(monkeypatch) -> None:
    row = {"id": "u", "sku": None, "name": "Unknown", "manufacturer": None,
           "product_type": "ai_workstation", "max_ram_gb": None, "max_gpu_slots": None,
           "base_price_vnd": None, "cpu_options": [], "base_price_includes": [],
           "source_urls": [], "specs": {}, "source_url": "https://example.invalid/u"}
    cursor = FakeCursor([row])
    monkeypatch.setattr(PostgresProductRepository, "_connect",
                        staticmethod(lambda _dsn: FakeConnection(cursor)))
    repo = PostgresProductRepository("unused")
    request = ProductSearchRequest(query="unk", filters=ProductFilter(
        min_ram_gb=512, min_gpu_count=4, max_base_price_vnd=300,
        min_total_gpu_vram_gb=96, min_installed_ram_gb=128,
        product_type=ProductType.AI_WORKSTATION, gpu_vendor="NVIDIA",
        availability="unknown",
    ), limit=5)
    result = repo.search(request)
    assert [p.id for p in result.products] == ["u"]
    assert result.products[0].sku is None
    assert result.total == 1
    sql, params = cursor.statements[1]
    for column in ("max_ram_gb", "max_gpu_slots", "base_price_vnd",
                   "total_gpu_vram_gb", "installed_ram_gb"):
        assert f"{column} IS NULL OR" in sql
    assert "ORDER BY catalog_order ASC LIMIT %s" in sql
    assert "512" not in sql and "NVIDIA" not in sql
    assert params[-1] == 5
    assert repo.get("u").id == "u"
    assert cursor.statements[-1] == ("SELECT * FROM products WHERE id = %s", ("u",))


def test_postgres_query_text_is_parameterized_and_case_insensitive() -> None:
    query = "RTX'; DROP TABLE products; --"
    where, params = PostgresProductRepository._where(
        ProductSearchRequest(query=query)
    )

    assert "position(%s in lower(name))" in where
    assert "position(%s in lower(coalesce(sku, '')))" in where
    assert "position(%s in lower(coalesce(manufacturer, '')))" in where
    assert query not in where
    assert params == [query.lower()] * 3


def test_seed_validation_rejects_invalid_values() -> None:
    basic = {"id": "p", "name": "Product", "product_type": "ai_workstation",
             "source_url": "https://example.invalid/product"}
    assert SeedProduct.model_validate(basic).source_urls == [basic["source_url"]]
    for update in ({"gpu_count": 0}, {"installed_ram_gb": 512, "max_ram_gb": 256},
                   {"gpu_count": 2, "gpu_vram_per_gpu_gb": 96,
                    "total_gpu_vram_gb": 96}, {"source_url": "not-a-url"},
                   {"availability": "fabricated"}):
        with pytest.raises(ValueError):
            SeedProduct.model_validate({**basic, **update})


def test_curated_seed_is_parseable_and_sourced() -> None:
    rows = load_seed()
    assert len(rows) == 10
    assert len({row.id for row in rows}) == len(rows)
    assert all(row.source_url.startswith("https://cnttshop.vn/") for row in rows)
    assert all(row.base_price_vnd is None for row in rows)
    assert all(row.source_retrieved_at is not None for row in rows)
    assert all(row.source_url in row.source_urls for row in rows)
    assert sum(row.product_type == ProductType.AI_WORKSTATION for row in rows) == 3
    assert sum(row.product_type == ProductType.AI_PC for row in rows) == 7


def test_listed_configuration_price_is_not_base_chassis_price() -> None:
    rows = {row.id: row for row in load_seed()}
    assert rows["cntt-ws-rtx5000-ada"].listed_price_vnd == 200_000_000
    assert rows["cntt-ws-rtxpro6000-maxq"].listed_price_vnd == 800_000_000
    assert rows["cntt-ws-rtx5000-ada"].base_price_vnd is None
    assert rows["cntt-ws-rtxpro6000-maxq"].base_price_vnd is None


def test_listed_price_filter_keeps_unknown_candidates_but_excludes_known_over_budget() -> None:
    products = [
        Product(id="under", name="Under", product_type=ProductType.AI_WORKSTATION,
                listed_price_vnd=200_000_000),
        Product(id="over", name="Over", product_type=ProductType.AI_WORKSTATION,
                listed_price_vnd=800_000_000),
        Product(id="unknown", name="Unknown", product_type=ProductType.AI_WORKSTATION),
    ]
    request = ProductSearchRequest(filters=ProductFilter(max_listed_price_vnd=300_000_000))
    result = InMemoryProductRepository(products).search(request)
    assert [product.id for product in result.products] == ["under", "unknown"]
    where, params = PostgresProductRepository._where(request)
    assert "listed_price_vnd IS NULL OR listed_price_vnd <= %s" in where
    assert params == [300_000_000]


def test_runtime_tool_schema_distinguishes_listed_and_base_price() -> None:
    definition = TOOL_DEFINITIONS_BY_NAME["search_products"]
    fields = definition.parameters["$defs"]["ProductFilter"]["properties"]
    assert "giá niêm yết" in fields["max_listed_price_vnd"]["description"]
    assert "giá máy cơ bản" in fields["max_base_price_vnd"]["description"]
    assert "chưa biết" in definition.description


def test_base_price_includes_default_matches_domain_and_sql() -> None:
    basic = {"id": "p", "name": "Product", "product_type": "ai_workstation",
             "source_url": "https://example.invalid/product"}
    assert Product.model_validate(basic).base_price_includes == {"chassis"}
    assert SeedProduct.model_validate(basic).base_price_includes == {"chassis"}
    migration = (Path(__file__).resolve().parents[2] /
                 "infra/postgres/migrations/001_create_products.sql").read_text()
    assert "base_price_includes JSONB NOT NULL DEFAULT '[\"chassis\"]'::jsonb" in migration
    assert "idx_products_max_gpu_slots ON products(max_gpu_slots)" in migration
    upgrade = (Path(__file__).resolve().parents[2] /
               "infra/postgres/migrations/002_listed_price_and_base_defaults.sql").read_text()
    assert "ALTER COLUMN base_price_includes SET DEFAULT '[\"chassis\"]'::jsonb" in upgrade


@pytest.mark.parametrize(
    ("filters", "expected_sql", "expected_value"),
    [
        (ProductFilter(min_ram_gb=512), "max_ram_gb IS NULL OR max_ram_gb >= %s", 512),
        (ProductFilter(min_gpu_count=4), "max_gpu_slots IS NULL OR max_gpu_slots >= %s", 4),
        (ProductFilter(max_base_price_vnd=300),
         "base_price_vnd IS NULL OR base_price_vnd <= %s", 300),
        (ProductFilter(max_listed_price_vnd=300),
         "listed_price_vnd IS NULL OR listed_price_vnd <= %s", 300),
        (ProductFilter(min_total_gpu_vram_gb=96),
         "total_gpu_vram_gb IS NULL OR total_gpu_vram_gb >= %s", 96),
        (ProductFilter(min_installed_ram_gb=128),
         "installed_ram_gb IS NULL OR installed_ram_gb >= %s", 128),
        (ProductFilter(gpu_vendor="NVIDIA"), "gpu_vendor = %s", "NVIDIA"),
        (ProductFilter(availability="in_stock"), "availability = %s", "in_stock"),
    ],
)
def test_postgres_filters_are_parameterized(filters, expected_sql, expected_value) -> None:
    where, params = PostgresProductRepository._where(ProductSearchRequest(filters=filters))
    assert expected_sql in where
    assert params == [expected_value]


def test_no_filter_and_missing_get(monkeypatch) -> None:
    cursor = FakeCursor([])
    monkeypatch.setattr(PostgresProductRepository, "_connect",
                        staticmethod(lambda _dsn: FakeConnection(cursor)))
    repo = PostgresProductRepository("unused")
    result = repo.search(ProductSearchRequest())
    assert result.total == 0 and result.products == []
    assert cursor.statements[0] == ("SELECT COUNT(*) AS total FROM products", [])
    assert repo.get("missing") is None


def test_database_row_maps_jsonb_and_nullable_fields() -> None:
    product = PostgresProductRepository._product({
        "id": "p", "sku": None, "name": "Product", "manufacturer": None,
        "product_type": "ai_workstation", "cpu_options": '["CPU A"]',
        "base_price_includes": '["cpu"]',
        "source_urls": '["https://example.invalid/p"]',
        "specs": '{"network":"10GbE"}', "max_ram_gb": None,
        "listed_price_vnd": 200_000_000,
        "source_url": "https://example.invalid/p", "catalog_order": 2,
    })
    assert product.cpu_options == ["CPU A"]
    assert product.base_price_includes == {"cpu"}
    assert product.specs == {"network": "10GbE"}
    assert product.max_ram_gb is None
    assert product.listed_price_vnd == 200_000_000
    assert product.sku is None


def test_seed_upsert_is_rerunnable_without_delete(monkeypatch) -> None:
    fake_json = ModuleType("psycopg.types.json")
    fake_json.Jsonb = lambda value: value
    monkeypatch.setitem(sys.modules, "psycopg", ModuleType("psycopg"))
    monkeypatch.setitem(sys.modules, "psycopg.types", ModuleType("psycopg.types"))
    monkeypatch.setitem(sys.modules, "psycopg.types.json", fake_json)
    cursor = FakeCursor([])
    connection = FakeConnection(cursor)
    products = load_seed()[:2]
    assert upsert_products(connection, products) == 2
    assert upsert_products(connection, products) == 2
    assert len(cursor.statements) == 4
    assert all("ON CONFLICT (id) DO UPDATE" in sql for sql, _ in cursor.statements)
    assert all("DELETE" not in sql for sql, _ in cursor.statements)
