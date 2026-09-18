from enum import StrEnum


class UsageType(StrEnum):
    INFERENCE = "inference"
    FINE_TUNE = "fine_tune"


class ProductType(StrEnum):
    AI_SERVER = "ai_server"
    AI_WORKSTATION = "ai_workstation"


class WorkflowState(StrEnum):
    RECEIVED = "received"
    ANALYZING_REQUIREMENT = "analyzing_requirement"
    MISSING_INFORMATION = "missing_information"
    READY_FOR_SIZING = "ready_for_sizing"
    SIZING = "sizing"
    SEARCHING_PRODUCTS = "searching_products"
    VALIDATING_PRODUCTS = "validating_products"
    READING_DOCUMENTS = "reading_documents"
    COMPARING_OPTIONS = "comparing_options"
    GENERATING_PROPOSAL = "generating_proposal"
    VERIFYING_PROPOSAL = "verifying_proposal"
    COMPLETED = "completed"
    NO_SUITABLE_PRODUCT = "no_suitable_product"
    INSUFFICIENT_PRODUCT_DATA = "insufficient_product_data"
    SIZING_FAILED = "sizing_failed"
    VALIDATION_FAILED = "validation_failed"
    PROPOSAL_FAILED = "proposal_failed"
