from __future__ import annotations

import sys
from types import ModuleType

import pytest
from pydantic import ValidationError

from infra.postgres.seed import (
    DEMO_CONFIGURATION_OPTIONS,
    ConfigurationOptionSeed,
    load_configuration_option_seed,
    load_seed,
    upsert_configuration_options,
)


class SeedState:
    def __init__(self) -> None:
        self.options: dict[str, tuple[object, ...]] = {}
        self.links: set[tuple[str, str]] = set()


class SeedCursor:
    def __init__(self, state: SeedState) -> None:
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        if statement.startswith("INSERT INTO configuration_options"):
            self.state.options[params[0]] = params
        elif statement.startswith("DELETE FROM configuration_option_products"):
            option_id = params[0]
            retained_ids = set(params[1]) if len(params) > 1 else set()
            self.state.links = {
                link
                for link in self.state.links
                if link[0] != option_id or link[1] in retained_ids
            }
        elif statement.startswith(
            "INSERT INTO configuration_option_products"
        ):
            self.state.links.add((params[0], params[1]))


class SeedConnection:
    def __init__(self, state: SeedState) -> None:
        self.state = state

    def cursor(self) -> SeedCursor:
        return SeedCursor(self.state)


def option_seed(
    option_id: str, option_type: str, product_ids: list[str]
) -> ConfigurationOptionSeed:
    fields = (
        {"name": f"{option_id} GPU", "memory_gb": 96}
        if option_type == "gpu"
        else {"capacity_gb": 256}
    )
    return ConfigurationOptionSeed.model_validate(
        {
            "option_id": option_id,
            "option_type": option_type,
            "source_urls": [f"https://example.invalid/{option_id}"],
            "supported_product_ids": product_ids,
            **fields,
        }
    )


def test_curated_option_seed_reuses_existing_products_and_keeps_demo_provenance():
    products = load_seed()
    options = load_configuration_option_seed()

    product_ids = {product.id for product in products}
    assert len(products) == 10
    assert len(product_ids) == 10
    assert len(options) == 3
    assert {product_id for option in options for product_id in option.supported_product_ids} == {
        "cntt-ws-rtxpro6000-maxq"
    }
    assert all(option.option_id.startswith("demo-") for option in options)
    assert all(option.source_urls for option in options)
    assert all(
        product_id in product_ids
        for option in options
        for product_id in option.supported_product_ids
    )

    gpu, ram, storage = options
    assert (gpu.option_type, gpu.memory_gb, gpu.price_vnd) == ("gpu", 96, None)
    assert (ram.option_type, ram.capacity_gb, ram.price_vnd) == (
        "ram", 512, 160_000_000
    )
    assert (storage.option_type, storage.capacity_gb, storage.price_vnd) == (
        "storage", 2048, 20_000_000
    )
    assert all(
        "example.invalid" in url
        for option in (ram, storage)
        for url in option.source_urls
    )
    assert options == [
        ConfigurationOptionSeed.model_validate(item)
        for item in DEMO_CONFIGURATION_OPTIONS
    ]


@pytest.mark.parametrize(
    "updates",
    [
        {"option_type": "gpu", "name": None, "memory_gb": 96},
        {"option_type": "ram", "capacity_gb": None},
        {"option_type": "storage", "capacity_gb": 2048, "memory_gb": 1},
    ],
)
def test_configuration_option_seed_rejects_mismatched_typed_fields(updates):
    option = {
        "option_id": "demo-invalid",
        "source_urls": ["https://example.invalid/demo"],
        "supported_product_ids": ["cntt-ws-rtxpro6000-maxq"],
        "name": "GPU demo",
        "memory_gb": None,
        "capacity_gb": None,
        "storage_type": None,
        "price_vnd": None,
        **updates,
    }

    with pytest.raises(ValidationError):
        ConfigurationOptionSeed.model_validate(option)


def test_option_seed_reconciles_links_idempotently_without_touching_other_options(
    monkeypatch,
):
    psycopg = ModuleType("psycopg")
    psycopg.__path__ = []
    psycopg_types = ModuleType("psycopg.types")
    psycopg_types.__path__ = []
    psycopg_json = ModuleType("psycopg.types.json")
    psycopg_json.Jsonb = lambda value: value
    monkeypatch.setitem(sys.modules, "psycopg", psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.types", psycopg_types)
    monkeypatch.setitem(sys.modules, "psycopg.types.json", psycopg_json)

    state = SeedState()
    connection = SeedConnection(state)
    option_x = option_seed("option-x", "gpu", ["product-a"])
    unrelated_option = option_seed("option-y", "ram", ["product-a"])

    upsert_configuration_options(connection, [option_x, unrelated_option])
    upsert_configuration_options(connection, [option_x, unrelated_option])

    assert state.links == {("option-x", "product-a"), ("option-y", "product-a")}
    assert len(state.links) == 2
    assert len(state.options) == 2

    changed_option_x = option_seed("option-x", "gpu", ["product-b"])
    upsert_configuration_options(connection, [changed_option_x])
    upsert_configuration_options(connection, [changed_option_x])

    assert state.links == {("option-x", "product-b"), ("option-y", "product-a")}
    assert len(state.links) == 2
    assert len(state.options) == 2
