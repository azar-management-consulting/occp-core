"""SDK exception hierarchy."""

from __future__ import annotations


class OCCPAPIError(Exception):
    """Base error for OCCP API interactions."""

    def __init__(self, status: int, message: str, detail: str = "") -> None:
        self.status = status
        self.message = message
        self.detail = detail
        super().__init__(f"[{status}] {message}")


class AuthenticationError(OCCPAPIError):
    """Raised on 401/403 responses."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(401, message)


class NotFoundError(OCCPAPIError):
    """Raised on 404 responses."""

    def __init__(self, resource: str) -> None:
        super().__init__(404, f"Resource not found: {resource}")


class RateLimitError(OCCPAPIError):
    """Raised on 429 responses."""

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(429, f"Rate limited. Retry after {retry_after}s")


class ValidationError(OCCPAPIError):
    """Raised on 422 responses."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(422, f"Validation errors: {'; '.join(errors)}")
