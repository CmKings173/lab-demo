from typing import Protocol

from shared.contracts import SizingRequest, SizingResult


class SizingService(Protocol):
    def estimate(self, request: SizingRequest) -> SizingResult: ...
