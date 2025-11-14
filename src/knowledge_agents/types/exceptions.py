"""Basic exceptions for infrastructure."""

from typing import Any, Dict, Optional


class BaseInfrastructureError(Exception):
    """Base exception for infrastructure errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(BaseInfrastructureError):
    """Database-related errors."""


class ConfigurationError(BaseInfrastructureError):
    """Configuration-related errors."""
