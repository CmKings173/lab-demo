from typing import Protocol

from shared.contracts import ProductConfiguration


class ConfigurationRepository(Protocol):
    def get(self, configuration_id: str) -> ProductConfiguration | None: ...

    def put(self, configuration: ProductConfiguration) -> None: ...
