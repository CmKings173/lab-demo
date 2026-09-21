from collections.abc import Iterable

from shared.contracts import ProductConfiguration


class InMemoryConfigurationRepository:
    def __init__(self, configurations: Iterable[ProductConfiguration] = ()) -> None:
        self._items = {item.configuration_id: item.model_copy(deep=True) for item in configurations}

    def get(self, configuration_id: str) -> ProductConfiguration | None:
        item = self._items.get(configuration_id)
        return item.model_copy(deep=True) if item is not None else None

    def put(self, configuration: ProductConfiguration) -> None:
        self._items[configuration.configuration_id] = configuration.model_copy(deep=True)
