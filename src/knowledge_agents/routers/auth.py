"""
Authentication utilities for API endpoints.

This module provides functions to extract API tokens from request headers.
"""
import logging
from typing import Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


def get_api_token_from_header(
    authorization: Optional[str] = Header(None, description="Bearer token for API authentication")
) -> str:
    """
    Extract API token from Authorization header.

    Expected format: "Bearer <token>"

    Args:
        authorization: Authorization header value

    Returns:
        API token string

    Raises:
        HTTPException: If authorization header is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required. Use 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Extracted API token from header (first 10 chars: {token[:10]}...)")
    return token

