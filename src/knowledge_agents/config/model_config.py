"""
Model configuration for LM Studio, LiteLLM, and OpenAI Responses API.

This module defines all available models and their configurations. Models are categorized by type:
- "completion": ChatCompletions API models (via LiteLLM proxy)
- "embedding": Embedding models (via LiteLLM proxy)
- "responses": Responses API models (OpenAI native, supports HostedMCPTool)

See MODEL_ONBOARDING.md for instructions on adding new models.
"""

from typing import Any, Dict

# Available models with descriptions
AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {
    # ============================================================================
    # COMPLETION MODELS (ChatCompletions API via LiteLLM Proxy)
    # ============================================================================
    "lm_studio/qwen3-coder-30b": {
        "litellm_model": "lm_studio/qwen/qwen3-coder-30b",
        "description": "Qwen3 Coder 30B - Specialized coding model",
        "use_when": "Code generation, code completion, debugging, refactoring, code explanation",
        "best_for": "Programming tasks, code reviews, technical documentation",
        "model_type": "completion",
        "api_type": "chat_completions",  # Uses ChatCompletions API via LiteLLM proxy
        "requires_responses_api": False,
    },
    # ============================================================================
    # EMBEDDING MODELS (via LiteLLM Proxy)
    # ============================================================================
    "text-embedding-nomic-embed-text-v1.5": {
        "litellm_model": "text-embedding-nomic-embed-text-v1.5",
        "description": "Nomic Embed Text v1.5 - Embedding model",
        "use_when": "Generating embeddings for semantic search, similarity matching, clustering",
        "best_for": "Vector databases, RAG systems, document similarity, search functionality",
        "model_type": "embedding",
        "api_type": "embeddings",
        "requires_responses_api": False,
    },
    "text-embedding-qwen3-embedding-8b": {
        "litellm_model": "text-embedding-qwen3-embedding-8b",
        "description": "Qwen3 Embedding 8B - Qwen-based embedding model",
        "use_when": "Generating embeddings for semantic search, similarity matching, clustering",
        "best_for": "Vector databases, RAG systems, document similarity, multilingual embeddings",
        "model_type": "embedding",
        "api_type": "embeddings",
        "requires_responses_api": False,
    },
    "lm_studio/text-embedding-qwen3-embedding-8b": {
        "litellm_model": "lm_studio/text-embedding-qwen3-embedding-8b",
        "description": "Qwen3 Embedding 8B - Qwen-based embedding model (via LM Studio)",
        "use_when": "Generating embeddings for semantic search, similarity matching, clustering",
        "best_for": "Vector databases, RAG systems, document similarity, multilingual embeddings",
        "model_type": "embedding",
        "api_type": "embeddings",
        "requires_responses_api": False,
    },
    # ============================================================================
    # RESPONSES API MODELS (OpenAI Native - Supports HostedMCPTool)
    # ============================================================================
    "lm_studio/gpt-oss-20b": {
        "litellm_model": "lm_studio/openai/gpt-oss-20b",
        "description": "GPT-OSS 20B - General purpose open-source model",
        "use_when": "General conversations, text generation, question answering, content creation",
        "best_for": "Chat applications, text completion, general AI tasks",
        "model_type": "responses",
        "api_type": "responses",
        "requires_responses_api": True,
    },
    # ============================================================================
    # LM STUDIO GPT MODELS (Treated as Responses API models)
    # ============================================================================
    # Note: Models starting with "lm_studio/gpt" are treated as responses models
    # because they may benefit from Responses API features. This is handled
    # automatically by is_responses_model() function.
}



def get_model_config(model_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific model.

    Args:
        model_name: Name of the model

    Returns:
        Model configuration dictionary

    Raises:
        ValueError: If model not found
    """
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(
            f"Unknown model: {model_name}. Available models: {list(AVAILABLE_MODELS.keys())}"
        )
    return AVAILABLE_MODELS[model_name]


def list_models() -> Dict[str, Dict[str, Any]]:
    """
    Get all available models.

    Returns:
        Dictionary of all available models
    """
    return AVAILABLE_MODELS.copy()


def get_completion_models() -> Dict[str, Dict[str, Any]]:
    """
    Get all completion models.

    Returns:
        Dictionary of completion models
    """
    return {
        name: config
        for name, config in AVAILABLE_MODELS.items()
        if config.get("model_type") == "completion"
    }


def get_embedding_models() -> Dict[str, Dict[str, Any]]:
    """
    Get all embedding models.

    Returns:
        Dictionary of embedding models
    """
    return {
        name: config
        for name, config in AVAILABLE_MODELS.items()
        if config.get("model_type") == "embedding"
    }


def get_responses_models() -> Dict[str, Dict[str, Any]]:
    """
    Get all Responses API models.

    Returns:
        Dictionary of Responses API models
    """
    return {
        name: config
        for name, config in AVAILABLE_MODELS.items()
        if config.get("model_type") == "responses"
    }


def is_responses_model(model_name: str) -> bool:
    """
    Check if a model requires Responses API.

    This function checks:
    1. Explicit "requires_responses_api": True in model config
    2. Model type is "responses"
    3. Model name starts with "lm_studio/gpt" (treated as responses model)

    Args:
        model_name: Name of the model to check

    Returns:
        True if model requires Responses API, False otherwise
    """
    # Check if model is in config and explicitly requires responses API
    if model_name in AVAILABLE_MODELS:
        config = AVAILABLE_MODELS[model_name]
        if config.get("requires_responses_api") is True:
            return True
        if config.get("model_type") == "responses":
            return True

    # Treat lm_studio/gpt* models as responses models
    if model_name.startswith("lm_studio/gpt"):
        return True

    return False
