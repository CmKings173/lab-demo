from __future__ import annotations

from collections.abc import Iterable

from shared.contracts import Product, ProductSearchRequest, ProductSearchResult


class InMemoryProductRepository:
    def __init__(self, products: Iterable[Product] = ()) -> None:
        self._products = {product.id: product for product in products}

    def search(self, request: ProductSearchRequest) -> ProductSearchResult:
        filters = request.filters
        products = list(self._products.values())
        if request.query:
            query = request.query.lower()
            products = [
                product
                for product in products
                if query in product.name.lower()
                or query in (product.sku or "").lower()
                or query in (product.manufacturer or "").lower()
            ]
        if filters.product_type:
            products = [p for p in products if p.product_type == filters.product_type]
        if filters.min_ram_gb is not None:
            products = [
                p for p in products if p.max_ram_gb is None or p.max_ram_gb >= filters.min_ram_gb
            ]
        if filters.min_gpu_count is not None:
            products = [
                p
                for p in products
                if p.max_gpu_slots is None or p.max_gpu_slots >= filters.min_gpu_count
            ]
        if filters.max_base_price_vnd is not None:
            products = [
                p
                for p in products
                if p.base_price_vnd is None or p.base_price_vnd <= filters.max_base_price_vnd
            ]
        if filters.max_listed_price_vnd is not None:
            products = [
                p for p in products
                if p.listed_price_vnd is None
                or p.listed_price_vnd <= filters.max_listed_price_vnd
            ]
        if filters.min_total_gpu_vram_gb is not None:
            products = [p for p in products if p.total_gpu_vram_gb is None
                        or p.total_gpu_vram_gb >= filters.min_total_gpu_vram_gb]
        if filters.min_installed_ram_gb is not None:
            products = [p for p in products if p.installed_ram_gb is None
                        or p.installed_ram_gb >= filters.min_installed_ram_gb]
        if filters.gpu_vendor is not None:
            products = [p for p in products if p.gpu_vendor == filters.gpu_vendor]
        if filters.availability is not None:
            products = [p for p in products if p.availability == filters.availability]
        return ProductSearchResult(products=products[: request.limit], total=len(products))

    def get(self, product_id: str) -> Product | None:
        return self._products.get(product_id)


class PostgresProductRepository:
    """PostgreSQL-backed catalog with the same UNKNOWN semantics as the in-memory adapter."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @staticmethod
    def _connect(dsn: str):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(dsn, row_factory=dict_row)

    @staticmethod
    def _product(row: dict) -> Product:
        fields = set(Product.model_fields)
        data = {key: value for key, value in row.items() if key in fields}
        for key in ("cpu_options", "base_price_includes", "source_urls", "specs"):
            if isinstance(data.get(key), str):
                import json

                data[key] = json.loads(data[key])
        return Product.model_validate(data)

    @staticmethod
    def _where(request: ProductSearchRequest) -> tuple[str, list]:
        clauses: list[str] = []
        params: list = []
        if request.query:
            clauses.append("(position(%s in lower(name)) > 0 OR "
                           "position(%s in lower(coalesce(sku, ''))) > 0 OR "
                           "position(%s in lower(coalesce(manufacturer, ''))) > 0)")
            params.extend([request.query.lower()] * 3)
        filters = request.filters
        if filters.product_type is not None:
            clauses.append("product_type = %s")
            params.append(filters.product_type.value)
        numeric = (
            ("max_ram_gb", filters.min_ram_gb, ">="),
            ("max_gpu_slots", filters.min_gpu_count, ">="),
            ("base_price_vnd", filters.max_base_price_vnd, "<="),
            ("listed_price_vnd", filters.max_listed_price_vnd, "<="),
            ("total_gpu_vram_gb", filters.min_total_gpu_vram_gb, ">="),
            ("installed_ram_gb", filters.min_installed_ram_gb, ">="),
        )
        for column, value, operator in numeric:
            if value is not None:
                clauses.append(f"({column} IS NULL OR {column} {operator} %s)")
                params.append(value)
        for column, value in (("gpu_vendor", filters.gpu_vendor),
                              ("availability", filters.availability)):
            if value is not None:
                clauses.append(f"{column} = %s")
                params.append(value)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def search(self, request: ProductSearchRequest) -> ProductSearchResult:
        where, params = self._where(request)
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM products" + where, params)
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT * FROM products" + where +
                           " ORDER BY catalog_order ASC LIMIT %s", [*params, request.limit])
            products = [self._product(row) for row in cursor.fetchall()]
        return ProductSearchResult(products=products, total=total)

    def get(self, product_id: str) -> Product | None:
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            row = cursor.fetchone()
        return self._product(row) if row is not None else None
