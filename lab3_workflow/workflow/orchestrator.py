from __future__ import annotations

from lab3_workflow.evidence import DeterministicProductFactResolver
from lab3_workflow.requirement import RequirementAnalyzer
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
    ProductFactResolver,
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

        self._transition(context, WorkflowState.VALIDATE_INITIAL)
        for configuration in context.configurations:
            result = self.validator.validate(requirement, sizing, configuration)
            context.validation_results[configuration.configuration_id] = result
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
            result = self.document_search.search(
                DocumentSearchRequest(
                    query=" ".join(query_fields),
                    product_id=configuration.product.id,
                )
            )
            context.document_hits.extend(result.hits)
            facts = self.fact_resolver.resolve(
                configuration, resolvable, result.hits
            )
            facts_by_configuration[configuration.configuration_id] = facts
            context.resolved_facts.extend(facts)

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
                max_base_price_vnd=budget_vnd,
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
