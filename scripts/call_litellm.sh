#!/bin/bash
# Call LiteLLM via proxy
#
# This script:
# 1. Ensures LiteLLM proxy is running
# 2. Waits for proxy to be ready
# 3. Passes all arguments to the Python script (which handles argument parsing and validation)
#
# All argument parsing and validation is handled by call_litellm_model.py
# This script only handles Docker orchestration.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Store all arguments to pass through to Python script
# (No argument parsing here - Python handles it all)
ALL_ARGS=("$@")

# Check if proxy is running
echo "🔍 Checking if proxy is running..."
if ! docker compose ps llm-proxy 2>/dev/null | grep -q "running\|Up"; then
    echo "🚀 Starting proxy container..."
    docker compose up -d llm-proxy
else
    echo -e "${GREEN}✅${NC} Proxy container is already running"
fi

# Wait for proxy to be ready using centralized health check script
HEALTH_CHECK_SCRIPT="$PROJECT_ROOT/scripts/containers/litellm/check_proxy_health.sh"
if [ -f "$HEALTH_CHECK_SCRIPT" ]; then
    "$HEALTH_CHECK_SCRIPT" --timeout 30 --interval 1 --proxy-host localhost --proxy-port 4000 || {
        echo -e "${RED}❌${NC} Proxy not ready after 30 attempts"
        echo "Showing proxy logs:"
        docker compose logs --tail=50 llm-proxy 2>/dev/null || true
        exit 1
    }
else
    echo -e "${YELLOW}⚠️${NC} Health check script not found, using fallback check..."
    # Fallback: simple check
    for i in $(seq 1 30); do
        if docker compose ps llm-proxy 2>/dev/null | grep -q "running\|Up"; then
            if curl -sf -o /dev/null -w "%{http_code}" http://localhost:4000/health 2>/dev/null | grep -qE "200|401"; then
                echo -e "${GREEN}✅${NC} Proxy is ready"
                break
            fi
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌${NC} Proxy not ready after 30 attempts"
            echo "Showing proxy logs:"
            docker compose logs --tail=50 llm-proxy 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done
fi

# Run the Python script in Docker with all arguments passed through
# Python script handles all argument parsing, validation, and error messages
cd "$PROJECT_ROOT"
docker compose run --rm --no-deps \
    -v "$(pwd)/scripts:/app/scripts" \
    -v "$(pwd)/src:/app/src" \
    test python -u /app/scripts/call_litellm_model.py "${ALL_ARGS[@]}" || {
    echo -e "\n${RED}❌${NC} Request failed. Showing proxy logs:\n"
    docker compose logs --tail=50 llm-proxy 2>/dev/null || true
    exit 1
}

