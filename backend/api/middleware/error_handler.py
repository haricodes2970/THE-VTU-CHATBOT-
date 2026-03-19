"""
backend/api/middleware/error_handler.py
Global exception handler — returns consistent JSON error format.
"""
import traceback
from datetime import datetime

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from loguru import logger


def _error_body(status_code: int, error: str, message: str, detail: str = "") -> dict:
    return {
        "error": error,
        "message": message,
        "detail": detail,
        "status_code": status_code,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.status_code, "HTTPException", str(exc.detail)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "; ".join(
        f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors
    )
    return JSONResponse(
        status_code=422,
        content=_error_body(422, "ValidationError", "Request validation failed", message),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content=_error_body(500, "InternalServerError", "An unexpected error occurred"),
    )
