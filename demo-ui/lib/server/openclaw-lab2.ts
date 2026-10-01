import { randomUUID } from "node:crypto";
import { LAB2_AGENT_ID, LAB2_GATEWAY_MODEL } from "@/lib/lab2-contracts";

const MAX_MESSAGE_CHARS = 4_000;
const MAX_REQUEST_BYTES = 16 * 1024;
const MAX_RESPONSE_BYTES = 128 * 1024;
const MAX_RESPONSE_CHARS = 24_000;
const GATEWAY_TIMEOUT_MS = 120_000;
const TRACE_UNAVAILABLE_REASON = "This HTTP chat response does not include per-tool execution events.";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type GatewayConfig = { origin: string; token: string };
type JsonObject = Record<string, unknown>;
type ChatInput = { message: string; conversationId: string };

export type Lab2RouteFailure = {
  status: number;
  code: "invalid_request" | "origin_rejected" | "not_configured" | "upstream_failed" | "upstream_timeout";
  message: string;
};

export type Lab2RouteResult =
  | { ok: true; value: { message: string; conversationId: string; model: string | null; truncated: boolean; usage: { promptTokens: number | null; completionTokens: number | null; totalTokens: number | null } | null; trace: { available: false; reason: string } } }
  | { ok: false; failure: Lab2RouteFailure };

function failure(
  status: Lab2RouteFailure["status"],
  code: Lab2RouteFailure["code"],
  message: string,
): Lab2RouteResult {
  return { ok: false, failure: { status, code, message } };
}

