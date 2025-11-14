"""
Response schemas for API responses
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class GuardrailType(Enum):
    """Enum for guardrail type names"""

    # Input guardrails
    DESCRIBES_NOTE_QUERY = "describes_note_query"

    # Output guardrails
    JUDGES_NOTE_ANSWER = "judges_note_answer"


class HealthCheckResponse(BaseModel):
    """Response schema for health check"""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Check timestamp"
    )
    database_status: Optional[str] = Field(
        None, description="Database connectivity status"
    )
    llm_status: Optional[str] = Field(None, description="LLM connectivity status")


class MetricsResponse(BaseModel):
    """Response schema for metrics"""

    total_requests: int = Field(..., description="Total number of requests")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0-1)")
    average_response_time: float = Field(
        ..., ge=0.0, description="Average response time in ms"
    )
    total_cost: float = Field(..., ge=0.0, description="Total cost in USD")
    most_used_model: str = Field(..., description="Most used model")


class ErrorResponse(BaseModel):
    """Response schema for errors"""

    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )
