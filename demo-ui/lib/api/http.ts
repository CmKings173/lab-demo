export class ApiClientError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null = null) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value);
}

export function isNullableNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

function publicError(payload: unknown): { message: string; code: string | null } | null {
  if (!isRecord(payload) || Object.keys(payload).length !== 1 ||
      !isRecord(payload.error) || !isString(payload.error.message) ||
      Object.keys(payload.error).some((key) => key !== "message" && key !== "code" && key !== "details")) return null;
  const message = payload.error.message.trim();
  const code = payload.error.code ?? null;
  if (!message || payload.error.message.length > 2_000 ||
      (code !== null && (!isString(code) || !/^[A-Z][A-Z0-9_]{0,63}$/.test(code)))) return null;
  return { message, code };
}

export async function parseApiResponse<T>(
  response: Response,
  isPayload: (value: unknown) => value is T,
  fallbackMessage: string,
): Promise<T> {
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = publicError(payload);
    throw new ApiClientError(error?.message ?? `${fallbackMessage} (${response.status})`,
      response.status, error?.code ?? null);
  }
  if (!isPayload(payload)) {
    throw new ApiClientError(`${fallbackMessage}: the response format was invalid.`, response.status);
  }
  return payload;
}
