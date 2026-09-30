"""Lab 2's catalog-owned mapping from products to provider knowledge records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Protocol
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


NonBlankText = Annotated[str, AfterValidator(_require_non_blank)]
ProductId = Annotated[
    str,
    StringConstraints(max_length=64),
    AfterValidator(_require_non_blank),
]
ProviderParseStatus = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    AfterValidator(_require_non_blank),
]


def _validate_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or any(character.isspace() for character in value)
    ):
        raise ValueError("source_url must be an absolute HTTP(S) URL")
    return value


class ProductDocumentUpsert(BaseModel):
    """Input for recording a provider document identity; never stores its contents."""

    model_config = ConfigDict(extra="forbid")

    product_id: ProductId
    knowledge_base_id: NonBlankText
    knowledge_id: NonBlankText
    filename: NonBlankText
    # Populate only when the catalog/source system has verified this provenance URL.
    source_url: str | None = None
    content_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Lowercase SHA-256 digest of the source document bytes.",
    )
    # Kept provider-neutral as raw status text until a provider adapter is introduced.
    provider_parse_status: ProviderParseStatus = "unknown"

    @field_validator("source_url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        return _validate_source_url(value)


class ProductDocumentMapping(ProductDocumentUpsert):
    """Persisted product-to-provider document mapping."""

    id: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime


class ProductDocumentRepository(Protocol):
    def list_by_product_id(self, product_id: str) -> Sequence[ProductDocumentMapping]: ...

    def list_by_knowledge_base_id(
        self, knowledge_base_id: str
    ) -> Sequence[ProductDocumentMapping]: ...

    def get_by_knowledge_id(
        self, knowledge_base_id: str, knowledge_id: str
    ) -> ProductDocumentMapping | None: ...

    def find_by_content_sha256(
        self, product_id: str, knowledge_base_id: str, content_sha256: str
    ) -> ProductDocumentMapping | None: ...

    def upsert(self, mapping: ProductDocumentUpsert) -> ProductDocumentMapping: ...

    def update_parse_status(
        self,
        knowledge_base_id: str,
        knowledge_id: str,
        provider_parse_status: ProviderParseStatus,
    ) -> ProductDocumentMapping | None: ...


class ProductDocumentIdentityConflict(ValueError):
    """Raised when a provider record identity is already bound to another product."""