function isRecord(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readGatewayConfig(): GatewayConfig | null {
  const rawUrl = process.env.LAB2_OPENCLAW_GATEWAY_URL?.trim();
  const token = process.env.LAB2_OPENCLAW_GATEWAY_TOKEN?.trim();
  if (!rawUrl || !token || token.length > 4_096 || /[\r\n]/.test(token)) return null;

  try {
    const url = new URL(rawUrl);
    const loopbackHosts = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
    if (
      !["http:", "https:"].includes(url.protocol)
      || !url.hostname
      || (url.protocol !== "https:" && !loopbackHosts.has(url.hostname.toLowerCase()))
      || url.username
      || url.password
      || (url.pathname !== "" && url.pathname !== "/")
      || url.search
      || url.hash
    ) return null;
    return { origin: url.origin, token };
  } catch {
    return null;
  }
}

function isSameOriginRequest(request: Request): boolean {
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  const requestUrl = new URL(request.url);
  const host = request.headers.get("host");
  let expectedOrigin = requestUrl.origin;
  if (host !== null) {
    try {
      // Next may synthesize Request.url with its listening hostname rather than
      // the browser's LAN host. Use the actual Host, never X-Forwarded-Host.
      const hostUrl = new URL(`${requestUrl.protocol}//${host}`);
      if (hostUrl.host.toLowerCase() !== host.toLowerCase() || hostUrl.username ||
          hostUrl.password || hostUrl.pathname !== "/" || hostUrl.search || hostUrl.hash) return false;
      expectedOrigin = hostUrl.origin;
    } catch {
      return false;
    }
  }
  if (!origin || origin !== expectedOrigin) return false;
  return fetchSite === null || fetchSite === "same-origin";
}

async function readLimitedBody(stream: ReadableStream<Uint8Array> | null, limit: number): Promise<Uint8Array | null> {
  if (!stream) return new Uint8Array();
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

async function parseInput(request: Request): Promise<ChatInput | null> {
  const rawLength = request.headers.get("content-length");
  if (rawLength !== null) {
    const declaredLength = Number(rawLength);
    if (!Number.isSafeInteger(declaredLength) || declaredLength < 0 || declaredLength > MAX_REQUEST_BYTES) return null;
  }
  const bytes = await readLimitedBody(request.body, MAX_REQUEST_BYTES);
  if (!bytes) return null;

  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return null;
  }
  if (!isRecord(value) || Object.keys(value).some((key) => key !== "message" && key !== "conversationId")) return null;
  if (typeof value.message !== "string") return null;

  const message = value.message.trim();
  if (!message || message.length > MAX_MESSAGE_CHARS || Buffer.byteLength(message, "utf8") > MAX_REQUEST_BYTES) return null;
  if (value.conversationId === undefined || value.conversationId === null) {
    return { message, conversationId: randomUUID() };
  }
  if (typeof value.conversationId !== "string" || !UUID_PATTERN.test(value.conversationId)) return null;
  return { message, conversationId: value.conversationId.toLowerCase() };
}

function tokenCount(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function messageText(content: unknown): string | null {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return null;
  const parts: unknown[] = content;
  const textParts = parts.flatMap((part): string[] =>
    isRecord(part) && part.type === "text" && typeof part.text === "string" ? [part.text] : [],
  );
  return textParts.length ? textParts.join("\n") : null;
}

export async function runLab2Chat(request: Request): Promise<Lab2RouteResult> {
  if (!isSameOriginRequest(request)) {
    return failure(403, "origin_rejected", "This chat request must come from the Lab2 web app.");
  }
  if (request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") {
    return failure(400, "invalid_request", "Send a JSON chat message and try again.");
  }

  const config = readGatewayConfig();
  if (!config) {
    return failure(503, "not_configured", "Lab2 chat is not configured on this server.");
  }

  let input: ChatInput | null;
  try {
    input = await parseInput(request);
  } catch {
    return failure(400, "invalid_request", "The message is empty or exceeds the chat limit.");
  }
  if (!input) {
    return failure(400, "invalid_request", "The message is empty or exceeds the chat limit.");
  }

  let gatewayResponse: Response;
  try {
    gatewayResponse = await fetch(new URL("/v1/chat/completions", config.origin), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
        "x-openclaw-agent-id": LAB2_AGENT_ID,
        "x-openclaw-model": LAB2_GATEWAY_MODEL,
      },
      body: JSON.stringify({
        model: `openclaw/${LAB2_AGENT_ID}`,
        user: `conv:${input.conversationId}`,
        messages: [{ role: "user", content: input.message }],
        max_completion_tokens: 1_024,
        stream: false,
      }),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(GATEWAY_TIMEOUT_MS),
    });
  } catch (error) {
    const name = isRecord(error) && typeof error.name === "string" ? error.name : "";
    if (name === "TimeoutError" || name === "AbortError") {
      return failure(504, "upstream_timeout", "The Lab2 agent took too long to respond. Please try again.");
    }
    return failure(502, "upstream_failed", "The Lab2 agent could not complete this request.");
  }

  if (!gatewayResponse.ok || !gatewayResponse.headers.get("content-type")?.toLowerCase().includes("application/json")) {
    await gatewayResponse.body?.cancel().catch(() => undefined);
    return failure(502, "upstream_failed", "The Lab2 agent could not complete this request.");
  }

  let payload: unknown;
  try {
    const bytes = await readLimitedBody(gatewayResponse.body, MAX_RESPONSE_BYTES);
    if (!bytes) return failure(502, "upstream_failed", "The Lab2 agent could not complete this request.");
    payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return failure(502, "upstream_failed", "The Lab2 agent could not complete this request.");
  }

  const choices: unknown[] = isRecord(payload) && Array.isArray(payload.choices) ? payload.choices : [];
  const firstChoice = choices[0];
  const assistantMessage = isRecord(firstChoice) && isRecord(firstChoice.message)
    ? messageText(firstChoice.message.content)
    : null;
  if (!assistantMessage?.trim()) {
    return failure(502, "upstream_failed", "The Lab2 agent could not complete this request.");
  }

  const usage = isRecord(payload) && isRecord(payload.usage)
    ? {
      promptTokens: tokenCount(payload.usage.prompt_tokens),
      completionTokens: tokenCount(payload.usage.completion_tokens),
      totalTokens: tokenCount(payload.usage.total_tokens),
    }
    : null;

  return {
    ok: true,
    value: {
      message: assistantMessage.slice(0, MAX_RESPONSE_CHARS),
      conversationId: input.conversationId,
      model: isRecord(payload) && typeof payload.model === "string" ? payload.model.slice(0, 120) : null,
      truncated: assistantMessage.length > MAX_RESPONSE_CHARS,
      usage,
      trace: { available: false, reason: TRACE_UNAVAILABLE_REASON },
    },
  };
}
