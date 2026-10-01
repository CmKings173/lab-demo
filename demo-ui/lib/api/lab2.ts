import type { Lab2ChatRequest, Lab2ChatResponse, Lab2TokenUsage } from "@/lib/lab2-contracts";
import { isNullableNumber, isNullableString, isRecord, isString, parseApiResponse } from "./http";

function isTokenUsage(value: unknown): value is Lab2TokenUsage | null {
  return value === null || (isRecord(value) && isNullableNumber(value.promptTokens) &&
    isNullableNumber(value.completionTokens) && isNullableNumber(value.totalTokens));
}

function isLab2ChatResponse(value: unknown): value is Lab2ChatResponse {
  return isRecord(value) && isString(value.message) && isString(value.conversationId) &&
    isNullableString(value.model) && typeof value.truncated === "boolean" && isTokenUsage(value.usage) &&
    isRecord(value.trace) && value.trace.available === false && isString(value.trace.reason);
}

export async function sendLab2Message(
  request: Lab2ChatRequest,
  signal?: AbortSignal,
): Promise<Lab2ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/api/lab2/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
      cache: "no-store",
      credentials: "same-origin",
      signal,
    });
  } catch {
    throw new Error("Could not reach the Lab2 chat endpoint. Check the web app and try again.");
  }

  return parseApiResponse(response, isLab2ChatResponse, "The Lab2 agent could not complete this request");
}
