from typing import Any


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def bad_request(message: str, details: Any = None) -> AppError:
    return AppError(400, "BAD_REQUEST", message, details)


def unauthorized(message: str = "Authentication is required") -> AppError:
    return AppError(401, "UNAUTHORIZED", message)


def forbidden(message: str = "You do not have permission to perform this action") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def not_found(message: str = "Resource not found") -> AppError:
    return AppError(404, "NOT_FOUND", message)


def conflict(message: str) -> AppError:
    return AppError(409, "CONFLICT", message)
