import { toast } from "sonner";

export type FieldIssue = { field: string; message: string };

/** An API failure: the backend always answers errors with `{error: {code, message, …}}`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Per-field problems of a 422 `validation_error` (field = dotted path, e.g. "email"). */
  readonly details: FieldIssue[];

  constructor(status: number, code: string, message: string, details: FieldIssue[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  static fromBody(status: number, body: unknown): ApiError {
    const error = isRecord(body) && isRecord(body.error) ? body.error : null;
    const code = typeof error?.code === "string" ? error.code : `http_${status}`;
    const message =
      typeof error?.message === "string"
        ? error.message
        : "Something went wrong. Please try again.";
    const details = Array.isArray(error?.details) ? error.details.filter(isFieldIssue) : [];
    return new ApiError(status, code, message, details);
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // empty or non-JSON body (e.g. a proxy error page)
    }
    return ApiError.fromBody(response.status, body);
  }
}

const NETWORK_MESSAGE = "Can't reach the server. Check your connection and try again.";
const RATE_LIMIT_MESSAGE = "You're sending requests too quickly — try again in a minute.";

/** A message that is safe and useful to show the user, for any thrown value. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 429 ? RATE_LIMIT_MESSAGE : error.message;
  }
  if (error instanceof TypeError) return NETWORK_MESSAGE; // fetch() network failure
  return "Something went wrong. Please try again.";
}

export function toastError(error: unknown): void {
  toast.error(errorMessage(error));
}

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/** openapi-fetch result → data, or throw ApiError. `const user = unwrap(await api.GET(...))`. */
export function unwrap<T>(result: FetchResult<T>): T {
  if (result.error !== undefined || !result.response.ok) {
    throw ApiError.fromBody(result.response.status, result.error);
  }
  return result.data as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isFieldIssue(value: unknown): value is FieldIssue {
  return isRecord(value) && typeof value.field === "string" && typeof value.message === "string";
}
