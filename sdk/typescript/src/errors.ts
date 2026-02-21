/** Base API error. */
export class OCCPAPIError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(`[${status}] ${message}`);
    this.name = "OCCPAPIError";
  }
}

/** 401/403 authentication failure. */
export class AuthenticationError extends OCCPAPIError {
  constructor(message = "Authentication failed") {
    super(401, message);
    this.name = "AuthenticationError";
  }
}

/** 404 resource not found. */
export class NotFoundError extends OCCPAPIError {
  constructor(resource: string) {
    super(404, `Resource not found: ${resource}`);
    this.name = "NotFoundError";
  }
}

/** 429 rate limit exceeded. */
export class RateLimitError extends OCCPAPIError {
  public readonly retryAfter: number;

  constructor(retryAfter = 60) {
    super(429, `Rate limited. Retry after ${retryAfter}s`);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}
