"""Single-file operator ingestion into the configured WeKnora knowledge base."""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urlsplit

import httpx

from lab2_rag_agent.catalog.documents import (
    ProductDocumentMapping,
    ProductDocumentRepository,
    ProductDocumentUpsert,
)
from shared.interfaces import ProductRepository

_IN_PROGRESS = {"pending", "processing", "finalizing"}
_TERMINAL_FAILURE = {"failed", "cancelled"}
_KNOWN_STATUSES = _IN_PROGRESS | _TERMINAL_FAILURE | {"completed"}
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class WeKnoraIngestionError(RuntimeError):
    """Safe, credential-free failure from the WeKnora ingestion boundary."""


class WeKnoraDocumentIngestion:
    """Upload one explicit local file and persist its WeKnora identity/status."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        knowledge_base_id: str,
        product_repository: ProductRepository,
        product_document_repository: ProductDocumentRepository,
        http_client: httpx.Client | None = None,
        timeout: float | httpx.Timeout = 10.0,
        poll_interval_seconds: float = 1.0,
        max_poll_attempts: int = 60,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = self._validated_base_url(base_url)
        self._api_key = self._required_text(api_key, "api_key")
        self._knowledge_base_id = self._safe_id(knowledge_base_id, "knowledge_base_id")
        if type(max_poll_attempts) is not int or max_poll_attempts < 1:
            raise ValueError("max_poll_attempts must be a positive integer")
        if (
            isinstance(poll_interval_seconds, bool)
            or not isinstance(poll_interval_seconds, (int, float))
            or not math.isfinite(poll_interval_seconds)
            or poll_interval_seconds < 0
        ):
            raise ValueError("poll_interval_seconds must be a finite non-negative number")

        self._products = product_repository
        self._documents = product_document_repository
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._max_poll_attempts = max_poll_attempts
        self._sleep = sleep
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    @staticmethod
    def _required_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _validated_base_url(cls, value: str) -> str:
        base_url = cls._required_text(value, "base_url")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be an HTTP(S) URL without credentials or query")
        return base_url.rstrip("/")

    @staticmethod
    def _safe_id(value: str, name: str) -> str:
        if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
            raise ValueError(f"{name} must be a safe provider identifier")
        return value

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> WeKnoraDocumentIngestion:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def ingest_file(
        self, product_id: str, file_path: str | os.PathLike[str]
    ) -> ProductDocumentMapping:
        if not isinstance(product_id, str) or not product_id.strip():
            raise WeKnoraIngestionError("product_id_required")
        product_id = product_id.strip()
        if self._products.get(product_id) is None:
            raise WeKnoraIngestionError("unknown_product")

        path = Path(file_path)
        if not path.is_file():
            raise WeKnoraIngestionError("file_must_be_a_regular_file")

        try:
            with path.open("rb") as file_handle:
                digest = self._sha256(file_handle)
                existing = self._documents.find_by_content_sha256(
                    product_id, self._knowledge_base_id, digest
                )
                if existing is not None:
                    if (
                        existing.product_id != product_id
                        or existing.knowledge_base_id != self._knowledge_base_id
                        or existing.content_sha256 != digest
                    ):
                        raise WeKnoraIngestionError("existing checksum mapping is inconsistent")
                    return self._finish_existing(existing)

                knowledge_id, initial_status, is_duplicate = self._upload(
                    file_handle, path.name
                )
        except OSError:
            raise WeKnoraIngestionError("local_file_unavailable") from None

        if is_duplicate:
            prior = self._documents.get_by_knowledge_id(
                self._knowledge_base_id, knowledge_id
            )
            if prior is not None and (
                prior.product_id != product_id
                or (prior.content_sha256 not in {None, digest})
            ):
                raise WeKnoraIngestionError("duplicate_identity_conflicts_with_mapping")

        mapping = self._documents.upsert(
            ProductDocumentUpsert(
                product_id=product_id,
                knowledge_base_id=self._knowledge_base_id,
                knowledge_id=knowledge_id,
                filename=path.name,
                content_sha256=digest,
                provider_parse_status=initial_status,
            )
        )
        return self._poll_until_ready(mapping)

    @staticmethod
    def _sha256(file_handle: BinaryIO) -> str:
        digest = hashlib.sha256()
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
        file_handle.seek(0)
        return digest.hexdigest()

    def _upload(
        self, file_handle: BinaryIO, filename: str
    ) -> tuple[str, str, bool]:
        try:
            response = self._http.post(
                f"{self._base_url}/api/v1/knowledge-bases/"
                f"{quote(self._knowledge_base_id, safe='')}/knowledge/file",
                headers={"X-API-Key": self._api_key},
                files={"file": (filename, file_handle, "application/octet-stream")},
            )
        except (httpx.RequestError, httpx.InvalidURL):
            raise WeKnoraIngestionError("WeKnora upload request failed") from None

        if response.status_code == 409:
            body = self._json_object(response)
            data = body.get("data")
            if body.get("success") is not False or body.get("code") != "duplicate_file":
                raise WeKnoraIngestionError("WeKnora returned an unreconcilable conflict")
            knowledge_id, status = self._identity_and_status(data)
            return knowledge_id, status, True

        if not response.is_success:
            raise WeKnoraIngestionError(
                f"WeKnora upload failed with HTTP {response.status_code}"
            )
        body = self._json_object(response)
        if body.get("success") is not True:
            raise WeKnoraIngestionError("WeKnora upload response was unsuccessful")
        knowledge_id, status = self._identity_and_status(body.get("data"))
        return knowledge_id, status, False

    def _identity_and_status(self, data: object) -> tuple[str, str]:
        if not isinstance(data, dict):
            raise WeKnoraIngestionError("WeKnora response has no knowledge identity")
        knowledge_id = data.get("id")
        knowledge_base_id = data.get("knowledge_base_id")
        if (
            not isinstance(knowledge_id, str)
            or _SAFE_ID.fullmatch(knowledge_id) is None
            or self._api_key in knowledge_id
            or knowledge_base_id != self._knowledge_base_id
        ):
            raise WeKnoraIngestionError("WeKnora response has an invalid knowledge identity")
        status = data.get("parse_status")
        if not isinstance(status, str) or status not in _KNOWN_STATUSES:
            raise WeKnoraIngestionError("WeKnora returned an unknown parse status")
        return knowledge_id, status

    @staticmethod
    def _json_object(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            raise WeKnoraIngestionError("WeKnora response is not valid JSON") from None
        if not isinstance(body, dict):
            raise WeKnoraIngestionError("WeKnora response is malformed")
        return body

    def _finish_existing(self, mapping: ProductDocumentMapping) -> ProductDocumentMapping:
        if mapping.knowledge_base_id != self._knowledge_base_id:
            raise WeKnoraIngestionError("existing mapping is outside the configured knowledge base")
        if mapping.provider_parse_status == "completed":
            return mapping
        if mapping.provider_parse_status in _TERMINAL_FAILURE:
            raise WeKnoraIngestionError(
                f"WeKnora document is terminal: {mapping.provider_parse_status}"
            )
        return self._poll_until_ready(mapping)

    def _poll_until_ready(
        self, mapping: ProductDocumentMapping
    ) -> ProductDocumentMapping:
        if mapping.provider_parse_status == "completed":
            return mapping
        if mapping.provider_parse_status in _TERMINAL_FAILURE:
            raise WeKnoraIngestionError(
                f"WeKnora document is terminal: {mapping.provider_parse_status}"
            )

        for attempt in range(self._max_poll_attempts):
            if attempt and self._poll_interval_seconds:
                self._sleep(self._poll_interval_seconds)
            status = self._get_parse_status(mapping.knowledge_id)
            updated = self._documents.update_parse_status(
                self._knowledge_base_id, mapping.knowledge_id, status
            )
            if updated is None:
                raise WeKnoraIngestionError("product document mapping disappeared during polling")
            if status == "completed":
                return updated
            if status in _TERMINAL_FAILURE:
                raise WeKnoraIngestionError(f"WeKnora document is terminal: {status}")
        raise WeKnoraIngestionError("WeKnora parse polling reached its configured limit")

    def _get_parse_status(self, knowledge_id: str) -> str:
        try:
            response = self._http.get(
                f"{self._base_url}/api/v1/knowledge/{quote(knowledge_id, safe='')}",
                headers={"X-API-Key": self._api_key},
            )
        except (httpx.RequestError, httpx.InvalidURL):
            raise WeKnoraIngestionError("WeKnora status request failed") from None
        if not response.is_success:
            raise WeKnoraIngestionError(
                f"WeKnora status request failed with HTTP {response.status_code}"
            )
        body = self._json_object(response)
        data = body.get("data")
        if body.get("success") is not True or not isinstance(data, dict):
            raise WeKnoraIngestionError("WeKnora status response is malformed")
        if (
            data.get("id") != knowledge_id
            or data.get("knowledge_base_id") != self._knowledge_base_id
        ):
            raise WeKnoraIngestionError("WeKnora status identity does not match the uploaded file")
        status = data.get("parse_status")
        if not isinstance(status, str) or status not in _KNOWN_STATUSES:
            raise WeKnoraIngestionError("WeKnora returned an unknown parse status")
        return status
