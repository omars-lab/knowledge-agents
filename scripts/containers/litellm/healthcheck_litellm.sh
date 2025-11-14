#!/bin/sh
# Health check script for LiteLLM proxy (Docker healthcheck wrapper)
# This is a thin wrapper around the main health check script

exec /app/scripts/check_proxy_health.sh --quiet

