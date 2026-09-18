from __future__ import annotations

from shared.contracts import (
    CustomerRequirement,
    ProductCandidate,
    SizingRequest,
    WorkflowContext,
    WorkflowState,
)
from shared.interfaces import ProductRepository, ProposalService, SizingService, ValidationService
from services.requirement import RequirementAnalyzer


class DeterministicWorkflow:
    def __init__(
        self,
        repository: ProductRepository,
        sizing_service: SizingService,
        validator: ValidationService,
        proposal_service: ProposalService,
    ) -> None:
        self.repository = repository
        self.sizing_service = sizing_service
        self.validator = validator
        self.proposal_service = proposal_service
        self.requirement_analyzer = RequirementAnalyzer()

    def run(self, requirement: CustomerRequirement) -> WorkflowContext:
        context = WorkflowContext(requirement=requirement, history=[WorkflowState.RECEIVED])
        self._transition(context, WorkflowState.ANALYZING_REQUIREMENT)
        missing = self.requirement_analyzer.analyze(requirement)
        if missing:
            context.missing_fields = missing.missing_fields
            self._transition(context, WorkflowState.MISSING_INFORMATION)
            return context

        self._transition(context, WorkflowState.READY_FOR_SIZING)
        self._transition(context, WorkflowState.SIZING)
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

        self._transition(context, WorkflowState.SEARCHING_PRODUCTS)
        result = self.repository.search(
            self._product_search_request(context.sizing_result, requirement.budget_vnd)
        )
        if not result.products:
            self._transition(context, WorkflowState.NO_SUITABLE_PRODUCT)
            return context

        self._transition(context, WorkflowState.VALIDATING_PRODUCTS)
        for product in result.products:
            validation = self.validator.validate(requirement, context.sizing_result, product)
            context.validation_results[product.id] = validation
            if validation.valid:
                context.candidates.append(
                    ProductCandidate(product=product, fit_reasons=["passed deterministic validation"])
                )
        if not context.candidates:
            if all(result.unknown_fields for result in context.validation_results.values()):
                self._transition(context, WorkflowState.INSUFFICIENT_PRODUCT_DATA)
            else:
                self._transition(context, WorkflowState.VALIDATION_FAILED)
            return context

        self._transition(context, WorkflowState.COMPARING_OPTIONS)
        self._transition(context, WorkflowState.GENERATING_PROPOSAL)
        try:
            context.proposal = self.proposal_service.create(
                requirement, context.sizing_result, context.candidates
            )
        except Exception as exc:
            context.errors.append(str(exc))
            self._transition(context, WorkflowState.PROPOSAL_FAILED)
            return context

        self._transition(context, WorkflowState.VERIFYING_PROPOSAL)
        if not context.proposal.sources or not context.proposal.selected_products:
            context.errors.append("Proposal must contain selected products and sources.")
            self._transition(context, WorkflowState.PROPOSAL_FAILED)
            return context
        self._transition(context, WorkflowState.COMPLETED)
        return context

    @staticmethod
    def _product_search_request(sizing, budget_vnd):
        from shared.contracts import ProductFilter, ProductSearchRequest

        return ProductSearchRequest(
            filters=ProductFilter(
                min_ram_gb=sizing.recommended_ram_gb,
                min_gpu_count=sizing.minimum_gpu_count,
                max_price_vnd=budget_vnd,
            )
        )

    @staticmethod
    def _transition(context: WorkflowContext, state: WorkflowState) -> None:
        context.state = state
        context.history.append(state)
