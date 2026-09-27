"""Validate and upsert a curated Lab 2 product seed; never crawl or infer facts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.contracts import Product, ProductType

DEFAULT_SEED = (
    Path(__file__).resolve().parents[2] / "lab2_rag_agent/data/catalog/products.demo.json"
)


class SeedProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    sku: str | None = None
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    product_type: ProductType
    platform: str | None = None
    cpu_model: str | None = None
    cpu_options: list[str] = Field(default_factory=list)
    gpu_vendor: str | None = None
    gpu_model: str | None = None
    gpu_count: int | None = Field(default=None, gt=0)
    gpu_vram_per_gpu_gb: float | None = Field(default=None, gt=0)
    total_gpu_vram_gb: float | None = Field(default=None, gt=0)
    max_gpu_slots: int | None = Field(default=None, gt=0)
    installed_ram_gb: int | None = Field(default=None, gt=0)
    max_ram_gb: int | None = Field(default=None, gt=0)
    installed_storage_gb: int | None = Field(default=None, gt=0)
    max_storage_gb: int | None = Field(default=None, gt=0)
    storage_slots: int | None = Field(default=None, gt=0)
    power_w: int | None = Field(default=None, gt=0)
    form_factor: str | None = None
    base_price_vnd: int | None = Field(default=None, ge=0)
    listed_price_vnd: int | None = Field(default=None, ge=0)
    base_price_includes: set[str] = Field(default_factory=lambda: {"chassis"})
    availability: str = "unknown"
    source_url: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)
    source_retrieved_at: datetime | None = None
    specs: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_facts(self) -> "SeedProduct":
        if not self.id.strip() or not self.name.strip():
            raise ValueError("id and name must not be blank")
        if self.availability not in {
            "in_stock", "out_of_stock", "preorder", "contact", "unknown"
        }:
            raise ValueError("invalid availability")
        if not self.source_url.startswith(("https://", "http://")):
            raise ValueError("source_url must be an HTTP URL")
        if not self.source_urls:
            self.source_urls = [self.source_url]
        if any(not url.startswith(("https://", "http://")) for url in self.source_urls):
            raise ValueError("source_urls must contain HTTP URLs")
        if self.base_price_includes - {"chassis", "cpu", "ram", "storage"}:
            raise ValueError("base_price_includes contains unsupported components")
        if (self.installed_ram_gb is not None and self.max_ram_gb is not None
                and self.max_ram_gb < self.installed_ram_gb):
            raise ValueError("max_ram_gb is below installed_ram_gb")
        if (self.installed_storage_gb is not None and self.max_storage_gb is not None
                and self.max_storage_gb < self.installed_storage_gb):
            raise ValueError("max_storage_gb is below installed_storage_gb")
        if (self.gpu_count is not None and self.max_gpu_slots is not None
                and self.max_gpu_slots < self.gpu_count):
            raise ValueError("max_gpu_slots is below gpu_count")
        if (self.gpu_count is not None and self.gpu_vram_per_gpu_gb is not None
                and self.total_gpu_vram_gb is not None
                and abs(self.total_gpu_vram_gb - self.gpu_count * self.gpu_vram_per_gpu_gb)
                > 0.01):
            raise ValueError("total_gpu_vram_gb contradicts GPU count and per-GPU VRAM")
        return self


def load_seed(path: Path = DEFAULT_SEED) -> list[SeedProduct]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("seed must be a JSON array")
    products = [SeedProduct.model_validate(item) for item in raw]
    ids = [product.id for product in products]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate product id in seed")
    return products


def upsert_products(connection, products: list[SeedProduct]) -> int:
    from psycopg.types.json import Jsonb

    columns = [name for name in SeedProduct.model_fields if name != "source_retrieved_at"]
    columns.append("source_retrieved_at")
    update = ", ".join(f"{name} = EXCLUDED.{name}" for name in columns if name != "id")
    sql = (f"INSERT INTO products ({', '.join(columns)}) VALUES "
           f"({', '.join(['%s'] * len(columns))}) "
           f"ON CONFLICT (id) DO UPDATE SET {update}, updated_at = NOW()")
    with connection.cursor() as cursor:
        for product in products:
            values = product.model_dump(mode="python")
            # Validate compatibility with the public Product contract before writing.
            Product.model_validate({key: value for key, value in values.items()
                                    if key in Product.model_fields})
            for key in ("cpu_options", "base_price_includes", "source_urls", "specs"):
                values[key] = Jsonb(sorted(values[key]) if isinstance(values[key], set)
                                    else values[key])
            cursor.execute(sql, [values[name] for name in columns])
    return len(products)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    products = load_seed(args.seed)
    dsn = os.environ.get("LAB2_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("LAB2_POSTGRES_DSN is required")
    import psycopg

    with psycopg.connect(dsn) as connection:
        count = upsert_products(connection, products)
    print(f"Upserted {count} products")


if __name__ == "__main__":
    main()
