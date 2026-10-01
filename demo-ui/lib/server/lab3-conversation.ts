// Server-only, fixed-path proxy. Other rewrites (especially SSE) keep their policy.
import { LAB3_BACKEND_ERRORS as SAFE_ERRORS } from "../lab3-errors";

export const LAB3_CONVERSATION_TIMEOUT_MS = 135_000;
const MAX_REQUEST_BYTES = 96 * 1024;
const MAX_RESPONSE_BYTES = 128 * 1024;
const MAX_ERROR_BYTES = 16 * 1024;

function failure(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, {
    status, headers: { "Cache-Control": "no-store" },
  });
}

async function boundedText(body: ReadableStream<Uint8Array> | null, limit: number,
  signal: AbortSignal): Promise<string> {
  if (!body) throw new Error("empty body");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", cancel, { once: true });
  try {
    while (true) {
      signal.throwIfAborted();
      const chunk = await reader.read();
      signal.throwIfAborted();
      if (chunk.done) break;
      length += chunk.value.byteLength;
      if (length > limit) {
        cancel();
        throw new Error("body exceeds limit");
      }
      chunks.push(chunk.value);
    }
    return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
  } finally {
    signal.removeEventListener("abort", cancel);
    reader.releaseLock();
  }
}

function safeError(payload: unknown): { code: string; message: string } | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
      Object.keys(payload).length !== 1 || !("error" in payload)) return null;
  const error = payload.error;
  if (!error || typeof error !== "object" || Array.isArray(error)) return null;
  const keys = Object.keys(error);
  if (!keys.includes("code") || !keys.includes("message") ||
      keys.some((key) => !["code", "message", "details"].includes(key)) ||
      !("code" in error) || !("message" in error) ||
      typeof error.code !== "string" || !Object.hasOwn(SAFE_ERRORS, error.code) ||
      typeof error.message !== "string" || !error.message.trim() ||
      error.message.length > 300) return null;
  // FastAPI may include validation details containing input values. Discard them.
  return { code: error.code, message: SAFE_ERRORS[error.code] };
}

export async function proxyLab3Conversation(request: Request, options: {
  backendUrl?: string; timeoutMs?: number;
} = {}): Promise<Response> {
  let target: URL;
  const timeoutMs = options.timeoutMs ?? Number(
    process.env.LAB3_CONVERSATION_TIMEOUT_MS ?? LAB3_CONVERSATION_TIMEOUT_MS,
  );
  try {
    const base = new URL(options.backendUrl ?? process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password ||
        base.search || base.hash || !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 ||
        timeoutMs > LAB3_CONVERSATION_TIMEOUT_MS) throw new Error("invalid config");
    target = new URL(`${base.toString().replace(/\/$/, "")}/conversation/runs`);
  } catch {
    return failure(503, "LAB3_PROXY_NOT_CONFIGURED", "Lab 3 conversation proxy is not configured.");
  }

  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), timeoutMs);
  const signal = AbortSignal.any([deadline.signal, request.signal]);
  try {
    if (request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
      return failure(400, "INVALID_CONVERSATION", "A JSON conversation request is required.");
    }
    let body: string;
    try {
      body = await boundedText(request.body, MAX_REQUEST_BYTES, signal);
      JSON.parse(body);
    } catch {
      if (signal.aborted) throw new Error("request aborted");
      return failure(400, "INVALID_CONVERSATION", "The conversation request is invalid or too large.");
    }
    const response = await fetch(target, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body, signal, cache: "no-store", redirect: "error",
    });
    if (!response.ok) {
      const status = [400, 404, 409, 422, 503, 504].includes(response.status) ? response.status : 502;
      try {
        if (response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() === "application/json") {
          const error = safeError(JSON.parse(await boundedText(response.body, MAX_ERROR_BYTES, signal)));
          if (error) return failure(status, error.code, error.message);
        }
      } catch {
        if (signal.aborted) throw new Error("request aborted");
      } finally {
        // Cancellation must not hold an expired request open on an untrusted stream.
        void response.body?.cancel().catch(() => {});
      }
      return failure(status, "LAB3_BACKEND_ERROR", "Lab 3 could not process this conversation request.");
    }
    if (!response.headers.get("content-type")?.toLowerCase().includes("application/json")) {
      await response.body?.cancel();
      throw new Error("invalid response type");
    }
    const payload: unknown = JSON.parse(await boundedText(response.body, MAX_RESPONSE_BYTES, signal));
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("invalid payload");
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return signal.aborted
      ? failure(504, "LAB3_CONVERSATION_TIMEOUT", "Lab 3 conversation timed out. Please try again.")
      : failure(502, "LAB3_BACKEND_UNAVAILABLE", "Lab 3 conversation service is unavailable.");
  } finally {
    clearTimeout(timer);
  }
}
