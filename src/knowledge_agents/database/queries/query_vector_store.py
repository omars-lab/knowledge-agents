"""
Semantic search queries using Qdrant vector store.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from openai import OpenAI

if TYPE_CHECKING:
    from ...config.api_config import Settings
    from ...dependencies import Dependencies

logger = logging.getLogger(__name__)


class VectorStoreQueries:
    """
    Semantic search queries for NotePlan files using vector store.

    Uses explicit dependency injection - Dependencies must be provided at initialization.
    """

    def __init__(
        self,
        dependencies: "Dependencies",
        openai_client: Optional[OpenAI] = None,
    ):
        """
        Initialize vector store queries.

        Args:
            dependencies: Dependencies container (required)
            openai_client: OpenAI client for generating embeddings (optional, uses proxy from dependencies if None)
        """
        self.dependencies = dependencies
        self.settings = dependencies.settings

        # Use proxy client from dependencies if not provided
        if openai_client is None:
            self.openai_client = dependencies.proxy_client_manager.get_client()
            logger.info("Using proxy client for embeddings in VectorStoreQueries")
        else:
            self.openai_client = openai_client

        # Get vector store client from dependencies
        self.vector_store_client = dependencies.vector_store_client_manager.get_client()

    def query_files_semantically(
        self,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Query NotePlan files semantically using vector search.

        Args:
            query: Natural language query describing the desired content
            collection_name: Qdrant collection name (defaults to config value)
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score (0-1), results below this are filtered out

        Returns:
            List of dictionaries with keys: file_path, file_name, modified_at, file_size, similarity_score
            Results are ordered by similarity (highest first)
        """
        # Return empty results for empty or whitespace-only queries
        if not query or not query.strip():
            return []

        collection_name = collection_name or self.settings.qdrant_collection_name

        # Log collection name being used for debugging
        logger.debug(f"Querying semantic search on collection: '{collection_name}'")

        # Generate embedding for the query
        # Use proxy embedding model if using proxy client
        # Check if client is using proxy by checking base_url attribute
        is_proxy_client = False
        if hasattr(self.openai_client, "base_url") and self.openai_client.base_url:
            base_url_str = str(self.openai_client.base_url)
            if "llm-proxy" in base_url_str or "4000" in base_url_str:
                is_proxy_client = True

        if is_proxy_client:
            embedding_model = self.settings.litellm_proxy_embedding_model
            logger.debug(f"Using proxy embedding model: {embedding_model}")
        else:
            embedding_model = self.settings.openai_embedding_model
            logger.debug(f"Using OpenAI embedding model: {embedding_model}")

        # For proxy clients (LM Studio), don't pass encoding_format parameter at all
        # LM Studio doesn't support encoding_format parameter (neither 'base64' nor 'float')
        embedding_kwargs = {
            "input": [query],
            "model": embedding_model,
        }
        # Only add encoding_format for non-proxy clients (OpenAI API supports it)
        # For proxy clients, omit encoding_format entirely

        embedding_result = self.openai_client.embeddings.create(**embedding_kwargs)
        query_vector = embedding_result.data[0].embedding

        # Search in vector store
        search_results = self.vector_store_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        # Extract and return file metadata with scores
        results = []
        for result in search_results:
            try:
                payload = result.payload
                # Qdrant returns score (higher is better), convert to similarity (0-1 range)
                # Score is already in similarity range for COSINE distance
                similarity_score = float(result.score)

                file_result = {
                    "file_path": payload.get("file_path", ""),
                    "file_name": payload.get("file_name", ""),
                    "modified_at": payload.get("modified_at", ""),
                    "file_size": payload.get("file_size", 0),
                    "similarity_score": similarity_score,
                }
                results.append(file_result)
            except (ValueError, KeyError) as e:
                # Skip results that can't be parsed
                continue

        # Log semantic search results for debugging
        logger.info(
            f"Semantic search for query '{query[:50]}...' returned {len(results)} results:"
        )
        for idx, result in enumerate(results, 1):
            logger.info(
                f"  {idx}. File: {result['file_name']}, Path: {result['file_path']}, "
                f"Score: {result['similarity_score']:.4f}"
            )

        return results

    def query_tools_semantically(
        self,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[tuple]:
        """
        [DEPRECATED] Query app/action pairs semantically using vector search.

        This method is deprecated and maintained for backward compatibility.
        Use query_files_semantically() instead for NotePlan file search.

        Returns:
            List of tuples: (app_name, action_name, similarity_score) for backward compatibility
        """
        # For backward compatibility, return empty results
        # The vector store now stores NotePlan files, not app/action pairs
        logger.warning(
            "query_tools_semantically() is deprecated. "
            "Vector store now stores NotePlan files. Use query_files_semantically() instead."
        )
        return []
