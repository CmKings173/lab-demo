from __future__ import annotations

import inspect
import traceback

import httpx
import pytest

from adapters.real.weknora_provenance import WeKnoraEvidenceProvenanceVerifier
from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.retrieval.weknora import WeKnoraDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.evidence.verified_product_facts import (
    VerifiedDocumentProductFactResolver,
)
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.runtime import composition
from lab3_workflow.runtime.settings import Lab3RuntimeSettings
from lab3_workflow.sizing.service import DeterministicSizingService
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import CustomerRequirement, DocumentSearchResult


def _settings(api_key: str = "runtime-test-secret") -> Lab3RuntimeSettings:
    return Lab3RuntimeSettings(
        postgres_dsn="postgresql://operator:pw@db/catalog",
        weknora_base_url="https://weknora.example.invalid",
        weknora_api_key=api_key,
        weknora_knowledge_base_id="configured-kb",
        llm_base_url="http://127.0.0.1:8001/v1",
        llm_model="Qwen/Qwen3-14B",
    )


def test_lab3_settings_redact_database_credentials_and_suppress_invalid_input_chain(
    monkeypatch,
):
    secret = "phase32-db-secret-marker"
    monkeypatch.setenv("LAB3_POSTGRES_DSN", f"mongodb://operator:{secret}@db/catalog")
    monkeypatch.setenv("WEKNORA_BASE_URL", "https://weknora.example.invalid")
    monkeypatch.setenv("WEKNORA_API_KEY", "phase33-provider-marker")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "configured-kb")
    monkeypatch.setenv("LAB3_LLM_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setenv("LAB3_LLM_MODEL", "Qwen/Qwen3-14B")

    try:
        Lab3RuntimeSettings.from_env(load_dotenv=False)
    except ValueError as error:
        rendered = "".join(traceback.format_exception(error))
    else:
        raise AssertionError("invalid PostgreSQL DSN should be rejected")

    assert "Invalid Lab 3 runtime environment configuration" in rendered
    assert secret not in rendered
    assert "mongodb://" not in rendered


def test_lab3_settings_repr_redacts_valid_database_credentials():
    secret = "phase32-repr-secret-marker"
    api_secret = "phase33-repr-api-secret"
    settings = Lab3RuntimeSettings(
        postgres_dsn=f"postgresql://operator:{secret}@db/catalog",
        weknora_base_url="https://weknora.example.invalid",
        weknora_api_key=api_secret,
        weknora_knowledge_base_id="configured-kb",
        llm_base_url="http://127.0.0.1:8001/v1",
        llm_model="Qwen/Qwen3-14B",
    )

    assert secret not in repr(settings)
    assert api_secret not in repr(settings)
    assert settings.postgres_dsn.get_secret_value().endswith("@db/catalog")


def test_lab3_settings_reuse_existing_weknora_environment_names(monkeypatch):
    api_secret = "phase33-env-api-secret"
    monkeypatch.setenv("LAB3_POSTGRES_DSN", "postgresql://operator:pw@db/catalog")
    monkeypatch.setenv("WEKNORA_BASE_URL", "https://weknora.example.invalid/api")
    monkeypatch.setenv("WEKNORA_API_KEY", api_secret)
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "shared-kb")
    monkeypatch.setenv("LAB3_LLM_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setenv("LAB3_LLM_MODEL", "Qwen/Qwen3-14B")

    settings = Lab3RuntimeSettings.from_env(load_dotenv=False)

    assert settings.weknora_base_url == "https://weknora.example.invalid/api"
    assert settings.weknora_api_key.get_secret_value() == api_secret
    assert api_secret not in repr(settings)
    assert settings.weknora_knowledge_base_id == "shared-kb"


def test_lab3_settings_suppress_invalid_weknora_secret_from_exception_chain(monkeypatch):
    secret = "phase33-invalid-provider-secret"
    monkeypatch.setenv("LAB3_POSTGRES_DSN", "postgresql://operator:pw@db/catalog")
    monkeypatch.setenv("WEKNORA_BASE_URL", f"https://user:{secret}@weknora.example.invalid")
    monkeypatch.setenv("WEKNORA_API_KEY", secret)
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "shared-kb")
    monkeypatch.setenv("LAB3_LLM_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setenv("LAB3_LLM_MODEL", "Qwen/Qwen3-14B")

    with pytest.raises(ValueError) as error:
        Lab3RuntimeSettings.from_env(load_dotenv=False)

    rendered = "".join(traceback.format_exception(error.value))
    assert "Invalid Lab 3 runtime environment configuration" in rendered
    assert secret not in rendered


def test_real_structured_data_composition_wires_repositories_without_lab2_http(
    monkeypatch,
):
    constructed: list[tuple[str, str]] = []

    class ProductRepository:
        def __init__(self, dsn):
            constructed.append(("products", dsn))

        def search(self, _request):
            raise AssertionError("test does not execute the workflow")

        def get(self, _product_id):
            return None

    class OptionRepository:
        def __init__(self, dsn):
            constructed.append(("options", dsn))

        def list_gpu_options(self, _product_ids):
            return []

        def list_ram_options(self, _product_ids):
            return []

        def list_storage_options(self, _product_ids):
            return []

    class DocumentRepository:
        def __init__(self, dsn):
            constructed.append(("documents", dsn))

    class InjectedDocumentSearch:
        def search(self, _request):
            return DocumentSearchResult()

        def close(self):
            raise AssertionError("externally injected search is caller-owned")

    monkeypatch.setattr(composition, "PostgresProductRepository", ProductRepository)
    monkeypatch.setattr(
        composition, "PostgresConfigurationOptionRepository", OptionRepository
    )
    monkeypatch.setattr(
        composition, "PostgresProductDocumentRepository", DocumentRepository
    )
    settings = _settings()
    runtime = composition.build_lab3_runtime(
        settings=settings,
        document_search=InjectedDocumentSearch(),
    )

    workflow = runtime.create_workflow()

    assert set(constructed) == {
        ("products", "postgresql://operator:pw@db/catalog"),
        ("options", "postgresql://operator:pw@db/catalog"),
        ("documents", "postgresql://operator:pw@db/catalog"),
    }
    assert isinstance(workflow, DeterministicWorkflow)
    assert isinstance(workflow.sizing_service, DeterministicSizingService)
    assert isinstance(workflow.validator, RuleBasedConfigurationValidator)
    assert isinstance(workflow.comparison_service, RuleBasedComparisonService)
    assert isinstance(workflow.proposal_service, RuleBasedProposalService)
    assert isinstance(workflow.proposal_verifier, RuleBasedProposalVerifier)
    assert isinstance(workflow.fact_resolver, VerifiedDocumentProductFactResolver)
    assert runtime.owns_document_search is False
    assert isinstance(
        workflow.configuration_builder,
        composition.RepositoryBackedProductConfigurationBuilder,
    )
    assert workflow.repository is runtime.product_repository
    assert workflow.document_search is runtime.document_search
    assert "lab2_rag_agent.runtime" not in inspect.getsource(composition)
    assert "lab2_rag_agent.catalog.repository" in inspect.getsource(composition)
    runtime.close()


def test_real_composition_constructs_owned_weknora_search_and_postgres_mapping_repo(
    monkeypatch,
):
    class Repository:
        def __init__(self, _dsn):
            pass

    monkeypatch.setattr(composition, "PostgresProductRepository", Repository)
    monkeypatch.setattr(composition, "PostgresConfigurationOptionRepository", Repository)

    runtime = composition.build_lab3_runtime(settings=_settings())
    try:
        assert isinstance(runtime.document_search, WeKnoraDocumentSearch)
        assert isinstance(
            runtime.document_search._documents,
            PostgresProductDocumentRepository,
        )
        assert runtime.owns_document_search is True
        assert isinstance(
            runtime.create_workflow().fact_resolver._provenance_verifier,
            WeKnoraEvidenceProvenanceVerifier,
        )
        assert runtime.conversation_service.model_client is runtime.model_client
        assert runtime.owns_model_client is True
    finally:
        runtime.close()


def test_real_app_lifespan_closes_owned_weknora_client_and_preserves_executor_shutdown(
    monkeypatch,
):
    from fastapi.testclient import TestClient

    from lab3_workflow.runtime.real_app import create_real_app

    class Repository:
        def __init__(self, _dsn):
            pass

    monkeypatch.setattr(composition, "PostgresProductRepository", Repository)
    monkeypatch.setattr(composition, "PostgresConfigurationOptionRepository", Repository)
    monkeypatch.setattr(composition, "PostgresProductDocumentRepository", Repository)

    app = create_real_app(settings=_settings())
    client = app.state.lab3_runtime.document_search._http_client
    model_client = app.state.lab3_runtime.model_client._http_client
    assert isinstance(client, httpx.Client)
    assert not client.is_closed
    assert isinstance(model_client, httpx.Client)
    assert not model_client.is_closed

    with TestClient(app):
        pass

    assert client.is_closed
    assert model_client.is_closed
    with pytest.raises(RuntimeError, match="shutdown|shut down"):
        app.state.run_service.submit(
            CustomerRequirement(model_size_b=20, usage="inference")
        )


def test_real_app_does_not_close_externally_injected_document_search(monkeypatch):
    from fastapi.testclient import TestClient

    from lab3_workflow.runtime.real_app import create_real_app

    class Repository:
        def __init__(self, _dsn):
            pass

    class InjectedSearch:
        close_calls = 0

        def search(self, _request):
            return DocumentSearchResult()

        def close(self):
            self.close_calls += 1

    monkeypatch.setattr(composition, "PostgresProductRepository", Repository)
    monkeypatch.setattr(composition, "PostgresConfigurationOptionRepository", Repository)
    monkeypatch.setattr(composition, "PostgresProductDocumentRepository", Repository)
    search = InjectedSearch()
    app = create_real_app(settings=_settings(), document_search=search)

    with TestClient(app):
        pass

    assert search.close_calls == 0
    assert app.state.lab3_runtime.owns_document_search is False


def test_injected_model_client_remains_caller_owned(monkeypatch):
    class Repository:
        def __init__(self, _dsn):
            pass

    class InjectedSearch:
        def search(self, _request):
            return DocumentSearchResult()

    class InjectedModel:
        close_calls = 0

        def complete(self, _messages, tools=()):
            raise AssertionError("test does not make model calls")

        def close(self):
            self.close_calls += 1

    monkeypatch.setattr(composition, "PostgresProductRepository", Repository)
    monkeypatch.setattr(composition, "PostgresConfigurationOptionRepository", Repository)
    monkeypatch.setattr(composition, "PostgresProductDocumentRepository", Repository)
    model = InjectedModel()
    runtime = composition.build_lab3_runtime(
        settings=_settings(),
        document_search=InjectedSearch(),
        model_client=model,
    )

    runtime.close()

    assert runtime.owns_document_search is False
    assert runtime.owns_model_client is False
    assert model.close_calls == 0


def test_real_app_closes_owned_resources_in_executor_weknora_model_order(monkeypatch):
    from fastapi.testclient import TestClient

    from lab3_workflow.runtime.real_app import create_real_app

    closed: list[str] = []

    class Repository:
        def __init__(self, _dsn):
            pass

    class OwnedSearch:
        def search(self, _request):
            return DocumentSearchResult()

        def close(self):
            closed.append("weknora")

    class OwnedModel:
        def complete(self, _messages, tools=()):
            raise AssertionError("test does not make model calls")

        def close(self):
            closed.append("model")

    monkeypatch.setattr(composition, "PostgresProductRepository", Repository)
    monkeypatch.setattr(composition, "PostgresConfigurationOptionRepository", Repository)
    monkeypatch.setattr(composition, "PostgresProductDocumentRepository", Repository)
    monkeypatch.setattr(composition, "WeKnoraDocumentSearch", lambda **_kwargs: OwnedSearch())
    monkeypatch.setattr(composition, "VLLMChatClient", lambda **_kwargs: OwnedModel())
    app = create_real_app(settings=_settings())
    original_shutdown = app.state.run_service.shutdown

    def shutdown(*, wait: bool = True):
        closed.append("executor")
        original_shutdown(wait=wait)

    app.state.run_service.shutdown = shutdown
    with TestClient(app):
        pass

    assert closed == ["executor", "weknora", "model"]


def test_real_app_factory_is_separate_and_injects_lab3_runtime(monkeypatch):
    from lab3_workflow.runtime import real_app

    class ProductRepository:
        def __init__(self, _dsn):
            pass

    class OptionRepository:
        def __init__(self, _dsn):
            pass

        def list_gpu_options(self, _product_ids):
            return []

        def list_ram_options(self, _product_ids):
            return []

        def list_storage_options(self, _product_ids):
            return []

    monkeypatch.setattr(composition, "PostgresProductRepository", ProductRepository)
    monkeypatch.setattr(
        composition, "PostgresConfigurationOptionRepository", OptionRepository
    )
    monkeypatch.setattr(
        composition, "PostgresProductDocumentRepository", OptionRepository
    )
    app = real_app.create_real_app(
        settings=_settings()
    )

    assert app.state.lab3_runtime.product_repository is not None
    assert app.state.run_service.workflow_factory == app.state.lab3_runtime.create_workflow
