"""
Note query API endpoints
"""
import logging
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.sessions import get_async_session
from ..dependencies import Dependencies, get_dependencies
from ..metrics import metrics
from ..services.note_query_service import NoteQueryService
from ..types.note import NoteQueryRequest, NoteQueryResponse
from .auth import get_api_token_from_header

logger = logging.getLogger(__name__)

router = APIRouter()


def get_dependencies_with_api_key(
    api_token: str = Depends(get_api_token_from_header),
) -> Dependencies:
    """
    Get dependencies with API key from request header.

    Args:
        api_token: API token extracted from Authorization header

    Returns:
        Dependencies instance with API key from header
    """
    # Get base dependencies (with settings)
    base_deps = get_dependencies()
    # Create new dependencies with API key from header
    return Dependencies(settings=base_deps.settings, api_key=api_token)


def get_db_session(
    dependencies: Dependencies = Depends(get_dependencies_with_api_key),
) -> AsyncSession:
    """Get database session using settings from dependencies."""
    return get_async_session(settings=dependencies.settings)


@router.post("/query", response_model=NoteQueryResponse)
async def query_notes(
    request: NoteQueryRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    dependencies: Dependencies = Depends(get_dependencies_with_api_key),
) -> NoteQueryResponse:
    """Answer a question about notes using semantic search and AI."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    model = "gpt-4"  # Default model - will use LiteLLM proxy model from settings

    try:
        # Create service with dependencies
        note_query_service = NoteQueryService(db, dependencies=dependencies)

        # Query notes with guardrails
        result, metadata = await note_query_service.query_notes(request.query)

        # Set response headers with generation metadata
        for header_name, header_value in metadata.items():
            response.headers[header_name] = str(header_value)
            logger.debug(f"Set response header: {header_name} = {header_value}")

        # Calculate metrics
        duration = time.time() - start_time
        input_tokens = len(request.query.split())  # Rough estimate
        output_tokens = len(result.answer.split()) if result.answer else 0
        cost_usd = (
            input_tokens * 0.00003 + output_tokens * 0.00006
        )  # GPT-4 pricing estimate

        # Use model name from metadata for metrics
        model_name = metadata.get("X-Model-Name", model)

        # Record success metrics
        metrics.workflow_analysis_total.labels(status="success", model=model_name).inc()
        metrics.workflow_analysis_duration.labels(model=model_name).observe(duration)
        metrics.workflow_analysis_input_tokens.labels(model=model_name).observe(input_tokens)
        metrics.workflow_analysis_output_tokens.labels(model=model_name).observe(
            output_tokens
        )
        metrics.workflow_analysis_cost_usd.labels(model=model_name).observe(cost_usd)

        # Record business metrics (reusing existing metric names for now)
        if result.query_answered:
            metrics.workflow_analysis_apps_found.observe(
                1
            )  # Reuse metric for "queries answered"
        if result.relevant_files:
            metrics.workflow_analysis_actions_found.observe(
                len(result.relevant_files)
            )  # Reuse metric for "files found"

        # Add request ID to response if not already set
        if not result.request_id:
            result.request_id = request_id

        return result

    except Exception as e:
        # Record error metrics
        duration = time.time() - start_time
        metrics.workflow_analysis_total.labels(status="error", model=model).inc()
        metrics.workflow_analysis_duration.labels(model=model).observe(duration)

        raise HTTPException(status_code=500, detail=f"Error querying notes: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}
