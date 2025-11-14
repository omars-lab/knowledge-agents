#!/usr/bin/env python3
"""
Call LiteLLM Model via Proxy

PURPOSE: Make completion and embedding calls via the LiteLLM proxy server
SCOPE: Connect to proxy server and make requests to configured models

This script:
- Connects to the LiteLLM proxy server
- Makes completion calls using the specified model
- Makes embedding calls using embedding models
"""

import argparse
import json
import logging
import os
import sys

# Add src to path for imports
src_path = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, os.path.abspath(src_path))

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests")
    sys.exit(1)

# Configure logging using centralized config (must be before imports that use logger)
from knowledge_agents.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Try to import from knowledge_agents, fall back to standalone logic if not available
try:
    from knowledge_agents.config.model_config import get_model_config, list_models
    from knowledge_agents.config.secrets_config import get_openai_api_key

    USE_SHARED_SECRETS = True
except ImportError as e:
    logger.warning(f"Could not import from knowledge_agents: {e}")
    logger.warning("Using standalone secret loading logic")
    USE_SHARED_SECRETS = False

    # Fallback: create minimal model_config functions
    def get_model_config(model: str) -> dict:
        """Fallback model config."""
        return {
            "description": "Model configuration",
            "use_when": "When needed",
            "best_for": "General use",
        }

    def list_models() -> dict:
        """Fallback model list."""
        return {}


# Ensure logs are flushed immediately
sys.stdout.reconfigure(line_buffering=True) if hasattr(
    sys.stdout, "reconfigure"
) else None

# Default proxy configuration
# When running from host via make, use localhost (proxy is exposed on host port 4000)
# When running in Docker, use service name llm-proxy
# Detect if we're in Docker by checking if we're in a container
_in_docker = (
    os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER") == "true"
)
DEFAULT_PROXY_HOST = os.getenv("LITELLM_PROXY_HOST") or (
    "llm-proxy" if _in_docker else "localhost"
)
DEFAULT_PROXY_PORT = int(os.getenv("LITELLM_PROXY_PORT", "4000"))


def get_proxy_url() -> str:
    """
    Get the proxy server URL.

    Returns:
        Proxy server base URL
    """
    host = os.getenv("LITELLM_PROXY_HOST", DEFAULT_PROXY_HOST)
    port = os.getenv("LITELLM_PROXY_PORT", DEFAULT_PROXY_PORT)
    return f"http://{host}:{port}"


def get_api_key() -> str:
    """
    Get the API key using shared secrets configuration or fallback logic.

    Returns:
        API key string, or empty string if not found
    """
    if USE_SHARED_SECRETS:
        # Use shared secrets configuration
        from pathlib import Path

        # Get base directory (project root)
        base_dir = Path(__file__).parent.parent

        # Use shared secrets configuration
        api_key = get_openai_api_key(
            base_dir=base_dir,
            required=False,
            allow_test_key=False,
            environment=os.getenv("ENVIRONMENT", "development"),
        )

        return api_key or ""
    else:
        # Fallback: standalone secret loading logic
        # Read from Docker secrets or local files only (no env var dependencies)
        # Try reading from secret files
        from pathlib import Path

        base_dir = Path(__file__).parent.parent

        secret_paths = [
            Path("/run/secrets/openai_api_key"),  # Docker secret mount
            base_dir / "secrets" / "openai_api_key.txt",  # Local secrets directory
            base_dir / "config" / "openai_api_key.txt",  # Config directory (fallback)
        ]

        for secret_path in secret_paths:
            if secret_path.exists():
                try:
                    with open(secret_path, "r") as f:
                        key = f.read().strip()
                        if key:
                            logger.debug(f"✅ Loaded API key from {secret_path}")
                            return key
                except Exception as e:
                    logger.debug(f"⚠️  Could not read API key from {secret_path}: {e}")
                    continue

        logger.warning(
            "⚠️  No API key found - requests may fail if proxy requires authentication"
        )
        return ""


def make_completion(
    model: str, messages: list, proxy_url: str = None, **kwargs
) -> dict:
    """
    Make a completion call via the LiteLLM proxy.

    Args:
        model: Model identifier (e.g., "lm_studio/qwen3-coder-30b")
        messages: List of message dictionaries with "role" and "content"
        proxy_url: Proxy server URL (defaults to environment/default)
        **kwargs: Additional arguments (temperature, max_tokens, etc.)

    Returns:
        Response from proxy server
    """
    if proxy_url is None:
        proxy_url = get_proxy_url()

    # Get the model configuration to validate
    model_config = get_model_config(model)

    logger.info(f"🤖 Using model: {model} ({model_config['description']})")
    logger.info(f"📡 Proxy: {proxy_url}")
    logger.info(f"📝 Making completion request...")

    # Prepare request payload
    payload = {
        "model": model,
        "messages": messages,
    }
    payload.update(kwargs)

    # Prepare headers with API key if available
    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Make the request
    response = requests.post(
        f"{proxy_url}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=300.0,
    )

    response.raise_for_status()
    return response.json()


