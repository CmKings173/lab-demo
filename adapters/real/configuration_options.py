from __future__ import annotations

from collections.abc import Sequence

from shared.contracts import GPUOption, RAMOption, StorageOption


class PostgresConfigurationOptionRepository:
    """Reads typed Lab 3 options and explicit product links from PostgreSQL."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @staticmethod
    def _connect(dsn: str):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(dsn, row_factory=dict_row)

    def _list_rows(self, option_type: str, product_ids: Sequence[str]) -> list[dict]:
        scoped_ids = sorted(set(product_ids))
        if not scoped_ids:
            return []
        statement = (
            "SELECT config_option.option_id, config_option.name, config_option.memory_gb, "
            "config_option.capacity_gb, config_option.storage_type, config_option.price_vnd, "
            "config_option.source_urls, "
            'array_agg(all_link.product_id ORDER BY all_link.product_id COLLATE "C") '
            "AS supported_product_ids "
            "FROM configuration_options AS config_option "
            "JOIN configuration_option_products AS all_link "
            "ON all_link.option_id = config_option.option_id "
            "WHERE config_option.option_type = %s "
            "AND EXISTS (SELECT 1 FROM configuration_option_products AS eligible_link "
            "WHERE eligible_link.option_id = config_option.option_id "
            "AND eligible_link.product_id = ANY(%s)) "
            "GROUP BY config_option.option_id "
            'ORDER BY config_option.option_id COLLATE "C" ASC'
        )
        with self._connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(statement, (option_type, scoped_ids))
            return cursor.fetchall()

    def list_gpu_options(self, product_ids: Sequence[str]) -> list[GPUOption]:
        return [
            GPUOption(
                gpu_id=row["option_id"],
                name=row["name"],
                memory_gb=row["memory_gb"],
                supported_product_ids=row["supported_product_ids"],
                price_vnd=row["price_vnd"],
                source_urls=row["source_urls"],
            )
            for row in self._list_rows("gpu", product_ids)
        ]

    def list_ram_options(self, product_ids: Sequence[str]) -> list[RAMOption]:
        return [
            RAMOption(
                option_id=row["option_id"],
                capacity_gb=row["capacity_gb"],
                supported_product_ids=row["supported_product_ids"],
                price_vnd=row["price_vnd"],
                source_urls=row["source_urls"],
            )
            for row in self._list_rows("ram", product_ids)
        ]

    def list_storage_options(self, product_ids: Sequence[str]) -> list[StorageOption]:
        return [
            StorageOption(
                option_id=row["option_id"],
                capacity_gb=row["capacity_gb"],
                storage_type=row["storage_type"],
                supported_product_ids=row["supported_product_ids"],
                price_vnd=row["price_vnd"],
                source_urls=row["source_urls"],
            )
            for row in self._list_rows("storage", product_ids)
        ]
