"""
File logging utilities for per-file logging during processing.

This module provides utilities to set up loggers that write to specific
stdout/stderr files for each NotePlan file being processed.
"""
from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional


class FileLoggingContext:
    """
    Context manager for setting up file-based logging for a specific file.
    
    Creates file handlers that write to stdout.log and stderr.log files
    while preserving console output.
    """
    
    def __init__(
        self,
        stdout_file: Path,
        stderr_file: Path,
        log_level: int = logging.INFO,
    ):
        """
        Initialize file logging context.
        
        Args:
            stdout_file: Path to stdout log file
            stderr_file: Path to stderr log file
            log_level: Logging level (default: INFO)
        """
        self.stdout_file = stdout_file
        self.stderr_file = stderr_file
        self.log_level = log_level
        self.handlers: List[logging.Handler] = []
        self.original_handlers: dict[str, List[logging.Handler]] = {}
        
    def __enter__(self) -> "FileLoggingContext":
        """Set up file handlers."""
        # Create file handlers
        stdout_handler = logging.FileHandler(self.stdout_file, mode='w', encoding='utf-8')
        stdout_handler.setLevel(self.log_level)
        stdout_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s')
        )
        
        stderr_handler = logging.FileHandler(self.stderr_file, mode='w', encoding='utf-8')
        stderr_handler.setLevel(logging.WARNING)  # Only warnings and errors to stderr
        stderr_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s')
        )
        
        # Get relevant loggers
        loggers_to_configure = [
            logging.getLogger('knowledge_agents'),
            logging.getLogger('knowledge_agents.agents'),
            logging.getLogger('knowledge_agents.utils'),
            logging.getLogger('knowledge_agents.utils.graph_utils'),
            logging.getLogger('knowledge_agents.utils.data_persistence'),
            logging.getLogger('knowledge_agents.agents.graph_builder_agent'),
            logging.root,  # Root logger catches everything
        ]
        
        # Store original handlers and add file handlers
        for logger in loggers_to_configure:
            if logger not in self.original_handlers:
                self.original_handlers[logger.name] = logger.handlers[:]
            
            # Add stdout handler (for INFO and above)
            logger.addHandler(stdout_handler)
            # Add stderr handler (for WARNING and above)
            logger.addHandler(stderr_handler)
            
            self.handlers.append(stdout_handler)
            self.handlers.append(stderr_handler)
        
        # Also redirect print statements and actual stdout/stderr
        self._setup_stdout_stderr_redirect()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up file handlers."""
        # Remove file handlers from loggers
        for logger_name, original_handlers in self.original_handlers.items():
            logger = logging.getLogger(logger_name)
            # Remove all handlers we added
            for handler in self.handlers:
                if handler in logger.handlers:
                    logger.removeHandler(handler)
            # Restore original handlers if needed
            # (Usually not needed as we're just adding, not replacing)
        
        # Clean up stdout/stderr redirects
        self._cleanup_stdout_stderr_redirect()
        
        return False  # Don't suppress exceptions
    
    def _setup_stdout_stderr_redirect(self):
        """Set up redirection of actual stdout/stderr streams."""
        # Open files for writing
        self.stdout_file_obj = open(self.stdout_file, 'w', encoding='utf-8')
        self.stderr_file_obj = open(self.stderr_file, 'w', encoding='utf-8')
        
        # Store original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Create a Tee-like class that writes to both file and original stream
        class Tee:
            def __init__(self, file_obj, original_stream):
                self.file = file_obj
                self.original = original_stream
            
            def write(self, text):
                self.file.write(text)
                self.file.flush()
                self.original.write(text)
                self.original.flush()
            
            def flush(self):
                self.file.flush()
                self.original.flush()
        
        # Replace stdout/stderr with Tee objects
        sys.stdout = Tee(self.stdout_file_obj, self.original_stdout)
        sys.stderr = Tee(self.stderr_file_obj, self.original_stderr)
    
    def _cleanup_stdout_stderr_redirect(self):
        """Restore original stdout/stderr streams."""
        if hasattr(self, 'stdout_file_obj'):
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            self.stdout_file_obj.close()
            self.stderr_file_obj.close()


@contextmanager
def file_logging_context(
    stdout_file: Path,
    stderr_file: Path,
    log_level: int = logging.INFO,
) -> Iterator[FileLoggingContext]:
    """
    Context manager for file-based logging.
    
    Sets up logging to write to specific stdout/stderr files while
    preserving console output.
    
    Usage:
        with file_logging_context(stdout_file, stderr_file):
            # All logging and print statements go to both console and files
            logger.info("This goes to stdout.log and console")
            logger.error("This goes to stderr.log and console")
            print("This also goes to stdout.log and console")
    
    Args:
        stdout_file: Path to stdout log file
        stderr_file: Path to stderr log file
        log_level: Logging level (default: INFO)
        
    Yields:
        FileLoggingContext instance
    """
    context = FileLoggingContext(stdout_file, stderr_file, log_level)
    with context:
        yield context


def setup_file_logger(
    relative_path: str,
    data_dir: Path,
    log_level: int = logging.INFO,
) -> tuple[Path, Path]:
    """
    Set up file logging for a specific NotePlan file.
    
    Creates stdout and stderr log file paths and ensures directories exist.
    
    Args:
        relative_path: Relative path from NotePlan root
        data_dir: Base data directory
        log_level: Logging level (default: INFO)
        
    Returns:
        Tuple of (stdout_file_path, stderr_file_path)
    """
    from .data_persistence import get_file_data_dir, get_file_base_name
    
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    
    stdout_file = file_data_dir / f"{base_name}_stdout.log"
    stderr_file = file_data_dir / f"{base_name}_stderr.log"
    
    return stdout_file, stderr_file

