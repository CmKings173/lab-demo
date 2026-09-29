"""Operator-only Lab 2 document ingestion adapters."""

from lab2_rag_agent.ingestion.weknora import (
    WeKnoraDocumentIngestion,
    WeKnoraIngestionError,
)

__all__ = ["WeKnoraDocumentIngestion", "WeKnoraIngestionError"]
