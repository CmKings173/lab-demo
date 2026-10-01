// Server-only explanation proxy; conversation and SSE retain their existing policy.
export const LAB3_EXPLANATION_TIMEOUT_MS = 75_000;
const MAX_RESPONSE_BYTES = 32 * 1024;
const MAX_EXPLANATION_CHARS = 4000;

function failure(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, {
    status, headers: { "Cache-Control": "no-store" },
  });
}

async function boundedResponse(body: ReadableStream<Uint8Array> | null,
  signal: AbortSignal): Promise<unknown> {
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
      if (length > MAX_RESPONSE_BYTES) {
        cancel();
        throw new Error("body exceeds limit");
      }
      chunks.push(chunk.value);
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
  } finally {
    signal.removeEventListener("abort", cancel);
    reader.releaseLock();
  }
}

export async function proxyLab3Explanation(request: Request, runId: string, options: {
  backendUrl?: string; timeoutMs?: number;
} = {}): Promise<Response> {
  // UUID.hex IDs and existing store identifiers fit this safe, bounded segment.
  // Missing IDs still reach the backend; path/query/fragment injection cannot.
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(runId)) {
    return failure(400, "INVALID_RUN_ID", "The workflow run ID is invalid.");
  }
  let target: URL;
  const timeoutMs = options.timeoutMs ?? Number(
    process.env.LAB3_EXPLANATION_TIMEOUT_MS ?? LAB3_EXPLANATION_TIMEOUT_MS,
  );
  try {
    const base = new URL(options.backendUrl ?? process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password ||
        base.search || base.hash || !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 ||
        timeoutMs > LAB3_EXPLANATION_TIMEOUT_MS) throw new Error("invalid config");
    target = new URL(`${base.toString().replace(/\/$/, "")}/runs/${encodeURIComponent(runId)}/explanation`);
  } catch {
    return failure(503, "LAB3_PROXY_NOT_CONFIGURED", "Lab 3 explanation proxy is not configured.");
  }

  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), timeoutMs);
  const signal = AbortSignal.any([deadline.signal, request.signal]);
  try {
    const response = await fetch(target, {
      method: "POST", headers: { Accept: "application/json" },
      signal, cache: "no-store", credentials: "omit", redirect: "error",
    });
    if (!response.ok) {
      await response.body?.cancel();
      const status = [400, 404, 409, 422, 503, 504].includes(response.status) ? response.status : 502;
      return failure(status, "LAB3_BACKEND_ERROR", "Lab 3 could not explain this workflow run.");
    }
    if (response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
      await response.body?.cancel();
      throw new Error("invalid response type");
    }
    const value = await boundedResponse(response.body, signal);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid payload");
    const payload = value as Record<string, unknown>;
    if (payload.run_id !== runId || (payload.status !== "completed" && payload.status !== "failed") ||
        (payload.final_state !== null && typeof payload.final_state !== "string") ||
        typeof payload.explanation !== "string" || !payload.explanation.trim() ||
        payload.explanation.length > MAX_EXPLANATION_CHARS) throw new Error("invalid explanation");
    return Response.json({
      run_id: payload.run_id, status: payload.status,
      final_state: payload.final_state, explanation: payload.explanation,
    }, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return signal.aborted
      ? failure(504, "LAB3_EXPLANATION_TIMEOUT", "Lab 3 explanation timed out. Please try again.")
      : failure(502, "LAB3_BACKEND_UNAVAILABLE", "Lab 3 explanation service is unavailable.");
  } finally {
    clearTimeout(timer);
  }
}
