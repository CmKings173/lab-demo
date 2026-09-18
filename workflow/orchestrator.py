from __future__ import annotations

from services.requirement import RequirementAnalyzer
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
)
from shared.interfaces import (
    ComparisonService,
    ConfigurationBuilder,
    DocumentSearch,
    ProductRepository,
    ProposalService,
    ProposalVerifier,
    SizingService,
    ValidationService,
)


class WorkflowTransitionError(ValueError):
    """Raised when a workflow attempts a transition outside its state machine."""


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
            {WorkflowState.NO_SUITABLE_PRODUCT, WorkflowState.VALIDATE}
        ),
        WorkflowState.VALIDATE: frozenset(
            {
                WorkflowState.INSUFFICIENT_PRODUCT_DATA,
                WorkflowState.VALIDATION_FAILED,
                WorkflowState.READ_DOCUMENTS,
            }
        ),
        WorkflowState.READ_DOCUMENTS: frozenset({WorkflowState.COMPARE}),
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
    ) -> None:
        self.repository = repository
        self.sizing_service = sizing_service
        self.configuration_builder = configuration_builder
        self.validator = validator
        self.document_search = document_search
        self.comparison_service = comparison_service
        self.proposal_service = proposal_service
        self.proposal_verifier = proposal_verifier
        self.requirement_analyzer = RequirementAnalyzer()

    def run(self, requirement: CustomerRequirement) -> WorkflowContext:
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
            self._transition(context, WorkflowState.SIZING_FAILED)
            return context

        sizing = context.sizing_result
        self._transition(context, WorkflowState.SEARCH_PRODUCTS)
        search_result = self.repository.search(
            self._product_search_request(sizing, requirement.budget_vnd)
        )
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

        self._transition(context, WorkflowState.VALIDATE)
        for configuration in context.configurations:
            result = self.validator.validate(requirement, sizing, configuration)
            context.validation_results[configuration.configuration_id] = result
            if result.status == ValidationStatus.PASS:
                context.candidates.append(
                    ProductCandidate(
                        configuration=configuration,
                        fit_reasons=["passed deterministic validation"],
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

        self._transition(context, WorkflowState.READ_DOCUMENTS)
        passing_configurations = [candidate.configuration for candidate in context.candidates]
        for configuration in passing_configurations:
            result = self.document_search.search(
                DocumentSearchRequest(
                    query="GPU RAM storage configuration evidence",
                    product_id=configuration.product.id,
                )
            )
            context.document_hits.extend(result.hits)

        self._transition(context, WorkflowState.COMPARE)
        context.comparison = self.comparison_service.compare(passing_configurations)

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
            self._transition(context, WorkflowState.PROPOSAL_FAILED)
            return context

        self._transition(context, WorkflowState.VERIFY)
        verification = self.proposal_verifier.verify(context.proposal)
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
                max_price_vnd=budget_vnd,
            )
        )

    @staticmethod
    def _transition(context: WorkflowContext, state: WorkflowState) -> None:
        allowed = DeterministicWorkflow._ALLOWED_TRANSITIONS[context.state]
        if state not in allowed:
            raise WorkflowTransitionError(
                f"Illegal workflow transition: {context.state.value} -> {state.value}"
            )
        context.state = state
        context.history.append(state)
