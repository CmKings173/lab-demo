"""Secret-safe environment settings for the separate Lab 3 process."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


class Lab3RuntimeSettings(BaseModel):
    """Validated Lab 3 settings with database/provider credentials redacted."""

    model_config = ConfigDict(frozen=True)

    postgres_dsn: SecretStr
    weknora_base_url: str
    weknora_api_key: SecretStr
    weknora_knowledge_base_id: str
    llm_base_url: str
    llm_model: str
    llm_api_key: SecretStr | None = None
    llm_json_schema_enabled: bool = False

    @field_validator("postgres_dsn", mode="before")
    @classmethod
    def require_postgres_dsn(cls, value: Any) -> Any:
        rendered = value.get_secret_value() if isinstance(value, SecretStr) else value
        if (
            not isinstance(rendered, str)
            or not rendered.strip()
            or not rendered.startswith(("postgres://", "postgresql://"))
        ):
            raise ValueError("must be a non-empty PostgreSQL DSN")
        return value

    @field_validator("weknora_base_url", mode="before")
    @classmethod
    def require_safe_weknora_base_url(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty HTTP(S) base URL")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("must be an HTTP(S) base URL without credentials or query data")
        return value.rstrip("/")

    @field_validator("weknora_api_key", mode="before")
    @classmethod
    def require_weknora_api_key(cls, value: Any) -> Any:
        rendered = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(rendered, str) or not rendered.strip():
            raise ValueError("must be a non-empty API key")
        return value

    @field_validator("weknora_knowledge_base_id", mode="before")
    @classmethod
    def require_knowledge_base_id(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty knowledge base ID")
        return value.strip()

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def require_safe_llm_base_url(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty HTTP(S) base URL")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("must be an HTTP(S) base URL without credentials or query data")
        return value.rstrip("/")

    @field_validator("llm_model", mode="before")
    @classmethod
    def require_llm_model(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty model identifier")
        return value.strip()

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def normalize_llm_api_key(cls, value: Any) -> Any:
        if value is None or isinstance(value, SecretStr):
            return value
        if not isinstance(value, str):
            raise ValueError("must be a string API key")
        return SecretStr(value) if value.strip() else None

    @classmethod
    def from_env(cls, *, load_dotenv: bool = True) -> Lab3RuntimeSettings:
        if load_dotenv:
            try:
                from dotenv import load_dotenv as dotenv_load
            except ImportError:
                pass
            else:
                project_root = Path(__file__).resolve().parents[2]
                dotenv_load(project_root / ".env", override=False)

        raw_dsn = os.environ.get("LAB3_POSTGRES_DSN")
        if raw_dsn is None or not raw_dsn.strip():
            raise ValueError("Missing required Lab 3 environment variable: LAB3_POSTGRES_DSN")

        environment_names = (
            "WEKNORA_BASE_URL",
            "WEKNORA_API_KEY",
            "WEKNORA_KNOWLEDGE_BASE_ID",
            "LAB3_LLM_BASE_URL",
            "LAB3_LLM_MODEL",
        )
        missing = [
            name
            for name in environment_names
            if not os.environ.get(name) or not os.environ[name].strip()
        ]
        if missing:
            raise ValueError(f"Missing required Lab 3 environment variable: {missing[0]}")
        try:
            return cls(
                postgres_dsn=raw_dsn,
                weknora_base_url=os.environ["WEKNORA_BASE_URL"],
                weknora_api_key=os.environ["WEKNORA_API_KEY"],
                weknora_knowledge_base_id=os.environ["WEKNORA_KNOWLEDGE_BASE_ID"],
                llm_base_url=os.environ["LAB3_LLM_BASE_URL"],
                llm_model=os.environ["LAB3_LLM_MODEL"],
                llm_api_key=os.environ.get("LAB3_LLM_API_KEY") or None,
                llm_json_schema_enabled=os.environ.get("LAB3_LLM_JSON_SCHEMA_ENABLED", "false"),
            )
        except Exception:
            # Pydantic errors include invalid environment values and credentials.
            raise ValueError("Invalid Lab 3 runtime environment configuration") from None
