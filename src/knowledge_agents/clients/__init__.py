"""
Client modules for external services

Note: Global get_*_client() functions are deprecated.
Use Dependencies container for dependency injection instead.
"""
# Import classes for use with Dependencies container
from .openai import OpenAIClientManager
from .proxy_client import ProxyClientManager
from .vector_store import VectorStoreClientManager

__all__ = [
    "OpenAIClientManager",
    "ProxyClientManager",
    "VectorStoreClientManager",
]
