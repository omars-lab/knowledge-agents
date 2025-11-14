#!/bin/bash
# Health check script for LiteLLM proxy
# This script can be used both as a Docker healthcheck and as a standalone check
#
# Usage:
#   - As healthcheck: returns 0 if healthy, 1 if unhealthy
#   - As standalone: prints status messages and returns 0 if healthy, 1 if unhealthy
#
# Options:
#   --quiet: Suppress output (useful for healthchecks)
#   --timeout SECONDS: Maximum time to wait (default: 30)
#   --interval SECONDS: Time between checks (default: 1)

set -e

# Default values
QUIET=false
TIMEOUT=30
INTERVAL=1
PROXY_HOST="${LITELLM_PROXY_HOST:-localhost}"
PROXY_PORT="${LITELLM_PROXY_PORT:-4000}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quiet)
            QUIET=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --proxy-host)
            PROXY_HOST="$2"
            shift 2
            ;;
        --proxy-port)
            PROXY_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Logging function
log() {
    if [ "$QUIET" = false ]; then
        echo "$@"
    fi
}

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Try to read admin API key from Docker secret mount (preferred for health checks)
API_KEY=""
if [ -f /run/secrets/admin_api_key ]; then
    API_KEY=$(cat /run/secrets/admin_api_key | tr -d '\n\r' | tr -d ' ')
fi

# If running outside Docker, try to read from local secrets directory
if [ -z "$API_KEY" ]; then
    # Try to find the project root (script is in scripts/containers/litellm/)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    
    if [ -f "$PROJECT_ROOT/secrets/admin_api_key.txt" ]; then
        API_KEY=$(cat "$PROJECT_ROOT/secrets/admin_api_key.txt" | tr -d '\n\r' | tr -d ' ')
    elif [ -f "$PROJECT_ROOT/secrets/openai_api_key.txt" ]; then
        # Fallback to user API key if admin key not available
        API_KEY=$(cat "$PROJECT_ROOT/secrets/openai_api_key.txt" | tr -d '\n\r' | tr -d ' ')
    fi
fi

# Function to check proxy health
check_proxy_health() {
    local url="http://${PROXY_HOST}:${PROXY_PORT}/health"
    local http_code
    
    if [ -n "$API_KEY" ]; then
        # Try with admin API key - use -s to suppress output, but don't use -f so we can check status code
        http_code=$(curl --location -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_KEY" "$url" 2>/dev/null || echo "000")
    else
        # Try without API key - use liveliness endpoint which might not require auth
        http_code=$(curl --location -s -o /dev/null -w "%{http_code}" -X 'GET' "http://${PROXY_HOST}:${PROXY_PORT}/health/liveliness" -H 'accept: application/json' 2>/dev/null || echo "000")
    fi
    
    # Extract just the HTTP code (in case of multiple outputs)
    http_code=$(echo "$http_code" | tail -1 | tr -d ' ')
    
    # 200 = success, 401 = server is up but needs auth (still healthy)
    # 000 = connection failed, 5xx = server error
    case "$http_code" in
        200|401)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Wait for proxy to be ready
wait_for_proxy() {
    local max_attempts=$((TIMEOUT / INTERVAL))
    local attempt=0
    
    log "⏳ Waiting for proxy to be ready at ${PROXY_HOST}:${PROXY_PORT}..."
    
    while [ $attempt -lt $max_attempts ]; do
        # Check if container is running (if we're in Docker or checking Docker containers)
        if command -v docker >/dev/null 2>&1; then
            if docker compose ps llm-proxy 2>/dev/null | grep -q "running\|Up"; then
                if check_proxy_health; then
                    if [ "$QUIET" = false ]; then
                        echo -e "${GREEN}✅${NC} Proxy is ready"
                    fi
                    return 0
                fi
            fi
        else
            # Not in Docker, just check the endpoint
            if check_proxy_health; then
                if [ "$QUIET" = false ]; then
                    echo -e "${GREEN}✅${NC} Proxy is ready"
                fi
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ] && [ "$QUIET" = false ]; then
            log "   Attempt $attempt/$max_attempts: Proxy not ready yet, waiting ${INTERVAL}s..."
        fi
        sleep "$INTERVAL"
    done
    
    if [ "$QUIET" = false ]; then
        echo -e "${RED}❌${NC} Proxy not ready after $TIMEOUT seconds"
    fi
    return 1
}

# Main execution
if [ "$QUIET" = true ]; then
    # Quiet mode - just check once and return status (for Docker healthcheck)
    check_proxy_health
    exit $?
else
    # Verbose mode - wait for proxy to be ready
    wait_for_proxy
    exit $?
fi

