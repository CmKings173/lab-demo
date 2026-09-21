from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

from lab3_workflow.evidence import DeterministicProductFactResolver
from lab3_workflow.requirement import RequirementAnalyzer
from lab3_workflow.workflow.events import NoOpWorkflowEventSink, WorkflowEventEmitter
from shared.contracts import (
    CustomerRequirement,
    DocumentSearchRequest,
    ProductCandidate,
    ProductFilter,
    ProductSearchRequest,
    SizingRequest,
    SizingResult,
    ValidationStatus,
    WorkflowContext,
    WorkflowState,
    WorkflowTopology,
)
from shared.interfaces import (
    ComparisonService,
    ConfigurationBuilder,
    DocumentSearch,
    ProductFactResolver,
    ProductRepository,
    ProposalService,
    ProposalVerifier,
    SizingService,
    ValidationService,
    WorkflowEventSink,
)


class WorkflowTransitionError(ValueError):
    """Raised when a workflow attempts a transition outside its state machine."""


_ACTIVE_EVENT_EMITTER: ContextVar[WorkflowEventEmitter | None] = ContextVar(
    "active_workflow_event_emitter", default=None
)


@contextmanager
def _observed_tool(
    name: str, payload: Mapping[str, object] | None = None
) -> Iterator[None]:
    emitter = _ACTIVE_EVENT_EMITTER.get()
    if emitter is None:
        yield
        return
    started_at = emitter.tool_started(name, payload)
    try:
        yield
    except Exception as exc:
        emitter.tool_failed(name, started_at, exc)
        raise
    else:
        emitter.tool_completed(name, started_at)


