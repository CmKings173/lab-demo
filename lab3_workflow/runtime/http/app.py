from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from shared.contracts import CustomerRequirement, WorkflowEvent, WorkflowTopology

from ...workflow.orchestrator import DeterministicWorkflow
from ..runs.models import RunStatus
from ..runs.store import InMemoryRunStore
from .models import APIErrorDetail, APIErrorResponse, CreateRunResponse, RunSnapshot
from .runs import WorkflowFactory, WorkflowRunService


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _error_response(error: APIError) -> JSONResponse:
    body = APIErrorResponse(
        error=APIErrorDetail(
            code=error.code,
            message=error.message,
            details=error.details,
        )
    )
    return JSONResponse(status_code=error.status_code, content=body.model_dump(mode="json"))


def _sse_frame(event: WorkflowEvent) -> str:
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type.value}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def _resolve_cursor(after_sequence: int, last_event_id: str | None) -> int:
    if last_event_id is None or not last_event_id.strip():
        return after_sequence
    try:
        cursor = int(last_event_id)
    except ValueError as exc:
        raise APIError(
            400,
            "INVALID_CURSOR",
            "Last-Event-ID must be a nonnegative integer.",
        ) from exc
    if cursor < 0:
        raise APIError(400, "INVALID_CURSOR", "Last-Event-ID must be a nonnegative integer.")
    return max(after_sequence, cursor)


def create_app(
    *,
    workflow_factory: WorkflowFactory | None = None,
    store: InMemoryRunStore | None = None,
) -> FastAPI:
    app = FastAPI(title="Lab demo workflow API", version="0.1.0")
    service = WorkflowRunService(workflow_factory=workflow_factory, store=store)
    app.state.run_service = service

    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, error: APIError) -> JSONResponse:
        return _error_response(error)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, error: RequestValidationError) -> JSONResponse:
        return _error_response(
            APIError(
                422,
                "VALIDATION_ERROR",
                "Request validation failed.",
                jsonable_encoder(error.errors()),
            )
        )

    @app.post(
        "/runs",
        response_model=CreateRunResponse,
        status_code=202,
        responses={422: {"model": APIErrorResponse}, 503: {"model": APIErrorResponse}},
    )
    def create_run(requirement: CustomerRequirement) -> CreateRunResponse:
        if service.workflow_factory is None:
            raise APIError(503, "WORKFLOW_NOT_CONFIGURED", "Workflow execution is not configured.")
        record = service.submit(requirement)
        return CreateRunResponse(run_id=record.run_id, status=record.status)

    @app.get(
        "/runs/{run_id}",
        response_model=RunSnapshot,
        responses={404: {"model": APIErrorResponse}},
    )
    def get_run(run_id: str) -> RunSnapshot:
        record = service.store.get(run_id)
        if record is None:
            raise APIError(404, "RUN_NOT_FOUND", "Run was not found.")
        return RunSnapshot.from_record(record)

    @app.get("/workflow/topology", response_model=WorkflowTopology)
    def get_topology() -> WorkflowTopology:
        return DeterministicWorkflow.describe_topology()

    @app.get(
        "/runs/{run_id}/events",
        responses={404: {"model": APIErrorResponse}, 400: {"model": APIErrorResponse}},
    )
    def get_run_events(
        run_id: str,
        request: Request,
        after_sequence: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        if service.store.get(run_id) is None:
            raise APIError(404, "RUN_NOT_FOUND", "Run was not found.")
        cursor = _resolve_cursor(after_sequence, last_event_id)

        async def event_stream() -> AsyncIterator[str]:
            nonlocal cursor
            while True:
                if await request.is_disconnected():
                    return
                record = service.store.get(run_id)
                if record is None:
                    return
                events = service.store.events_after(run_id, cursor)
                for event in events:
                    cursor = event.sequence
                    yield _sse_frame(event)
                if record.status in {RunStatus.COMPLETED, RunStatus.FAILED} and not events:
                    return
                await asyncio.sleep(0.02)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
