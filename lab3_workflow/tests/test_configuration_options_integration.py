"""Isolated real PostgreSQL coverage for Lab 3's shared structured options."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from adapters.real.configuration_options import PostgresConfigurationOptionRepository
from infra.postgres.seed import (
    load_configuration_option_seed,
    load_seed,
    upsert_configuration_options,
    upsert_products,
)
from lab2_rag_agent.catalog.repository import PostgresProductRepository
from lab3_workflow.configuration.repository_builder import (
    RepositoryBackedProductConfigurationBuilder,
)
from lab3_workflow.sizing.service import DeterministicSizingService
from shared.contracts import CustomerRequirement, PriceStatus, SizingRequest, UsageType


def test_real_postgres_options_seed_repository_and_configuration_builder(monkeypatch):
    dsn = os.environ.get("LAB2_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set LAB2_TEST_POSTGRES_DSN for isolated real PostgreSQL integration")
    psycopg = pytest.importorskip(
        "psycopg",
        reason="Install the optional postgres extra to run real PostgreSQL integration",
    )
    from psycopg import sql
    from psycopg.rows import dict_row

    schema = "lab3_options_test_" + uuid4().hex
    migration_dir = Path(__file__).resolve().parents[2] / "infra/postgres/migrations"
    products = load_seed()
    options = load_configuration_option_seed(products)
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
                assert upsert_products(connection, products) == len(products)
                assert upsert_products(connection, products) == len(products)
                assert upsert_configuration_options(connection, options) == len(options)
                assert upsert_configuration_options(connection, options) == len(options)
                assert connection.execute("SELECT COUNT(*) AS total FROM products").fetchone()[
                    "total"
                ] == len(products)
                assert connection.execute(
                    "SELECT COUNT(*) AS total FROM configuration_options"
                ).fetchone()["total"] == len(options)
                assert connection.execute(
                    "SELECT COUNT(*) AS total FROM configuration_option_products"
                ).fetchone()["total"] == len(options)
                connection.execute(
                    "INSERT INTO configuration_option_products (option_id, product_id) "
                    "VALUES (%s, %s) ON CONFLICT (option_id, product_id) DO NOTHING",
                    ("demo-gpu-rtxpro6000-96", "cntt-asus-proart-gr1x"),
                )

            monkeypatch.setattr(PostgresProductRepository, "_connect", staticmethod(connect))
            monkeypatch.setattr(
                PostgresConfigurationOptionRepository, "_connect", staticmethod(connect)
            )
            product_repository = PostgresProductRepository(dsn)
            option_repository = PostgresConfigurationOptionRepository(dsn)
            product_id = "cntt-ws-rtxpro6000-maxq"
            product = product_repository.get(product_id)

            gpu_options = option_repository.list_gpu_options([product_id])
            ram_options = option_repository.list_ram_options([product_id])
            storage_options = option_repository.list_storage_options([product_id])
            assert [option.gpu_id for option in gpu_options] == [
                "demo-gpu-rtxpro6000-96"
            ]
            assert gpu_options[0].supported_product_ids == sorted(
                [product_id, "cntt-asus-proart-gr1x"]
            )
            assert [option.option_id for option in ram_options] == ["demo-ram-512gb"]
            assert [option.option_id for option in storage_options] == [
                "demo-storage-nvme-2048gb"
            ]
            asus_gpu_options = option_repository.list_gpu_options(
                ["cntt-asus-proart-gr1x"]
            )
            assert [option.gpu_id for option in asus_gpu_options] == [
                "demo-gpu-rtxpro6000-96"
            ]
            assert asus_gpu_options[0].supported_product_ids == sorted(
                [product_id, "cntt-asus-proart-gr1x"]
            )
            assert option_repository.list_gpu_options(["unrelated-product"]) == []

            sizing_request = SizingRequest(
                model_parameters_b=14,
                usage=UsageType.INFERENCE,
            )
            sizing = DeterministicSizingService().estimate(sizing_request)
            requirement = CustomerRequirement(
                model_size_b=14,
                usage=UsageType.INFERENCE,
                storage_requirement_gb=1500,
            )
            configurations = RepositoryBackedProductConfigurationBuilder(
                option_repository
            ).build([product], sizing, requirement)

            assert len(configurations) == 1
            configuration = configurations[0]
            assert configuration.selected_gpu == gpu_options[0]
            assert configuration.selected_ram == ram_options[0]
            assert configuration.selected_storage == storage_options[0]
            assert configuration.price_status == PriceStatus.PARTIAL

            changed_gpu_seed = options[0].model_copy(
                update={"supported_product_ids": ["cntt-asus-proart-gr1x"]}
            )
            with connect(dsn) as connection:
                assert upsert_configuration_options(connection, [changed_gpu_seed]) == 1
                assert upsert_configuration_options(connection, [changed_gpu_seed]) == 1
                gpu_links = connection.execute(
                    "SELECT product_id FROM configuration_option_products "
                    "WHERE option_id = %s ORDER BY product_id COLLATE \"C\"",
                    ("demo-gpu-rtxpro6000-96",),
                ).fetchall()
                all_links = connection.execute(
                    "SELECT option_id, product_id FROM configuration_option_products "
                    "ORDER BY option_id COLLATE \"C\", product_id COLLATE \"C\""
                ).fetchall()
                assert [row["product_id"] for row in gpu_links] == [
                    "cntt-asus-proart-gr1x"
                ]
                assert {
                    (row["option_id"], row["product_id"]) for row in all_links
                } == {
                    ("demo-gpu-rtxpro6000-96", "cntt-asus-proart-gr1x"),
                    ("demo-ram-512gb", product_id),
                    ("demo-storage-nvme-2048gb", product_id),
                }
                assert connection.execute(
                    "SELECT COUNT(*) AS total FROM products"
                ).fetchone()["total"] == len(products)
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