class DeterministicWorkflow:
    _ALLOWED_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
        WorkflowState.RECEIVED: frozenset({WorkflowState.ANALYZE}),
        WorkflowState.ANALYZE: frozenset({WorkflowState.CHECK_MISSING_INFORMATION}),
        WorkflowState.CHECK_MISSING_INFORMATION: frozenset(
            {WorkflowState.MISSING_INFORMATION, WorkflowState.SIZE}
        ),
        WorkflowState.MISSING_INFORMATION: frozenset(),
        WorkflowState.SIZE: frozenset(
            {WorkflowState.SIZING_FAILED, WorkflowState.SEARCH_PRODUCTS}
        ),
        WorkflowState.SEARCH_PRODUCTS: frozenset(
            {WorkflowState.NO_SUITABLE_PRODUCT, WorkflowState.BUILD_CONFIGURATIONS}
        ),
        WorkflowState.BUILD_CONFIGURATIONS: frozenset(
            {WorkflowState.NO_SUITABLE_PRODUCT, WorkflowState.VALIDATE_INITIAL}
        ),
        WorkflowState.VALIDATE_INITIAL: frozenset(
            {
                WorkflowState.VALIDATION_FAILED,
                WorkflowState.RESOLVE_UNKNOWN_FACTS,
            }
        ),
        WorkflowState.RESOLVE_UNKNOWN_FACTS: frozenset({WorkflowState.READ_DOCUMENTS}),
        WorkflowState.READ_DOCUMENTS: frozenset({WorkflowState.APPLY_VERIFIED_FACTS}),
        WorkflowState.APPLY_VERIFIED_FACTS: frozenset({WorkflowState.REVALIDATE}),
        WorkflowState.REVALIDATE: frozenset(
            {
                WorkflowState.INSUFFICIENT_PRODUCT_DATA,
                WorkflowState.VALIDATION_FAILED,
                WorkflowState.COMPARE,
            }
        ),
        WorkflowState.COMPARE: frozenset({WorkflowState.GENERATE_PROPOSAL}),
        WorkflowState.GENERATE_PROPOSAL: frozenset(
            {WorkflowState.PROPOSAL_FAILED, WorkflowState.VERIFY}
        ),
        WorkflowState.VERIFY: frozenset(
            {WorkflowState.PROPOSAL_FAILED, WorkflowState.COMPLETE}
        ),
        WorkflowState.COMPLETE: frozenset(),
        WorkflowState.NO_SUITABLE_PRODUCT: frozenset(),
        WorkflowState.INSUFFICIENT_PRODUCT_DATA: frozenset(),
        WorkflowState.SIZING_FAILED: frozenset(),
        WorkflowState.VALIDATION_FAILED: frozenset(),
        WorkflowState.PROPOSAL_FAILED: frozenset(),
    }

    @classmethod
    def describe_topology(cls) -> WorkflowTopology:
        """Describe the canonical workflow graph without duplicating its transitions."""

        return WorkflowTopology.from_transitions(cls._ALLOWED_TRANSITIONS)

    def __init__(
        self,
        repository: ProductRepository,
        sizing_service: SizingService,
        configuration_builder: ConfigurationBuilder,
        validator: ValidationService,
        document_search: DocumentSearch,
        comparison_service: ComparisonService,
        proposal_service: ProposalService,
        proposal_verifier: ProposalVerifier,
        fact_resolver: ProductFactResolver | None = None,
        event_sink: WorkflowEventSink | None = None,
    ) -> None:
        self.repository = repository
        self.sizing_service = sizing_service
        self.configuration_builder = configuration_builder
        self.validator = validator
        self.document_search = document_search
        self.fact_resolver = fact_resolver or DeterministicProductFactResolver()
        self.comparison_service = comparison_service
        self.proposal_service = proposal_service
        self.proposal_verifier = proposal_verifier
        self.event_sink = event_sink or NoOpWorkflowEventSink()
        self.requirement_analyzer = RequirementAnalyzer()

    def run(
        self, requirement: CustomerRequirement, run_id: str | None = None
    ) -> WorkflowContext:
        emitter = WorkflowEventEmitter(self.event_sink, run_id=run_id)
        token = _ACTIVE_EVENT_EMITTER.set(emitter)
        emitter.workflow_started()
        emitter.state_started(WorkflowState.RECEIVED)
        try:
            context = self._run_business(requirement)
        except Exception as exc:
            state = emitter.active_state or WorkflowState.RECEIVED
            emitter.state_failed(state, exc)
            emitter.workflow_failed(state, exc)
            raise
        else:
            emitter.state_completed(context.state)
            emitter.workflow_completed(context.state)
            return context
        finally:
            _ACTIVE_EVENT_EMITTER.reset(token)

    def _run_business(self, requirement: CustomerRequirement) -> WorkflowContext:
        context = WorkflowContext(requirement=requirement, history=[WorkflowState.RECEIVED])
        self._transition(context, WorkflowState.ANALYZE)
        self._transition(context, WorkflowState.CHECK_MISSING_INFORMATION)
        missing = self.requirement_analyzer.analyze(requirement)
        if missing:
            context.missing_fields = missing.missing_fields
            context.missing_information = missing
            self._transition(context, WorkflowState.MISSING_INFORMATION)
            return context

        self._transition(context, WorkflowState.SIZE)
        try:
            context.sizing_result = self.sizing_service.estimate(
                SizingRequest(
                    model_parameters_b=requirement.model_size_b,
                    usage=requirement.usage,
                    context_length=requirement.context_length,
                    concurrent_users=requirement.concurrent_users,
                    training_method=requirement.training_method,
                )
            )
        except Exception as exc:
            context.errors.append(str(exc))
            emitter = _ACTIVE_EVENT_EMITTER.get()
            if emitter is not None:
                emitter.state_failed(WorkflowState.SIZE, exc)
            self._transition(context, WorkflowState.SIZING_FAILED)
            return context

        sizing = context.sizing_result
        self._transition(context, WorkflowState.SEARCH_PRODUCTS)
        search_request = self._product_search_request(sizing, requirement.budget_vnd)
        with _observed_tool(
            "ProductRepository.search",
            {
                "min_ram_gb": search_request.filters.min_ram_gb,
                "max_base_price_vnd": search_request.filters.max_base_price_vnd,
            },
        ):
            search_result = self.repository.search(search_request)
        if not search_result.products:
            self._transition(context, WorkflowState.NO_SUITABLE_PRODUCT)
            return context

        self._transition(context, WorkflowState.BUILD_CONFIGURATIONS)
        context.configurations = self.configuration_builder.build(
            search_result.products, sizing, requirement
        )
        if not context.configurations:
            self._transition(context, WorkflowState.NO_SUITABLE_PRODUCT)
            return context

        self._transition(context, WorkflowState.VALIDATE_INITIAL)
        for configuration in context.configurations:
            result = self.validator.validate(requirement, sizing, configuration)
            context.validation_results[configuration.configuration_id] = result
            emitter = _ACTIVE_EVENT_EMITTER.get()
            if emitter is not None:
                emitter.validation_result(
                    configuration.configuration_id, result, WorkflowState.VALIDATE_INITIAL
                )
        if {
            result.status for result in context.validation_results.values()
        } == {ValidationStatus.FAIL}:
            self._transition(context, WorkflowState.VALIDATION_FAILED)
            return context

        self._transition(context, WorkflowState.RESOLVE_UNKNOWN_FACTS)
        self._transition(context, WorkflowState.READ_DOCUMENTS)
        facts_by_configuration = {}
        for configuration in context.configurations:
            validation = context.validation_results[configuration.configuration_id]
            if validation.status == ValidationStatus.FAIL:
                continue
            resolvable = [field for field in validation.unknown_fields
                          if field in {"max_ram_gb", "max_gpu_slots", "max_storage_gb"}]
            query_fields = resolvable + ["memory_gb", "capacity_gb", "max_gpu_slots", "max_ram_gb"]
            document_request = DocumentSearchRequest(
                query=" ".join(query_fields),
                product_id=configuration.product.id,
            )
            with _observed_tool(
                "DocumentSearch.search",
                {"product_id": document_request.product_id},
            ):
                result = self.document_search.search(document_request)
            context.document_hits.extend(result.hits)
            emitter = _ACTIVE_EVENT_EMITTER.get()
            if emitter is not None:
                for hit in result.hits:
                    emitter.document_hit(hit)
            facts = self.fact_resolver.resolve(
                configuration, resolvable, result.hits
            )
            facts_by_configuration[configuration.configuration_id] = facts
            context.resolved_facts.extend(facts)
            if emitter is not None:
                for fact in facts:
                    emitter.fact_resolved(fact)

        self._transition(context, WorkflowState.APPLY_VERIFIED_FACTS)
        context.configurations = [
            self.fact_resolver.apply(
                configuration,
                facts_by_configuration.get(configuration.configuration_id, []),
            )
            for configuration in context.configurations
        ]

        self._transition(context, WorkflowState.REVALIDATE)
        context.validation_results = {}
        context.candidates = []
        for configuration in context.configurations:
            result = self.validator.validate(requirement, sizing, configuration)
            context.validation_results[configuration.configuration_id] = result
            emitter = _ACTIVE_EVENT_EMITTER.get()
            if emitter is not None:
                emitter.validation_result(
                    configuration.configuration_id, result, WorkflowState.REVALIDATE
                )
            if result.status == ValidationStatus.PASS:
                context.candidates.append(
                    ProductCandidate(
                        configuration=configuration,
                        fit_reasons=["passed deterministic validation after evidence resolution"],
                    )
                )
        if not context.candidates:
            statuses = {result.status for result in context.validation_results.values()}
            terminal = (
                WorkflowState.INSUFFICIENT_PRODUCT_DATA
                if ValidationStatus.UNKNOWN in statuses
                else WorkflowState.VALIDATION_FAILED
            )
            self._transition(context, terminal)
            return context

        self._transition(context, WorkflowState.COMPARE)
        passing_configurations = [candidate.configuration for candidate in context.candidates]
        context.comparison = self.comparison_service.compare_configurations(
            passing_configurations
        )

        self._transition(context, WorkflowState.GENERATE_PROPOSAL)
        try:
            context.proposal = self.proposal_service.create(
                requirement,
                sizing,
                passing_configurations,
                context.comparison,
                context.document_hits,
            )
        except Exception as exc:
            context.errors.append(str(exc))
            emitter = _ACTIVE_EVENT_EMITTER.get()
            if emitter is not None:
                emitter.state_failed(WorkflowState.GENERATE_PROPOSAL, exc)
            self._transition(context, WorkflowState.PROPOSAL_FAILED)
            return context

        emitter = _ACTIVE_EVENT_EMITTER.get()
        if emitter is not None:
            emitter.proposal_generated(
                [configuration.configuration_id for configuration in passing_configurations],
                len(context.document_hits),
            )

        self._transition(context, WorkflowState.VERIFY)
        verification = self.proposal_verifier.verify(context.proposal)
        if emitter is not None:
            emitter.proposal_verified(verification)
        if not verification.valid:
            context.errors.extend(verification.errors)
            self._transition(context, WorkflowState.PROPOSAL_FAILED)
            return context
        self._transition(context, WorkflowState.COMPLETE)
        return context

    @staticmethod
    def _product_search_request(sizing: SizingResult, budget_vnd: int) -> ProductSearchRequest:
        return ProductSearchRequest(
            filters=ProductFilter(
                min_ram_gb=sizing.recommended_system_ram_gb,
                max_base_price_vnd=budget_vnd,
            )
        )

    @staticmethod
    def _transition(
        context: WorkflowContext,
        state: WorkflowState,
        event_emitter: WorkflowEventEmitter | None = None,
    ) -> None:
        allowed = DeterministicWorkflow._ALLOWED_TRANSITIONS[context.state]
        if state not in allowed:
            raise WorkflowTransitionError(
                f"Illegal workflow transition: {context.state.value} -> {state.value}"
            )
        emitter = event_emitter or _ACTIVE_EVENT_EMITTER.get()
        if emitter is not None:
            emitter.state_completed(context.state)
        context.state = state
        context.history.append(state)
        if emitter is not None:
            emitter.state_started(state)
