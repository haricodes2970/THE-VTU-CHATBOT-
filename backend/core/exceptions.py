"""
backend/core/exceptions.py
Custom exception hierarchy for the VTU Smart Scheduler.
"""
from fastapi import HTTPException


class VTUException(HTTPException):
    """Base exception for all VTU app errors."""
    status_code: int = 500
    error: str = "VTUError"

    def __init__(self, message: str, detail: str = ""):
        super().__init__(status_code=self.status_code, detail=message)
        self.message = message
        self.detail_str = detail


class CircularNotFoundError(VTUException):
    status_code = 404
    error = "CircularNotFound"

    def __init__(self, circular_id: int):
        super().__init__(f"Circular {circular_id} not found")


class UserNotFoundError(VTUException):
    status_code = 404
    error = "UserNotFound"

    def __init__(self, identifier: str):
        super().__init__(f"User '{identifier}' not found")


class ScrapingError(VTUException):
    status_code = 502
    error = "ScrapingError"


class EmbeddingError(VTUException):
    status_code = 500
    error = "EmbeddingError"


class LLMError(VTUException):
    status_code = 503
    error = "LLMError"


class DatabaseError(VTUException):
    status_code = 500
    error = "DatabaseError"
