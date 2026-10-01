"""Small HTTP boundary exposing only the six Lab 2 domain tools."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import Body, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from lab2_rag_agent.openclaw.plugins.catalog_tools import CatalogTools
from lab2_rag_agent.runtime.composition import Lab2Runtime, build_runtime
from shared.tool_args import (
    CompareConfigurationsArgs,
    CompareProductsArgs,
    EstimateAIRequirementsArgs,
    GetProductArgs,
    SearchProductDocumentsArgs,
    SearchProductsArgs,
)

ToolHandler = Callable[[CatalogTools, BaseModel], Any]


def _search_products(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(SearchProductsArgs, raw_args)
    return tools.search_products(args.filters, args.query, args.limit)


def _get_product(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(GetProductArgs, raw_args)
    return tools.get_product(args.product_id)


def _search_product_documents(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(SearchProductDocumentsArgs, raw_args)
    return tools.search_product_documents(args.query, args.product_id, args.top_k)


def _compare_products(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(CompareProductsArgs, raw_args)
    return tools.compare_products(args.product_ids)


def _compare_configurations(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(CompareConfigurationsArgs, raw_args)
    return tools.compare_configurations(args.configuration_ids)


def _estimate_ai_requirements(tools: CatalogTools, raw_args: BaseModel) -> Any:
    args = cast(EstimateAIRequirementsArgs, raw_args)
    return tools.estimate_ai_requirements(
        model_parameters_b=args.model_parameters_b,
        usage=args.usage,
        quantization=args.quantization,
        context_length=args.context_length,
        concurrent_users=args.concurrent_users,
        training_method=args.training_method,
    )


_TOOL_BINDINGS: dict[str, tuple[type[BaseModel], ToolHandler]] = {
    "search_products": (SearchProductsArgs, _search_products),
    "get_product": (GetProductArgs, _get_product),
    "search_product_documents": (SearchProductDocumentsArgs, _search_product_documents),
    "compare_products": (CompareProductsArgs, _compare_products),
    "compare_configurations": (CompareConfigurationsArgs, _compare_configurations),
    "estimate_ai_requirements": (EstimateAIRequirementsArgs, _estimate_ai_requirements),
}


def create_app(
    *,
    tools: CatalogTools | None = None,
    runtime_factory: Callable[[], Lab2Runtime] = build_runtime,
) -> FastAPI:
    """Create API; injected tools are intended for unit tests and local harnesses."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime: Lab2Runtime | None = None
        if tools is None:
            runtime = runtime_factory()
            app.state.catalog_tools = runtime.tools
        else:
            app.state.catalog_tools = tools
        try:
            yield
        finally:
            if runtime is not None:
                runtime.close()

    app = FastAPI(title="Lab 2 Domain Tool API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request"}})

    @app.get("/health")
    def health() -> dict[str, str]:
        # Deliberately checks only that this process can serve HTTP.
        return {"status": "ok"}

    @app.post("/tools/{tool_name}")
    def invoke_tool(tool_name: str, payload: dict[str, Any] = Body(...)) -> JSONResponse:
        binding = _TOOL_BINDINGS.get(tool_name)
        if binding is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "unknown_tool"}},
            )
        argument_model, handler = binding
        try:
            arguments = argument_model.model_validate(payload)
        except ValidationError as exc:
            issues = [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in exc.errors(include_input=False, include_context=False)
            ]
            return JSONResponse(
                status_code=422,
                content={"error": {"code": "invalid_tool_arguments", "issues": issues}},
            )
        try:
            result = handler(app.state.catalog_tools, arguments)
            return JSONResponse(content=jsonable_encoder(result.model_dump(mode="json")))
        except Exception:
            # Provider/DB exception text can contain credentials or connection details.
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "tool_execution_failed"}},
            )

    return app


app = create_app()
