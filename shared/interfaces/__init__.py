"""Stable seams between domain logic and infrastructure implementations."""

from .catalog import ProductRepository
from .comparison import ComparisonService
from .configuration import ConfigurationBuilder
from .configuration_repository import ConfigurationRepository
from .documents import DocumentSearch
from .embeddings import EmbeddingProvider
from .evidence import ProductFactResolver
from .model import ModelClient
from .proposal import ProposalService
from .reranker import Reranker
from .sizing import SizingService
from .validation import ValidationService
from .verification import ProposalVerifier
from .workflow import WorkflowEventSink, WorkflowRunner

__all__ = [
    "ComparisonService",
    "ConfigurationBuilder",
    "ConfigurationRepository",
    "DocumentSearch",
    "ProductFactResolver",
    "EmbeddingProvider",
    "ModelClient",
    "ProductRepository",
    "ProposalService",
    "ProposalVerifier",
    "Reranker",
    "SizingService",
    "ValidationService",
    "WorkflowRunner",
    "WorkflowEventSink",
]
