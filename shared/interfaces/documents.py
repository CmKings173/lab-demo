from typing import Protocol

from shared.contracts import DocumentSearchRequest, DocumentSearchResult


class DocumentSearch(Protocol):
    def search(self, request: DocumentSearchRequest) -> DocumentSearchResult: ...
