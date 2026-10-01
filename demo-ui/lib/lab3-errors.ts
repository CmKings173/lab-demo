// Public error text shared by the proxy and browser. Never render provider prose.
export const LAB3_BACKEND_ERRORS: Readonly<Record<string, string>> = {
  VALIDATION_ERROR: "Request validation failed.",
  RUN_NOT_FOUND: "Run was not found.",
  CONVERSATION_NOT_CONFIGURED: "Natural-language conversation is not configured.",
  WORKFLOW_NOT_CONFIGURED: "Workflow execution is not configured.",
  INVALID_CONVERSATION: "At least one user message is required.",
  LLM_ADVISOR_RESPONSE_INVALID: "The model could not produce a valid advisor response.",
  LLM_INVALID_RESPONSE: "The language model returned an invalid response.",
  LLM_UNAVAILABLE: "The language model service is unavailable.",
};

const LAB3_PUBLIC_ERRORS: Readonly<Record<string, string>> = {
  ...LAB3_BACKEND_ERRORS,
  LAB3_PROXY_NOT_CONFIGURED: "Lab 3 conversation proxy is not configured.",
  LAB3_BACKEND_ERROR: "Lab 3 could not process this conversation request.",
  LAB3_CONVERSATION_TIMEOUT: "Lab 3 conversation timed out. Please try again.",
  LAB3_BACKEND_UNAVAILABLE: "Lab 3 conversation service is unavailable.",
};

export function formatLab3ConversationError(code: string | null): string {
  return code !== null && Object.hasOwn(LAB3_PUBLIC_ERRORS, code)
    ? `[${code}] ${LAB3_PUBLIC_ERRORS[code]}`
    : LAB3_PUBLIC_ERRORS.LAB3_BACKEND_ERROR;
}
