from typing import Protocol, Sequence

from shared.contracts import DocumentHit


class Reranker(Protocol):
    def rank(self, query: str, hits: Sequence[DocumentHit]) -> list[DocumentHit]: ...
