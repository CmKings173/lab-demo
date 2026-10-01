"""Environment-backed settings for the local Lab 2 runtime."""

from __future__ import annotations

import os
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, SecretStr, field_validator


class RuntimeSettings(BaseModel):
    """Validated runtime configuration; credential fields are redacted in repr."""

    model_config = ConfigDict(frozen=True)

    postgres_dsn: SecretStr
    weknora_base_url: AnyHttpUrl
    weknora_api_key: SecretStr
    weknora_knowledge_base_id: str

    @field_validator("postgres_dsn", "weknora_api_key", mode="before")
    @classmethod
    def require_nonblank_secret(cls, value: Any) -> Any:
        rendered = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(rendered, str) or not rendered.strip():
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("weknora_knowledge_base_id")
    @classmethod
    def require_knowledge_base_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @field_validator("weknora_base_url")
    @classmethod
    def reject_embedded_provider_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("must not embed credentials, query parameters, or fragments")
        return value

    @classmethod
    def from_env(cls, *, load_dotenv: bool = True) -> RuntimeSettings:
        if load_dotenv:
            try:
                from dotenv import load_dotenv as dotenv_load
            except ImportError:
                pass
            else:
                dotenv_load(override=False)

        names = (
            "LAB2_POSTGRES_DSN",
            "WEKNORA_BASE_URL",
            "WEKNORA_API_KEY",
            "WEKNORA_KNOWLEDGE_BASE_ID",
        )
        values = {name: os.environ.get(name) for name in names}
        missing = [name for name, value in values.items() if value is None or not value.strip()]
        if missing:
            raise ValueError("Missing required Lab 2 environment variables: " + ", ".join(missing))

        try:
            return cls(
                postgres_dsn=values["LAB2_POSTGRES_DSN"],
                weknora_base_url=values["WEKNORA_BASE_URL"],
                weknora_api_key=values["WEKNORA_API_KEY"],
                weknora_knowledge_base_id=values["WEKNORA_KNOWLEDGE_BASE_ID"],
            )
        except Exception:
            # Pydantic's default validation errors include invalid input values.
            raise ValueError("Invalid Lab 2 runtime environment configuration") from None
