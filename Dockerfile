# Multi-stage build: build stage for testing, app stage for production
ARG BUILD_TIMESTAMP
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Add build timestamp label to force rebuilds
LABEL build_timestamp=${BUILD_TIMESTAMP}

# Build stage - includes dev dependencies for testing
FROM base as build

# Copy requirements and install ALL dependencies (including dev)
COPY requirements.txt .
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Note: tidy-mcp will be installed via volume mount in docker-compose at runtime

# Copy application code, tests, scripts, and configuration files
COPY src/ ./src/
COPY tst/ ./tst/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY .flake8 .flake8
COPY pyproject.toml ./

# Copy pytest configuration into the image
COPY pytest.ini ./

# Run tests to ensure everything works
ENV PYTHONPATH=/app/src
# Skip unit tests during build - they will be run during integration tests
# RUN pytest tst/unit/ -v -m "unit"

# App stage - production (tests have passed, only need runtime deps)
FROM python:3.11-slim as app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Copy requirements and install ONLY production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Note: tidy-mcp will be installed via volume mount in docker-compose at runtime

# Copy application code (no tests needed in production)
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from src.knowledge_agents.startup import check_database_connection; from src.knowledge_agents.metrics import Metrics; asyncio.run(check_database_connection(Metrics()))" || exit 1

# Run the application
CMD ["python", "-m", "src.knowledge_agents.main"]

# LiteLLM Router stage - for LiteLLM proxy server
FROM base as litellm-proxy

# Copy LiteLLM-specific requirements and install dependencies
COPY requirements-litellm.txt .
RUN pip install --no-cache-dir -r requirements-litellm.txt

# Copy scripts needed for LiteLLM proxy
COPY scripts/containers/litellm ./scripts/
# Ensure healthcheck scripts are executable
RUN chmod +x /app/scripts/healthcheck_litellm.sh /app/scripts/check_proxy_health.sh

# Copy Prisma schema file for LiteLLM
COPY config/litellm/schema.prisma ./schema.prisma

# Generate Prisma client
RUN python -m prisma generate

# Expose LiteLLM proxy port
EXPOSE 4000

# Default command (can be overridden in docker-compose.yml)
CMD ["python", "/app/scripts/start_litellm_proxy.py"]

# Seeder stage - for database and vector store seeding
FROM base as seeder

# Copy seeder-specific requirements and install dependencies
COPY requirements-seeder.txt .
RUN pip install --no-cache-dir -r requirements-seeder.txt

# Copy application code needed for seeding scripts
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/
