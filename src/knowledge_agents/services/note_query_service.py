"""
Note query service for answering questions about notes.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.note_query_agent import run_note_query_agent
from ..types.note import NoteQueryResponse
from ..utils.exception_handlers import ServiceExceptionHandler

if TYPE_CHECKING:
    from ..dependencies import Dependencies

logger = logging.getLogger(__name__)


class NoteQueryService:
    """
    Service for querying and answering questions about notes.

    Uses explicit dependency injection - Dependencies must be provided at initialization.
    """

    def __init__(self, database_session: AsyncSession, dependencies: "Dependencies"):
        """
        Initialize the note query service.

        Args:
            database_session: Database session for queries
            dependencies: Dependencies container (required)
        """
        self.database_session = database_session
        self.dependencies = dependencies

    async def query_notes(self, query: str) -> tuple[NoteQueryResponse, dict[str, str]]:
        """
        Answer a question about notes using semantic search and AI.
        
        Returns:
            Tuple of (NoteQueryResponse, metadata_dict) where metadata contains
            generation information for response headers.
        """
        logger.info(f"Starting note query for: {query[:100]}...")

        try:
            # Run note query agent with integrated guardrails
            result, metadata = await run_note_query_agent(query, dependencies=self.dependencies)

            return result, metadata

        except Exception as e:
            logger.error(f"Error in note query: {str(e)}", exc_info=True)
            # Use centralized exception handler
            response = ServiceExceptionHandler.handle_service_exception(
                exception=e,
                response_type=NoteQueryResponse,
                log_prefix="Note query service",
            )
            # Return default metadata on error
            metadata = {
                "X-Model-Name": "unknown",
                "X-API-Type": "unknown",
                "X-Generation-Time-Seconds": "0.000",
                "X-Model-Class": "unknown",
            }
            return response, metadata
