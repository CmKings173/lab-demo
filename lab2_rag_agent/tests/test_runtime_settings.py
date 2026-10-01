from __future__ import annotations

import traceback

import pytest

from lab2_rag_agent.runtime.settings import RuntimeSettings


def test_runtime_settings_fail_fast_with_names_of_missing_environment_variables(
    monkeypatch,
) -> None:
    for key in (
        "LAB2_POSTGRES_DSN",
        "WEKNORA_BASE_URL",
        "WEKNORA_API_KEY",
        "WEKNORA_KNOWLEDGE_BASE_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError) as error:
        RuntimeSettings.from_env(load_dotenv=False)

    message = str(error.value)
    assert "LAB2_POSTGRES_DSN" in message
    assert "WEKNORA_API_KEY" in message
    assert "secret" not in message


def test_runtime_settings_keep_credentials_out_of_repr(monkeypatch) -> None:
    monkeypatch.setenv("LAB2_POSTGRES_DSN", "postgresql://demo:db-secret@localhost/lab2")
    monkeypatch.setenv("WEKNORA_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("WEKNORA_API_KEY", "weknora-secret")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "demo-kb")

    settings = RuntimeSettings.from_env(load_dotenv=False)
    rendered = repr(settings)

    assert "db-secret" not in rendered
    assert "weknora-secret" not in rendered
    assert settings.weknora_api_key.get_secret_value() == "weknora-secret"
    assert str(settings.weknora_base_url) == "http://127.0.0.1:8080/"


def test_runtime_settings_reject_invalid_provider_url_without_echoing_secrets(monkeypatch) -> None:
    monkeypatch.setenv("LAB2_POSTGRES_DSN", "postgresql://demo:db-secret@localhost/lab2")
    monkeypatch.setenv("WEKNORA_BASE_URL", "not-a-url")
    monkeypatch.setenv("WEKNORA_API_KEY", "weknora-secret")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "demo-kb")

    with pytest.raises(ValueError) as error:
        RuntimeSettings.from_env(load_dotenv=False)

    assert "db-secret" not in str(error.value)
    assert "weknora-secret" not in str(error.value)


def test_runtime_settings_validation_traceback_does_not_retain_raw_secrets(
    monkeypatch,
) -> None:
    database_secret = "traceback-db-secret"
    provider_secret = "traceback-provider-secret"
    monkeypatch.setenv(
        "LAB2_POSTGRES_DSN",
        f"postgresql://demo:{database_secret}@localhost/lab2",
    )
    monkeypatch.setenv(
        "WEKNORA_BASE_URL",
        f"http://127.0.0.1:8080/?api_key={provider_secret}",
    )
    monkeypatch.setenv("WEKNORA_API_KEY", provider_secret)
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "demo-kb")

    with pytest.raises(ValueError) as error:
        RuntimeSettings.from_env(load_dotenv=False)

    rendered_traceback = "".join(
        traceback.TracebackException.from_exception(error.value).format(chain=True)
    )
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert database_secret not in rendered_traceback
    assert provider_secret not in rendered_traceback


@pytest.mark.parametrize(
    "provider_url",
    [
        "ftp://127.0.0.1:8080",
        "http://user:provider-secret@127.0.0.1:8080",
        "http://127.0.0.1:8080/?token=provider-secret",
        "http://127.0.0.1:8080/#provider-secret",
    ],
)
def test_runtime_settings_reject_unsafe_provider_urls_without_echoing_credentials(
    monkeypatch, provider_url: str
) -> None:
    monkeypatch.setenv("LAB2_POSTGRES_DSN", "postgresql://demo:db-secret@localhost/lab2")
    monkeypatch.setenv("WEKNORA_BASE_URL", provider_url)
    monkeypatch.setenv("WEKNORA_API_KEY", "provider-secret")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "demo-kb")

    with pytest.raises(ValueError) as error:
        RuntimeSettings.from_env(load_dotenv=False)

    assert "db-secret" not in str(error.value)
    assert "provider-secret" not in str(error.value)
