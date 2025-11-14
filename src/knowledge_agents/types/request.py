"""
Request schemas for API validation
"""

from pydantic import BaseModel, Field, field_validator


class HealthCheckRequest(BaseModel):
    """Request schema for health check"""

    check_database: bool = Field(
        default=False, description="Whether to check database connectivity"
    )
    check_llm: bool = Field(
        default=False, description="Whether to check LLM connectivity"
    )
