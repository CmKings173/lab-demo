"""Explicit real-data Lab 3 app factory; importing the demo app stays offline."""

from __future__ import annotations

from fastapi import FastAPI

from lab3_workflow.runtime.composition import build_lab3_runtime
from lab3_workflow.runtime.settings import Lab3RuntimeSettings
from shared.interfaces import DocumentSearch, ModelClient

from .http.app import create_app


def create_real_app(
    *,
    settings: Lab3RuntimeSettings | None = None,
    document_search: DocumentSearch | None = None,
    model_client: ModelClient | None = None,
) -> FastAPI:
    runtime = build_lab3_runtime(
        settings=settings,
        document_search=document_search,
        model_client=model_client,
    )
    app = create_app(
        workflow_factory=runtime.create_workflow,
        shutdown_callback=runtime.close,
        conversation_service=runtime.conversation_service,
    )
    app.state.lab3_runtime = runtime
    return app