def make_embedding(
    model: str, input_text: str, proxy_url: str = None, **kwargs
) -> dict:
    """
    Make an embedding call via the LiteLLM proxy.

    Args:
        model: Model identifier (should be an embedding model)
        input_text: Text to generate embedding for
        proxy_url: Proxy server URL (defaults to environment/default)
        **kwargs: Additional arguments

    Returns:
        Response from proxy server
    """
    if proxy_url is None:
        proxy_url = get_proxy_url()

    # Get the model configuration to validate
    model_config = get_model_config(model)

    logger.info(f"🤖 Using embedding model: {model} ({model_config['description']})")
    logger.info(f"📡 Proxy: {proxy_url}")
    logger.info(f"📝 Generating embedding...")

    # Prepare request payload
    payload = {
        "model": model,
        "input": input_text,
    }
    payload.update(kwargs)

    # Prepare headers with API key if available
    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Make the request
    response = requests.post(
        f"{proxy_url}/v1/embeddings",
        json=payload,
        headers=headers,
        timeout=300.0,
    )

    response.raise_for_status()
    return response.json()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Call LiteLLM models via proxy server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Chat completion with default model
  python scripts/call_litellm_model.py --prompt "What's the weather like?"

  # Chat completion with specific model
  python scripts/call_litellm_model.py --model lm_studio/qwen3-coder-30b --prompt "Write a Python function"

  # Embedding generation
  python scripts/call_litellm_model.py --model text-embedding-qwen3-embedding-8b --embedding "Hello world"

  # Custom proxy host/port
  python scripts/call_litellm_model.py --proxy-host localhost --proxy-port 4000 --prompt "Hello"

  # List available models
  python scripts/call_litellm_model.py --list-models
        """,
    )

    parser.add_argument(
        "--proxy-host",
        type=str,
        default=os.getenv("LITELLM_PROXY_HOST", DEFAULT_PROXY_HOST),
        help=f"Proxy server host (default: {DEFAULT_PROXY_HOST}, or LITELLM_PROXY_HOST env var)",
    )

    parser.add_argument(
        "--proxy-port",
        type=int,
        default=int(os.getenv("LITELLM_PROXY_PORT", DEFAULT_PROXY_PORT)),
        help=f"Proxy server port (default: {DEFAULT_PROXY_PORT}, or LITELLM_PROXY_PORT env var)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-oss-20b",
        help="Model to use (default: openai/gpt-oss-20b)",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        help="Prompt text for chat completion",
    )

    parser.add_argument(
        "--embedding",
        type=str,
        help="Text to generate embedding for",
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all available models and exit",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Temperature for completion (0.0-2.0)",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum tokens to generate",
    )

    args = parser.parse_args()

    # List models if requested
    if args.list_models:
        print("\n📋 Available Models:\n")
        models = list_models()
        for model_id, model_info in models.items():
            print(f"  {model_id}")
            print(f"    Description: {model_info['description']}")
            print(f"    Type: {model_info.get('model_type', 'unknown')}")
            print(f"    Use when: {model_info['use_when']}")
            print(f"    Best for: {model_info['best_for']}\n")
        sys.exit(0)

    # Validate arguments
    if not args.prompt and not args.embedding:
        parser.error("Either --prompt or --embedding must be provided")

    if args.prompt and args.embedding:
        parser.error("Cannot use both --prompt and --embedding at the same time")

    try:
        # Build proxy URL
        proxy_url = f"http://{args.proxy_host}:{args.proxy_port}"

        # Prepare kwargs
        kwargs = {}
        if args.temperature is not None:
            kwargs["temperature"] = args.temperature
        if args.max_tokens is not None:
            kwargs["max_tokens"] = args.max_tokens

        # Make the request
        if args.embedding:
            # Embedding request
            response = make_embedding(
                model=args.model,
                input_text=args.embedding,
                proxy_url=proxy_url,
                **kwargs,
            )
            print("\n✅ Embedding Response:")
            print(json.dumps(response, indent=2))
        else:
            # Chat completion request
            messages = [
                {
                    "role": "user",
                    "content": args.prompt,
                }
            ]
            response = make_completion(
                model=args.model, messages=messages, proxy_url=proxy_url, **kwargs
            )
            print("\n✅ Completion Response:")
            print(json.dumps(response, indent=2))

            # Extract and print the content if available
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                if "message" in choice:
                    content = choice["message"].get("content", "")
                    print(f"\n📄 Response Content:\n{content}")
                elif "text" in choice:
                    content = choice["text"]
                    print(f"\n📄 Response Content:\n{content}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
