"""Unified error handling for the HueFit API.

Every error the frontend ever sees has the same JSON shape:

    {
      "success": false,
      "error": { "code": "INVALID_INPUT", "message": "Occasion is required" }
    }

Raise ApiError anywhere in a route/service and the registered handler
converts it to this shape automatically.
"""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Application error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    # Convenience constructors â€” keeps codes consistent across the codebase.
    @classmethod
    def invalid_input(cls, message: str = "Invalid input") -> "ApiError":
        return cls("INVALID_INPUT", message, 400)

    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> "ApiError":
        return cls("UNAUTHORIZED", message, 401)

    @classmethod
    def forbidden(cls, message: str = "You do not have access to this resource") -> "ApiError":
        return cls("FORBIDDEN", message, 403)

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "ApiError":
        return cls("NOT_FOUND", message, 404)

    @classmethod
    def rate_limited(cls, message: str = "Too many requests, slow down") -> "ApiError":
        return cls("RATE_LIMITED", message, 429)

    @classmethod
    def ai_unavailable(cls, message: str = "AI service is temporarily unavailable") -> "ApiError":
        return cls("AI_UNAVAILABLE", message, 502)


def error_response(code: str, message: str, status: int):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.code, err.message, err.status)

    @app.errorhandler(404)
    def handle_404(_):
        return error_response("NOT_FOUND", "Endpoint not found", 404)

    @app.errorhandler(405)
    def handle_405(_):
        return error_response("METHOD_NOT_ALLOWED", "Method not allowed on this endpoint", 405)

    @app.errorhandler(413)
    def handle_413(_):
        return error_response("FILE_TOO_LARGE", "Uploaded file exceeds the size limit", 413)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return error_response("HTTP_ERROR", err.description or "HTTP error", err.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # Never leak stack traces or internals to the public API.
        app.logger.exception("Unhandled error: %s", err)
        return error_response("SERVER_ERROR", "Something went wrong on our side", 500)
