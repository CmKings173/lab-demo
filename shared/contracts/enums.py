from enum import StrEnum


class UsageType(StrEnum):
    INFERENCE = "inference"
    FINE_TUNE = "fine_tune"


class ProductType(StrEnum):
    AI_SERVER = "ai_server"
    AI_WORKSTATION = "ai_workstation"


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class WorkflowState(StrEnum):
    RECEIVED = "received"
    ANALYZE = "analyze"
    CHECK_MISSING_INFORMATION = "check_missing_information"
    MISSING_INFORMATION = "missing_information"
    SIZE = "size"
    SEARCH_PRODUCTS = "search_products"
    BUILD_CONFIGURATIONS = "build_configurations"
    VALIDATE = "validate"
    READ_DOCUMENTS = "read_documents"
    COMPARE = "compare"
    GENERATE_PROPOSAL = "generate_proposal"
    VERIFY = "verify"
    COMPLETE = "complete"
    NO_SUITABLE_PRODUCT = "no_suitable_product"
    INSUFFICIENT_PRODUCT_DATA = "insufficient_product_data"
    SIZING_FAILED = "sizing_failed"
    VALIDATION_FAILED = "validation_failed"
    PROPOSAL_FAILED = "proposal_failed"
