"""Real Lab 3 composition over the shared PostgreSQL catalog."""

from __future__ import annotations

from dataclasses import dataclass

from adapters.real.configuration_options import PostgresConfigurationOptionRepository
from adapters.real.vllm_chat import VLLMChatClient
from adapters.real.weknora_provenance import WeKnoraEvidenceProvenanceVerifier
from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.documents import ProductDocumentRepository
from lab2_rag_agent.catalog.repository import PostgresProductRepository
from lab2_rag_agent.retrieval.weknora import WeKnoraDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.repository import ConfigurationOptionRepository
from lab3_workflow.configuration.repository_builder import (
    RepositoryBackedProductConfigurationBuilder,
)
from lab3_workflow.evidence.provenance import EvidenceProvenanceVerifier
from lab3_workflow.evidence.verified_product_facts import (
    VerifiedDocumentProductFactResolver,
)
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.runtime.conversation import ConversationService
from lab3_workflow.runtime.settings import Lab3RuntimeSettings
from lab3_workflow.sizing.service import DeterministicSizingService
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.interfaces import DocumentSearch, ModelClient, ProductRepository


@dataclass(frozen=True)
class Lab3Runtime:
    settings: Lab3RuntimeSettings
    product_repository: ProductRepository
    configuration_option_repository: ConfigurationOptionRepository
    product_document_repository: ProductDocumentRepository
    document_search: DocumentSearch
    model_client: ModelClient
    conversation_service: ConversationService
    fact_resolver: VerifiedDocumentProductFactResolver
    owns_document_search: bool
    owns_model_client: bool

    def create_workflow(self) -> DeterministicWorkflow:
        """Create a fresh workflow; configuration options are read during each run."""

        return DeterministicWorkflow(
            repository=self.product_repository,
            sizing_service=DeterministicSizingService(),
            configuration_builder=RepositoryBackedProductConfigurationBuilder(
                self.configuration_option_repository
            ),
            validator=RuleBasedConfigurationValidator(),
            document_search=self.document_search,
            comparison_service=RuleBasedComparisonService(),
            proposal_service=RuleBasedProposalService(),
            proposal_verifier=RuleBasedProposalVerifier(),
            fact_resolver=self.fact_resolver,
        )

    def close(self) -> None:
        """Close runtime-owned WeKnora then model clients; injected clients stay caller-owned."""
        try:
            if self.owns_document_search:
                close_search = getattr(self.document_search, "close", None)
                if callable(close_search):
                    close_search()
        finally:
            if self.owns_model_client:
                close_model = getattr(self.model_client, "close", None)
                if callable(close_model):
                    close_model()


def build_lab3_runtime(
    *,
    settings: Lab3RuntimeSettings | None = None,
    document_search: DocumentSearch | None = None,
    model_client: ModelClient | None = None,
) -> Lab3Runtime:
    """Build Lab 3 directly on PostgreSQL adapters, never through Lab 2 HTTP."""

    resolved_settings = settings or Lab3RuntimeSettings.from_env()
    dsn = resolved_settings.postgres_dsn.get_secret_value()
    products = PostgresProductRepository(dsn)
    options = PostgresConfigurationOptionRepository(dsn)
    documents = PostgresProductDocumentRepository(dsn)
    owns_document_search = document_search is None
    resolved_document_search = document_search
    if resolved_document_search is None:
        resolved_document_search = WeKnoraDocumentSearch(
            base_url=resolved_settings.weknora_base_url,
            api_key=resolved_settings.weknora_api_key.get_secret_value(),
            knowledge_base_id=resolved_settings.weknora_knowledge_base_id,
            product_document_repository=documents,
        )
    owns_model_client = model_client is None
    resolved_model_client = model_client
    if resolved_model_client is None:
        resolved_model_client = VLLMChatClient(
            base_url=resolved_settings.llm_base_url,
            model=resolved_settings.llm_model,
            api_key=resolved_settings.llm_api_key,
            json_schema_enabled=resolved_settings.llm_json_schema_enabled,
        )
    verifier: EvidenceProvenanceVerifier = WeKnoraEvidenceProvenanceVerifier(
        documents,
        knowledge_base_id=resolved_settings.weknora_knowledge_base_id,
    )
    return Lab3Runtime(
        settings=resolved_settings,
        product_repository=products,
        configuration_option_repository=options,
        product_document_repository=documents,
        document_search=resolved_document_search,
        model_client=resolved_model_client,
        conversation_service=ConversationService(resolved_model_client),
        fact_resolver=VerifiedDocumentProductFactResolver(verifier),
        owns_document_search=owns_document_search,
        owns_model_client=owns_model_client,
    )
