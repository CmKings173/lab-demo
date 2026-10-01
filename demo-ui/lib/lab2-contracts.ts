export const LAB2_AGENT_ID = "lab2" as const;
export const LAB2_MODEL_TARGET = "Qwen/Qwen3-14B" as const;
export const LAB2_DOMAIN_TOOL_NAMES = [
  "search_products",
  "get_product",
  "search_product_documents",
  "compare_products",
  "compare_configurations",
  "estimate_ai_requirements",
] as const;

export type Lab2ChatRequest = {
  message: string;
  conversationId: string;
};

export type Lab2TokenUsage = {
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
};

export type Lab2ChatResponse = {
  message: string;
  conversationId: string;
  model: string | null;
  truncated: boolean;
  usage: Lab2TokenUsage | null;
  trace: {
    available: false;
    reason: string;
  };
};

export type Lab2ChatErrorCode =
  | "invalid_request"
  | "origin_rejected"
  | "not_configured"
  | "upstream_failed"
  | "upstream_timeout";

export type Lab2ChatErrorResponse = {
  error: {
    code: Lab2ChatErrorCode;
    message: string;
  };
};
