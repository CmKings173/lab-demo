"""HTTP adapter for the pinned WeKnora knowledge-search API."""

from __future__ import annotations

import json
import math
from typing import Any

import httpx

from lab2_rag_agent.catalog.documents import (
    ProductDocumentMapping,
    ProductDocumentRepository,
)
from shared.contracts import DocumentChunk, DocumentHit, DocumentSearchRequest, DocumentSearchResult


class WeKnoraDocumentSearchError(RuntimeError):
    """A provider transport or response-contract failure."""


class WeKnoraDocumentSearch:
    """Search a configured WeKnora knowledge base through the Lab2 document contract."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        knowledge_base_id: str,
        product_document_repository: ProductDocumentRepository,
        http_client: httpx.Client | None = None,
        timeout: float | httpx.Timeout = 10.0,
    ) -> None:
        self._base_url = self._require_config("base_url", base_url).rstrip("/")
        self._api_key = self._require_config("api_key", api_key)
        self._knowledge_base_id = self._require_config(
            "knowledge_base_id", knowledge_base_id
        )
        self._documents = product_document_repository
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=timeout)

    @staticmethod
    def _require_config(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip() if name != "api_key" else value

    def close(self) -> None:
        """Close the internally-created HTTP client, if this adapter owns it."""
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> WeKnoraDocumentSearch:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def search(self, request: DocumentSearchRequest) -> DocumentSearchResult:
        mappings_by_id: dict[str, ProductDocumentMapping] = {}
        payload: dict[str, Any] = {
            "query": request.query,
            "knowledge_base_id": self._knowledge_base_id,
        }

        candidates = (
            self._documents.list_by_product_id(request.product_id)
            if request.product_id is not None
            else self._documents.list_by_knowledge_base_id(self._knowledge_base_id)
        )
        mappings_by_id = {
            mapping.knowledge_id: mapping
            for mapping in candidates
            if (request.product_id is None or mapping.product_id == request.product_id)
            and mapping.knowledge_base_id == self._knowledge_base_id
            and mapping.provider_parse_status == "completed"
        }
        if not mappings_by_id:
            return DocumentSearchResult(hits=[], total=0)
        payload["knowledge_ids"] = list(mappings_by_id)

        provider_data = self._request(payload)
        hits = [
            self._map_hit(
                item,
                index=index,
                mappings_by_id=mappings_by_id,
            )
            for index, item in enumerate(provider_data, start=1)
        ]
        return DocumentSearchResult(hits=hits[: request.top_k], total=len(provider_data))

    def _request(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = self._http_client.post(
                f"{self._base_url}/api/v1/knowledge-search",
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise WeKnoraDocumentSearchError(
                f"WeKnora returned HTTP {exc.response.status_code}"
            ) from None
        except (httpx.RequestError, httpx.InvalidURL) as exc:
            raise WeKnoraDocumentSearchError("WeKnora request failed") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise WeKnoraDocumentSearchError("WeKnora response is not valid JSON") from exc

        if not isinstance(body, dict):
            raise WeKnoraDocumentSearchError("WeKnora response root must be a JSON object")
        if body.get("success") is not True:
            raise WeKnoraDocumentSearchError("WeKnora response success must be true")
        if "data" not in body:
            raise WeKnoraDocumentSearchError("WeKnora response is missing data")
        data = body["data"]
        if not isinstance(data, list):
            raise WeKnoraDocumentSearchError("WeKnora response data must be a list")
        if not all(isinstance(item, dict) for item in data):
            raise WeKnoraDocumentSearchError("WeKnora response contains a malformed hit")
        return data

    def _map_hit(
        self,
        provider_hit: dict[str, Any],
        *,
        index: int,
        mappings_by_id: dict[str, ProductDocumentMapping],
    ) -> DocumentHit:
        chunk_id = self._required_text(provider_hit, "id", index)
        text = self._required_text(provider_hit, "content", index)
        knowledge_id = self._required_text(provider_hit, "knowledge_id", index)
        chunk_index = self._optional_nonnegative_int(provider_hit, "chunk_index", index)
        sequence = self._optional_nonnegative_int(provider_hit, "seq", index)
        score = self._optional_score(provider_hit, index)

        provider_metadata = provider_hit.get("metadata", {})
        if not isinstance(provider_metadata, dict):
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} metadata must be an object"
            )
        metadata: dict[str, str] = {}
        for key, value in provider_metadata.items():
            if not isinstance(key, str):
                continue
            rendered = self._metadata_value(value)
            if (
                self._api_key not in key
                and rendered is not None
                and self._api_key not in rendered
            ):
                metadata[key] = rendered

        title = self._optional_text(provider_hit, "knowledge_title", index)
        filename = self._optional_text(provider_hit, "knowledge_filename", index)
        self._add_safe_metadata(metadata, "provider", "weknora")
        self._add_safe_metadata(metadata, "knowledge_id", knowledge_id)
        if title is not None:
            self._add_safe_metadata(metadata, "knowledge_title", title)
        if filename is not None:
            self._add_safe_metadata(metadata, "knowledge_filename", filename)
        if chunk_index is not None:
            self._add_safe_metadata(metadata, "chunk_index", str(chunk_index))
        if sequence is not None:
            self._add_safe_metadata(metadata, "seq", str(sequence))
        if score is not None:
            self._add_safe_metadata(metadata, "provider_score", str(score))

        mapping = mappings_by_id.get(knowledge_id)
        if mapping is None:
            raise WeKnoraDocumentSearchError(
                f"WeKnora returned unmapped knowledge id for search (hit {index})"
            )

        chunk = DocumentChunk(
            id=chunk_id,
            text=text,
            product_id=mapping.product_id,
            source_url=mapping.source_url,
            page=None,
            metadata=metadata,
        )
        return DocumentHit(
            chunk=chunk,
            retrieval_score=None,
            rerank_score=None,
            rank=sequence + 1 if sequence is not None else index,
            retrieval_method="weknora",
        )

    @staticmethod
    def _required_text(hit: dict[str, Any], field: str, index: int) -> str:
        value = hit.get(field)
        if not isinstance(value, str) or not value.strip():
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} is missing valid {field}"
            )
        return value

    @staticmethod
    def _optional_text(hit: dict[str, Any], field: str, index: int) -> str | None:
        value = hit.get(field)
        if value is None:
            return None
        if not isinstance(value, str):
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} has invalid {field}"
            )
        return value or None

    @staticmethod
    def _optional_nonnegative_int(
        hit: dict[str, Any], field: str, index: int
    ) -> int | None:
        value = hit.get(field)
        if value is None:
            return None
        if type(value) is not int or value < 0:
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} has invalid {field}"
            )
        return value

    @staticmethod
    def _optional_score(hit: dict[str, Any], index: int) -> int | float | None:
        value = hit.get("score")
        if value is None:
            return None
        if isinstance(value, bool):
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} has invalid score"
            )
        if isinstance(value, int):
            return value
        if not isinstance(value, float) or not math.isfinite(value):
            raise WeKnoraDocumentSearchError(
                f"WeKnora hit {index} has invalid score"
            )
        return value

    @staticmethod
    def _metadata_value(value: Any) -> str | None:
        if value is None or isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float) and math.isfinite(value):
            return str(value)
        return None

    def _add_safe_metadata(
        self, metadata: dict[str, str], key: str, value: str
    ) -> None:
        if self._api_key not in value:
            metadata[key] = value
