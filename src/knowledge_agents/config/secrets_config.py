"""Secrets configuration management.

This module provides utilities for reading secrets from various sources:
- Docker secret mounts (/run/secrets/)
- Local files (secrets/ directory)
- Environment variables
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_secret_paths(secret_name: str, base_dir: Optional[Path] = None) -> List[Path]:
    """
    Get list of potential paths for a secret, in order of preference.

    Args:
        secret_name: Name of the secret (e.g., "openai_api_key")
        base_dir: Base directory for local paths (defaults to project root)

    Returns:
        List of paths to check, in order of preference
    """
    if base_dir is None:
        # Try to find project root (assumes this file is in src/knowledge_agents/config/)
        current_file = Path(__file__)
        # Go up from: src/knowledge_agents/config/secrets_config.py
        # To: project root
        base_dir = current_file.parent.parent.parent.parent

    paths = [
        # Docker secret mount (highest priority)
        Path(f"/run/secrets/{secret_name}"),
        # Local secrets directory
        base_dir / "secrets" / f"{secret_name}.txt",
        # Config directory (fallback)
        base_dir / "config" / f"{secret_name}.txt",
    ]

    return paths


def read_secret_from_file(file_path: Path) -> Optional[str]:
    """
    Read a secret from a file.

    Args:
        file_path: Path to the secret file

    Returns:
        Secret value (stripped of whitespace), or None if file doesn't exist or can't be read
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r") as f:
            secret = f.read().strip()
            if secret:
                return secret
    except Exception as e:
        logger.debug(f"Could not read secret from {file_path}: {e}")

    return None


def get_secret(
    secret_name: str,
    env_var_names: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
    required: bool = False,
) -> Optional[str]:
    """
    Get a secret from various sources in order of preference:
    1. Environment variables
    2. Docker secret mount (/run/secrets/)
    3. Local files (secrets/ directory, then config/ directory)

    Args:
        secret_name: Name of the secret (e.g., "openai_api_key")
        env_var_names: List of environment variable names to check (defaults to uppercase secret_name variants)
        base_dir: Base directory for local paths
        required: If True, raise ValueError if secret not found

    Returns:
        Secret value, or None if not found (unless required=True)

    Raises:
        ValueError: If required=True and secret not found
    """
    # Default environment variable names
    if env_var_names is None:
        # Try common variations
        secret_upper = secret_name.upper()
        env_var_names = [
            secret_upper,
            secret_upper.replace("-", "_"),
            f"LITELLM_{secret_upper}",
        ]

    # 1. Check environment variables first
    for env_var in env_var_names:
        value = os.getenv(env_var)
        if value:
            value = value.strip()
            if value:
                logger.debug(
                    f"✅ Loaded {secret_name} from environment variable {env_var}"
                )
                return value

    # 2. Check secret files
    secret_paths = get_secret_paths(secret_name, base_dir)
    for secret_path in secret_paths:
        secret = read_secret_from_file(secret_path)
        if secret:
            logger.debug(f"✅ Loaded {secret_name} from {secret_path}")
            return secret

    # 3. Not found
    if required:
        raise ValueError(
            f"{secret_name} not found. Checked: "
            f"environment variables ({', '.join(env_var_names)}), "
            f"and files: {', '.join(str(p) for p in secret_paths)}"
        )

    logger.warning(
        f"⚠️  {secret_name} not found. Checked: "
        f"environment variables ({', '.join(env_var_names)}), "
        f"and files: {', '.join(str(p) for p in secret_paths)}"
    )
    return None


def get_openai_api_key(
    base_dir: Optional[Path] = None,
    required: bool = False,
    allow_test_key: bool = False,
    environment: str = "development",
) -> Optional[str]:
    """
    Get OpenAI API key using the standard secret loading mechanism.

    Args:
        base_dir: Base directory for local paths
        required: If True, raise ValueError if key not found
        allow_test_key: If True and in test environment, allow a test key
        environment: Current environment (used for test key logic)

    Returns:
        API key, or None if not found (unless required=True)
    """
    # Try to get the key from Docker secrets or local files only (no env vars)
    api_key = get_secret(
        "openai_api_key",
        env_var_names=[],  # No env var dependencies - only Docker secrets and local files
        base_dir=base_dir,
        required=False,  # We handle required separately
    )

    # Never default to a hardcoded key - test fixtures should inject keys via Settings overrides
    # This prevents accidental use of invalid keys
    if not api_key and allow_test_key and environment == "test":
        logger.debug(
            "No API key found in test environment - test fixtures should inject via Settings override"
        )
        # Don't set a default - let the caller decide what to do

    # Check if required
    if not api_key and required:
        raise ValueError(
            "API key is required - must be provided via Docker secret at "
            "/run/secrets/openai_api_key or secrets/openai_api_key.txt. "
            "Or generate one with: make litellm-generate-api-token"
        )

    # Log status
    if api_key:
        logger.info(f"OpenAI API key loaded: {api_key[:10]}...")
        # Log warning if API key doesn't start with "sk-" (unusual format)
        if not api_key.startswith("sk-"):
            logger.warning(
                f"API key does not start with 'sk-': {api_key[:20]}... "
                f"(length: {len(api_key)}). This may be a non-standard key format."
            )
    else:
        logger.error("No OpenAI API key found")

    return api_key
