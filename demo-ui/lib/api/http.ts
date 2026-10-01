export class ApiClientError extends Error {
  constructor(message: string, readonly status: number) {
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

function publicErrorMessage(payload: unknown): string | null {
  if (!isRecord(payload) || !isRecord(payload.error) || !isString(payload.error.message)) return null;
  const message = payload.error.message.trim();
  return message ? message.slice(0, 2_000) : null;
}

export async function parseApiResponse<T>(
  response: Response,
  isPayload: (value: unknown) => value is T,
  fallbackMessage: string,
): Promise<T> {
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiClientError(publicErrorMessage(payload) ?? `${fallbackMessage} (${response.status})`, response.status);
  }
  if (!isPayload(payload)) {
    throw new ApiClientError(`${fallbackMessage}: the response format was invalid.`, response.status);
  }
  return payload;
}
