"""Opt-in real PostgreSQL parity test; set LAB2_TEST_POSTGRES_DSN to run."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from infra.postgres.seed import SeedProduct, load_seed, upsert_products
from lab2_rag_agent.catalog.repository import InMemoryProductRepository, PostgresProductRepository
from shared.contracts import Product, ProductFilter, ProductSearchRequest, ProductType


def _parity_seed_rows() -> list[dict[str, object]]:
    return [
        {
            "id": "parity-unknown-server",
            "name": "Unknown Candidate Stra\u00dfe Server",
            "product_type": "ai_server",
            "availability": "unknown",
            "source_url": "https://example.invalid/parity-unknown-server",
        },
        {
            "id": "parity-alpha-workstation",
            "sku": "PARITY-ALPHA",
            "name": "Fixture Alpha Workstation",
            "manufacturer": "NVIDIA Systems",
            "product_type": "ai_workstation",
            "gpu_vendor": "NVIDIA",
            "gpu_model": "Fixture GPU Alpha",
            "gpu_count": 2,
            "gpu_vram_per_gpu_gb": 96,
            "total_gpu_vram_gb": 192,
            "max_gpu_slots": 4,
            "installed_ram_gb": 128,
            "max_ram_gb": 512,
            "installed_storage_gb": 2048,
            "base_price_vnd": 40_000_000,
            "listed_price_vnd": 250_000_000,
            "availability": "in_stock",
            "source_url": "https://example.invalid/parity-alpha-workstation",
        },
        {
            "id": "parity-beta-workstation",
            "sku": "PARITY-BETA",
            "name": "Fixture Beta Workstation",
            "manufacturer": "AMD Systems",
            "product_type": "ai_workstation",
            "gpu_vendor": "AMD",
            "gpu_model": "Fixture GPU Beta",
            "gpu_count": 1,
            "gpu_vram_per_gpu_gb": 48,
            "total_gpu_vram_gb": 48,
            "max_gpu_slots": 2,
            "installed_ram_gb": 64,
            "max_ram_gb": 256,
            "installed_storage_gb": 1024,
            "base_price_vnd": 60_000_000,
            "listed_price_vnd": 400_000_000,
            "availability": "out_of_stock",
            "source_url": "https://example.invalid/parity-beta-workstation",
        },
    ]


def test_real_postgres_migration_seed_twice_and_repository_parity(monkeypatch) -> None:
    dsn = os.environ.get("LAB2_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set LAB2_TEST_POSTGRES_DSN for isolated real PostgreSQL integration")
    psycopg = pytest.importorskip(
        "psycopg",
        reason="Install the optional postgres extra to run real PostgreSQL integration",
    )
    from psycopg import sql
    from psycopg.rows import dict_row

    schema = "lab2_test_" + uuid4().hex
    migration_dir = Path(__file__).resolve().parents[2] / "infra/postgres/migrations"
    seed = load_seed()
    assert len(seed) == 10
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            def connect(_dsn):
                connection = psycopg.connect(_dsn, row_factory=dict_row)
                connection.execute(
                    sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
                )
                return connection

            with connect(dsn) as connection:
                migrations = sorted(migration_dir.glob("*.sql"))
                for _ in range(2):
                    for migration in migrations:
                        connection.execute(migration.read_text(encoding="utf-8"))
                parity_seed = [
                    SeedProduct.model_validate(row) for row in _parity_seed_rows()
                ]
                all_seed = [*seed, *parity_seed]
                assert upsert_products(connection, all_seed) == len(all_seed)
                assert upsert_products(connection, all_seed) == len(all_seed)
                assert connection.execute(
                    "SELECT COUNT(*) FROM products"
                ).fetchone()["count"] == len(all_seed)

            monkeypatch.setattr(PostgresProductRepository, "_connect", staticmethod(connect))
            postgres = PostgresProductRepository(dsn)
            memory = InMemoryProductRepository(
                Product.model_validate(row.model_dump()) for row in all_seed
            )
            for request in (
                ProductSearchRequest(limit=100),
                ProductSearchRequest(query="alpha"),
                ProductSearchRequest(query="NVIDIA SYSTEMS"),
                ProductSearchRequest(query="parity-alpha"),
                ProductSearchRequest(query="STRASSE"),
                ProductSearchRequest(filters=ProductFilter(
                    product_type=ProductType.AI_SERVER,
                )),
                ProductSearchRequest(filters=ProductFilter(min_ram_gb=512)),
                ProductSearchRequest(filters=ProductFilter(min_ram_gb=513)),
                ProductSearchRequest(filters=ProductFilter(min_gpu_count=4)),
                ProductSearchRequest(filters=ProductFilter(max_base_price_vnd=50_000_000)),
                ProductSearchRequest(filters=ProductFilter(
                    max_listed_price_vnd=300_000_000,
                )),
                ProductSearchRequest(filters=ProductFilter(min_total_gpu_vram_gb=96)),
                ProductSearchRequest(filters=ProductFilter(min_installed_ram_gb=128)),
                ProductSearchRequest(filters=ProductFilter(gpu_vendor="NVIDIA")),
                ProductSearchRequest(filters=ProductFilter(availability="in_stock")),
                ProductSearchRequest(filters=ProductFilter(
                    product_type=ProductType.AI_WORKSTATION,
                    min_ram_gb=512,
                    max_listed_price_vnd=300_000_000,
                    gpu_vendor="NVIDIA",
                    availability="in_stock",
                )),
                ProductSearchRequest(query="workstation", limit=1),
            ):
                actual = postgres.search(request)
                expected = memory.search(request)
                assert [p.id for p in actual.products] == [p.id for p in expected.products]
                assert actual.total == expected.total
            assert postgres.get(all_seed[0].id).id == all_seed[0].id
            assert postgres.get("missing") is None
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
