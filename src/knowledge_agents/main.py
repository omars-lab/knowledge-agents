"""
FastAPI main application entry point
"""
import asyncio
import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from .config.api_config import Settings
from .config.logging_config import setup_logging
from .dependencies import get_dependencies, initialize_dependencies
from .metrics import Metrics
from .middleware import MetricsMiddleware
from .routers.base import router as base_router
from .routers.base import set_db_connected
from .routers.note_query import router as note_query_router
from .startup import startup_tasks

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize metrics
metrics = Metrics()

# Initialize Settings (loaded once at startup)
settings = Settings()

# Initialize Dependencies container (explicit dependency injection)
dependencies = initialize_dependencies(settings)

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware, metrics=metrics)

# Include routers
app.include_router(base_router)  # Base routes (/, /health, /hello)
app.include_router(note_query_router, prefix="/api/v1/notes")


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting up Agentic API...")
    # Get dependencies (already initialized at module level)
    deps = get_dependencies()
    db_connected = await startup_tasks(deps, metrics)
    set_db_connected(db_connected)
    logger.info(f"Database connected: {db_connected}")


async def main() -> None:
    """Main entry point for agentic API."""
    # Get dependencies (already initialized at module level)
    deps = get_dependencies()
    db_connected = await startup_tasks(deps, metrics)
    set_db_connected(db_connected)

    # Start FastAPI server
    config = uvicorn.Config(
        app=app, host=settings.api_host, port=settings.api_port, log_level="info"
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Agentic API shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
