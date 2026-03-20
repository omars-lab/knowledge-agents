"""
Unit tests for file logging utilities.

Tests verify that:
1. File logging context manager works correctly
2. Logs are written to stdout/stderr files
3. Console output is preserved
4. Multiple loggers are configured correctly
5. Cleanup works properly
"""
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_agents.utils.file_logging import (
    FileLoggingContext,
    file_logging_context,
    setup_file_logger,
)

pytestmark = [pytest.mark.unit]


class TestSetupFileLogger:
    """Test setup_file_logger function."""

    def test_creates_log_file_paths(self):
        """Test that log file paths are created correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            
            stdout_path, stderr_path = setup_file_logger(relative_path, data_dir)
            
            assert stdout_path.parent.exists()
            assert stdout_path.name == "file_stdout.log"
            assert stderr_path.name == "file_stderr.log"

    def test_handles_nested_paths(self):
        """Test that nested paths are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "Calendar/2025/2025-01-15.md"
            
            stdout_path, stderr_path = setup_file_logger(relative_path, data_dir)
            
            assert stdout_path.parent.exists()
            assert "2025-01-15" in stdout_path.name


class TestFileLoggingContext:
    """Test FileLoggingContext class."""

    def test_creates_log_files(self):
        """Test that log files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger = logging.getLogger("test")
                logger.info("Test message")
            
            assert stdout_file.exists()
            assert stderr_file.exists()

    def test_writes_to_stdout_file(self):
        """Test that INFO logs are written to stdout file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger = logging.getLogger("test")
                logger.info("Info message")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "Info message" in content

    def test_writes_to_stderr_file(self):
        """Test that WARNING/ERROR logs are written to stderr file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger = logging.getLogger("test")
                logger.warning("Warning message")
                logger.error("Error message")
            
            with open(stderr_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "Warning message" in content
            assert "Error message" in content

    def test_preserves_console_output(self):
        """Test that console output is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            # Capture original stdout
            original_stdout = sys.stdout
            
            with FileLoggingContext(stdout_file, stderr_file):
                # Verify stdout is still accessible
                assert sys.stdout is not original_stdout
                print("Console test")
            
            # Verify stdout is restored
            assert sys.stdout is original_stdout
            
            # Verify file was written
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Console test" in content

    def test_configures_multiple_loggers(self):
        """Test that multiple loggers are configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger1 = logging.getLogger("knowledge_agents")
                logger2 = logging.getLogger("knowledge_agents.agents")
                logger3 = logging.getLogger("knowledge_agents.utils")
                
                logger1.info("Logger 1 message")
                logger2.info("Logger 2 message")
                logger3.info("Logger 3 message")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "Logger 1 message" in content
            assert "Logger 2 message" in content
            assert "Logger 3 message" in content

    def test_cleans_up_handlers(self):
        """Test that handlers are cleaned up after context exit."""
        logger = logging.getLogger("test_cleanup")
        initial_handler_count = len(logger.handlers)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger.info("Test")
                # Handlers should be added
                assert len(logger.handlers) > initial_handler_count
            
            # Handlers should be removed
            assert len(logger.handlers) == initial_handler_count

    def test_handles_exceptions(self):
        """Test that exceptions don't prevent cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            original_stdout = sys.stdout
            
            try:
                with FileLoggingContext(stdout_file, stderr_file):
                    raise ValueError("Test exception")
            except ValueError:
                pass
            
            # Verify cleanup happened
            assert sys.stdout is original_stdout


class TestFileLoggingContextFunction:
    """Test file_logging_context function."""

    def test_context_manager_function(self):
        """Test that file_logging_context works as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with file_logging_context(stdout_file, stderr_file):
                logger = logging.getLogger("test")
                logger.info("Context test")
            
            assert stdout_file.exists()
            with open(stdout_file, 'r', encoding='utf-8') as f:
                assert "Context test" in f.read()

    def test_custom_log_level(self):
        """Test that custom log level works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with file_logging_context(stdout_file, stderr_file, log_level=logging.DEBUG):
                logger = logging.getLogger("test")
                logger.debug("Debug message")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "Debug message" in content


class TestPrintStatements:
    """Test that print statements are captured."""

    def test_captures_print_to_stdout(self):
        """Test that print statements are captured in stdout file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                print("Print test message")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "Print test message" in content

    def test_captures_multiple_prints(self):
        """Test that multiple print statements are captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                print("First message")
                print("Second message")
                print("Third message")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "First message" in content
            assert "Second message" in content
            assert "Third message" in content


class TestFileEncoding:
    """Test file encoding handling."""

    def test_handles_unicode_content(self):
        """Test that unicode content is handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_file = Path(tmpdir) / "stdout.log"
            stderr_file = Path(tmpdir) / "stderr.log"
            
            with FileLoggingContext(stdout_file, stderr_file):
                logger = logging.getLogger("test")
                logger.info("Unicode test: émojis 🎉 and 中文")
                print("Print with unicode: émojis 🎉")
            
            with open(stdout_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "émojis" in content or "🎉" in content




