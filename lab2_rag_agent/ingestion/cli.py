"""Thin one-file command-line entry point for operator document ingestion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from lab2_rag_agent.catalog.document_repository import PostgresProductDocumentRepository
from lab2_rag_agent.catalog.repository import PostgresProductRepository
from lab2_rag_agent.ingestion.weknora import (
    WeKnoraDocumentIngestion,
    WeKnoraIngestionError,
)
from lab2_rag_agent.runtime.settings import RuntimeSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import one explicit product document into the configured WeKnora KB."
    )
    parser.add_argument("--product-id", required=True, help="Exact Lab 2 catalog product ID")
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="One local file to import; directories are rejected",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = RuntimeSettings.from_env()
        dsn = settings.postgres_dsn.get_secret_value()
        products = PostgresProductRepository(dsn)
        documents = PostgresProductDocumentRepository(dsn)
        with WeKnoraDocumentIngestion(
            base_url=str(settings.weknora_base_url),
            api_key=settings.weknora_api_key.get_secret_value(),
            knowledge_base_id=settings.weknora_knowledge_base_id,
            product_repository=products,
            product_document_repository=documents,
        ) as ingestion:
            mapping = ingestion.ingest_file(args.product_id, args.file)
    except WeKnoraIngestionError as exc:
        print(f"Document ingestion failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        # Runtime/database exceptions may contain local credentials or connection details.
        print("Document ingestion failed due to a local runtime error.", file=sys.stderr)
        return 1

    print(
        "Document ready: "
        f"product_id={mapping.product_id} knowledge_id={mapping.knowledge_id} "
        f"status={mapping.provider_parse_status}"
    )
    return 0
