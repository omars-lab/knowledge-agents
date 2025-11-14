"""
Base routes for the Agentic API.
"""
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine as sqlalchemy_create_async_engine

from ..config.api_config import Settings
from ..dependencies import get_dependencies
from ..metrics import metrics

logger = logging.getLogger(__name__)

router = APIRouter()

# Global variable to track database connection status
db_connected = False


def set_db_connected(status: bool) -> None:
    """Set the database connection status."""
    global db_connected
    db_connected = status


@router.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint."""
    return {
        "service": "Agentic API",
        "version": "1.0.0",
        "message": "Agentic API is running",
        "database_connected": db_connected,
    }


@router.get("/hello")
async def hello() -> Dict[str, Any]:
    """Hello world endpoint for canary monitoring."""
    # Test database connection on each request
    if db_connected:
        try:
            # Get settings from dependencies
            deps = get_dependencies()
            db_url = deps.settings.database_url
            if db_url.startswith("postgresql://"):
                async_db_url = db_url.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            else:
                async_db_url = db_url

            engine = sqlalchemy_create_async_engine(async_db_url)
            async with engine.begin() as conn:
                # Get table count
                result = await conn.execute(
                    text(
                        "SELECT COUNT(*) as table_count FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
                row = result.fetchone()
                table_count = row[0] if row else 0

                # Get actual data from our plans table
                result = await conn.execute(
                    text("SELECT COUNT(*) as record_count FROM plans")
                )
                row = result.fetchone()
                record_count = row[0] if row else 0

                # Get a sample record
                result = await conn.execute(text("SELECT title FROM plans LIMIT 1"))
                row = result.fetchone()
                sample_record = row[0] if row else None

            await engine.dispose()

            return {
                "message": "Hello, World!",
                "database_connected": db_connected,
                "database_tables": table_count,
                "database_records": record_count,
                "sample_record": sample_record,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"Database query failed in hello endpoint: {e}")
            return {
                "message": "Hello, World!",
                "database_connected": False,
                "error": str(e),
            }
    else:
        return {"message": "Hello, World!", "database_connected": db_connected}


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint."""
    if db_connected:
        return {"status": "healthy", "database": "connected", "timestamp": time.time()}
    else:
        raise HTTPException(status_code=503, detail="Database not connected")


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return metrics.generate_metrics()
