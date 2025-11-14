"""Centralized logging configuration."""

import logging
import logging.config
import os
from typing import Any, Dict

from .api_config import settings


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration based on environment."""
    log_level = settings.log_level.upper()
    environment = settings.environment

    # Check if build/logs directory exists
    logs_dir_exists = os.path.exists("build/logs")

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: "
                "%(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {  # root logger
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "src": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    # Only add file logging if the logs directory exists
    if logs_dir_exists:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "detailed",
            "filename": "build/logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }

        # Add file handler to src logger
        config["loggers"]["src"]["handlers"] = ["console", "file"]  # type: ignore

        # In production, add file logging to root logger too
        if environment == "production":
            config["loggers"][""]["handlers"] = ["console", "file"]  # type: ignore

    return config


def setup_logging() -> None:
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    try:
        os.makedirs("build/logs", exist_ok=True)
    except (OSError, PermissionError):
        # If we can't create the directory, file logging will be disabled
        pass

    # Apply logging configuration
    logging.config.dictConfig(get_logging_config())

    # Set up third-party library log levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
