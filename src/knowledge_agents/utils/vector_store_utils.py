"""
Vector store utilities for note embeddings and text processing.
"""
from __future__ import annotations

import base64
import logging
import re
import struct
from typing import TYPE_CHECKING, List, Optional

from openai import OpenAI

if TYPE_CHECKING:
    from ..config.api_config import Settings
    from ..dependencies import Dependencies

logger = logging.getLogger(__name__)


# Token limit for text-embedding-3-small (8191 tokens)
EMBEDDING_TOKEN_LIMIT = 8191

# Rough token estimation: ~1 token per 4 characters for English text
# This is a conservative estimate for OpenAI's tokenizer
CHARS_PER_TOKEN_ESTIMATE = 4


def normalize_text(text: str) -> str:
    """
    Normalize text before embedding: clean whitespace, normalize newlines.

    Args:
        text: Raw text to normalize

    Returns:
        Normalized text with cleaned whitespace
    """
    if not text:
        return ""
    # Normalize whitespace: collapse multiple spaces, strip
    text = re.sub(r"\s+", " ", text)
    # Normalize newlines to spaces
    text = re.sub(r"\n+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.

    Uses a conservative estimate: ~1 token per 4 characters.
    For more accurate counting, use tiktoken library with 'cl100k_base' encoding.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Conservative estimate: ~1 token per 4 characters
    # Actual ratio varies by language and content
    return len(text) // CHARS_PER_TOKEN_ESTIMATE + 1


def validate_token_limit(text: str, max_tokens: int = EMBEDDING_TOKEN_LIMIT) -> None:
    """
    Validate that text doesn't exceed token limit for embedding.

    Args:
        text: Text to validate
        max_tokens: Maximum allowed tokens (default: 8191 for text-embedding-3-small)

    Raises:
        ValueError: If text exceeds token limit
    """
    estimated_tokens = estimate_tokens(text)
    if estimated_tokens > max_tokens:
        raise ValueError(
            f"Text exceeds token limit: {estimated_tokens} tokens (max: {max_tokens}). "
            f"Text length: {len(text)} characters. Consider chunking or shortening the text."
        )


def generate_embeddings(
    texts: List[str],
    dependencies: Optional["Dependencies"] = None,
    openai_client: Optional[OpenAI] = None,
    settings: Optional["Settings"] = None,
    batch_size: int = 100,
    embedding_model: Optional[str] = None,
) -> List[List[float]]:
    """
    Generate embeddings for texts in batches using LiteLLM proxy.

    Args:
        texts: List of text strings to embed
        dependencies: Dependencies container (optional, used if openai_client and settings not provided)
        openai_client: OpenAI client instance (optional, will use proxy client from dependencies if not provided)
        settings: Settings instance (optional, used if embedding_model not provided)
        batch_size: Number of texts to process per batch (default: 100)
        embedding_model: Optional embedding model name. If None, uses proxy config default from settings.

    Returns:
        List of embedding vectors (each vector is a list of floats)

    Raises:
        ValueError: If neither dependencies nor (openai_client and settings) are provided
        Exception: If embedding generation fails for any batch
    """
    # Determine which client and settings to use
    if dependencies:
        # Use dependencies - get client and settings from there
        if openai_client is None:
            openai_client = dependencies.proxy_client_manager.get_client()
            # Verify we got a sync client, not async
            from openai import AsyncOpenAI
            if isinstance(openai_client, AsyncOpenAI):
                raise ValueError(
                    "Expected synchronous OpenAI client, but got AsyncOpenAI. "
                    "Use proxy_client_manager.get_client() not get_async_client()"
                )
        if settings is None:
            settings = dependencies.settings
    elif openai_client and settings:
        # Use provided client and settings
        pass
    else:
        raise ValueError(
            "Either 'dependencies' must be provided, or both 'openai_client' and 'settings' must be provided."
        )

    # Verify client is using proxy base_url
    if hasattr(openai_client, "base_url"):
        logger.debug(f"Using client with base_url: {openai_client.base_url}")

    # Determine if client is using proxy by checking base_url
    is_proxy_client = False
    if openai_client and hasattr(openai_client, "base_url") and openai_client.base_url:
        base_url_str = str(openai_client.base_url)
        # Check if base_url points to proxy (llm-proxy or port 4000)
        if "llm-proxy" in base_url_str or ":4000" in base_url_str:
            is_proxy_client = True
            logger.debug(f"Detected proxy client: {base_url_str}")

    # Use appropriate embedding model based on client type
    if embedding_model:
        # User explicitly specified a model, use it
        model = embedding_model
    elif is_proxy_client:
        # Client is using proxy, use proxy embedding model from settings
        model = settings.litellm_proxy_embedding_model
        logger.info(f"Using proxy embedding model from settings: {model}")
    else:
        # Client is not using proxy, use OpenAI embedding model (backward compatibility)
        model = settings.openai_embedding_model
        logger.info(f"Using OpenAI embedding model: {model}")

    all_embeddings = []
    total_batches = (len(texts) - 1) // batch_size + 1

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(
            f"Generating embeddings for batch {batch_num}/{total_batches} "
            f"({len(batch)} texts) using model: {model}"
        )

        try:
            # For proxy clients (LM Studio), don't pass encoding_format parameter at all
            # LM Studio doesn't support encoding_format parameter (neither 'base64' nor 'float')
            embedding_kwargs = {
                "input": batch,
                "model": model,
            }
            # Only add encoding_format for non-proxy clients (OpenAI API supports it)
            if not is_proxy_client:
                # OpenAI API supports encoding_format, default to 'float' if not specified
                pass  # Let OpenAI SDK use its default

            logger.debug(f"Calling embeddings.create with {len(batch)} texts")
            result = openai_client.embeddings.create(**embedding_kwargs)
            logger.debug(f"Got result type: {type(result)}")

            # Extract embeddings and ensure they're in the correct format (list of floats)
            batch_embeddings = []
            # Access result.data - should be a list for sync OpenAI client
            # Store it in a variable first to avoid any property access issues
            try:
                # Get the data attribute directly
                data_attr = getattr(result, 'data', None)
                if data_attr is None:
                    raise ValueError("result.data is None - embeddings.create() returned invalid response")
                
                logger.debug(f"result.data type: {type(data_attr)}")
                
                # Check if it's awaitable (shouldn't be for sync client)
                if hasattr(data_attr, '__await__'):
                    raise ValueError(
                        f"result.data is awaitable (async), but using sync client. "
                        f"Type: {type(data_attr)}. This suggests the client is async."
                    )
                
                # Convert to list explicitly to avoid any iteration issues
                if isinstance(data_attr, list):
                    data_list = data_attr
                else:
                    # Try to convert if it's iterable
                    try:
                        data_list = list(data_attr)
                    except (TypeError, ValueError) as e:
                        logger.error(f"Could not convert result.data to list: {e}, type: {type(data_attr)}")
                        raise ValueError(f"result.data is not a list or iterable: {type(data_attr)}")
                
            except AttributeError as e:
                logger.error(f"Error accessing result.data attribute: {e}")
                raise ValueError(f"result object missing 'data' attribute: {type(result)}")
            except Exception as e:
                logger.error(f"Unexpected error accessing result.data: {e}")
                raise
            
            # Now iterate over the list
            for data in data_list:
                embedding = data.embedding
                # Ensure embedding is a list of floats (not base64 string)
                if isinstance(embedding, str):
                    # If somehow we got a base64 string, decode it
                    try:
                        decoded_bytes = base64.b64decode(embedding)
                        embedding = list(
                            struct.unpack(f"{len(decoded_bytes)//4}f", decoded_bytes)
                        )
                        logger.warning(
                            "Received base64 embedding, decoded to float array"
                        )
                    except Exception as e:
                        logger.error(f"Failed to decode base64 embedding: {e}")
                        raise
                elif not isinstance(embedding, list):
                    logger.error(f"Unexpected embedding format: {type(embedding)}")
                    raise ValueError(f"Expected list of floats, got {type(embedding)}")
                batch_embeddings.append(embedding)

            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Error generating embeddings for batch {batch_num}: {e}")
            raise

    return all_embeddings
