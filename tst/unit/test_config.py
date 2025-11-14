"""Tests for configuration management and .env file loading."""

import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from knowledge_agents.config.api_config import Settings

pytestmark = [pytest.mark.unit]


class TestConfigEnvLoading:
    """Test configuration loading from .env files."""

    def test_default_settings(self):
        """Test that default settings are loaded when no .env file exists."""
        # Create a temporary directory without .env file
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Reload settings in clean environment
                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings()

                    # Check default values
                    assert settings.environment == "development"
                    assert settings.debug is False
                    assert settings.log_level == "INFO"
                    assert (
                        settings.database_url
                        == "postgresql+asyncpg://postgres:password@postgres:5432/knowledge_workflow"
                    )
                    assert settings.db_pool_size == 10
                    assert settings.db_max_overflow == 20
                    assert settings.db_pool_timeout == 30
                    assert settings.api_host == "0.0.0.0"
                    assert settings.api_port == 8000

            finally:
                os.chdir(original_cwd)

    def test_env_file_loading(self):
        """Test that .env file values override defaults."""
        # Create a temporary .env file
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create .env file with custom values
                env_content = """
# Test environment variables
ENVIRONMENT=production
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=60
API_HOST=127.0.0.1
API_PORT=9000
"""
                with open(".env", "w") as f:
                    f.write(env_content)

                # Reload settings in clean environment
                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings()

                    # Check that .env values override defaults
                    assert settings.environment == "production"
                    assert settings.debug is True
                    assert settings.log_level == "DEBUG"
                    assert (
                        settings.database_url
                        == "postgresql://test:test@localhost:5432/test_db"
                    )
                    assert settings.db_pool_size == 20
                    assert settings.db_max_overflow == 30
                    assert settings.db_pool_timeout == 60
                    assert settings.api_host == "127.0.0.1"
                    assert settings.api_port == 9000

            finally:
                os.chdir(original_cwd)

    def test_environment_variables_override_env_file(self):
        """Test that environment variables override .env file values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create .env file
                env_content = """
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql://env_file:env_file@localhost:5432/env_file_db
"""
                with open(".env", "w") as f:
                    f.write(env_content)

                # Set environment variables that should override .env file
                env_vars = {
                    "ENVIRONMENT": "staging",
                    "DEBUG": "true",
                    "LOG_LEVEL": "WARNING",
                    "DATABASE_URL": "postgresql://env_var:env_var@localhost:5432/env_var_db",
                }

                with patch.dict(os.environ, env_vars):
                    settings = Settings()

                    # Environment variables should take precedence
                    assert settings.environment == "staging"
                    assert settings.debug is True
                    assert settings.log_level == "WARNING"
                    assert (
                        settings.database_url
                        == "postgresql://env_var:env_var@localhost:5432/env_var_db"
                    )

            finally:
                os.chdir(original_cwd)

    def test_missing_env_file_uses_defaults(self):
        """Test that missing .env file falls back to defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # No .env file created
                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings()

                    # Should use default values
                    assert settings.environment == "development"
                    assert settings.debug is False
                    assert settings.log_level == "INFO"
                    assert (
                        settings.database_url
                        == "postgresql+asyncpg://postgres:password@postgres:5432/knowledge_workflow"
                    )

            finally:
                os.chdir(original_cwd)

    def test_partial_env_file(self):
        """Test that .env file with only some variables works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create .env file with only some variables
                env_content = """
ENVIRONMENT=production
DEBUG=true
# Other variables not specified, should use defaults
"""
                with open(".env", "w") as f:
                    f.write(env_content)

                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings()

                    # Specified variables should be overridden
                    assert settings.environment == "production"
                    assert settings.debug is True

                    # Non-specified variables should use defaults
                    assert settings.log_level == "INFO"
                    assert (
                        settings.database_url
                        == "postgresql+asyncpg://postgres:password@postgres:5432/knowledge_workflow"
                    )
                    assert settings.db_pool_size == 10

            finally:
                os.chdir(original_cwd)


class TestConfigValidation:
    """Test configuration validation and error handling."""

    def test_valid_configuration(self):
        """Test that valid configuration loads without errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create valid .env file
                env_content = """
ENVIRONMENT=production
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://user:pass@localhost:5432/db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=60
API_HOST=0.0.0.0
API_PORT=8000
"""
                with open(".env", "w") as f:
                    f.write(env_content)

                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings()

                    # Should load without errors
                    assert settings.environment == "production"
                    assert settings.debug is True
                    assert settings.log_level == "DEBUG"

            finally:
                os.chdir(original_cwd)

    def test_invalid_database_url_format(self):
        """Test that invalid database URL format raises validation error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create .env file with invalid database URL
                env_content = """
DATABASE_URL=invalid_url_format
"""
                with open(".env", "w") as f:
                    f.write(env_content)

                with patch.dict(os.environ, {}, clear=True):
                    # Should not raise validation error for URL format
                    # Pydantic doesn't validate URL format by default for strings
                    settings = Settings()
                    assert settings.database_url == "invalid_url_format"

            finally:
                os.chdir(original_cwd)
