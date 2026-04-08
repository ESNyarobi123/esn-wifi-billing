"""Domain and HTTP-friendly exceptions."""


class AppError(Exception):
    def __init__(self, message: str, code: str | None = None, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code or "error"
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="conflict", status_code=409)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="forbidden", status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="unauthorized", status_code=401)


class ValidationAppError(AppError):
    def __init__(self, message: str, errors: dict | None = None):
        super().__init__(message, code="validation_error", status_code=422)
        self.errors = errors or {}


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, code="rate_limit_exceeded", status_code=429)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, code="service_unavailable", status_code=503)
