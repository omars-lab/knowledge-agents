#!/bin/bash
# Generate API key via LiteLLM proxy and save to secrets file
#
# This script:
# 1. Ensures PostgreSQL and LiteLLM proxy are running
# 2. Waits for services to be ready
# 3. Generates an API key via LiteLLM proxy
# 4. Saves the key to secrets/openai_api_key.txt

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SECRETS_DIR="$PROJECT_ROOT/secrets"
API_KEY_FILE="$SECRETS_DIR/openai_api_key.txt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔑 Generating API key via LiteLLM proxy..."

# Check if PostgreSQL is running
echo "🔍 Checking if PostgreSQL is running..."
if ! docker compose ps postgres 2>/dev/null | grep -q "healthy\|running\|Up"; then
    echo "🚀 Starting PostgreSQL container..."
    docker compose up -d postgres
else
    echo -e "${GREEN}✅${NC} PostgreSQL container is already running"
fi

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if docker compose ps postgres 2>/dev/null | grep -q "healthy\|running"; then
        if docker compose exec -T postgres pg_isready -U knowledge >/dev/null 2>&1; then
            echo -e "${GREEN}✅${NC} PostgreSQL is ready"
            break
        fi
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌${NC} PostgreSQL not ready after 30 attempts"
        exit 1
    fi
    sleep 1
done

# Check if proxy is running
echo "🔍 Checking if proxy is running..."
if ! docker compose ps llm-proxy 2>/dev/null | grep -q "running\|Up"; then
    echo "🚀 Rebuilding and starting proxy (to include prisma dependency)..."
    docker compose build llm-proxy 2>/dev/null || true
    docker compose up -d llm-proxy
else
    echo -e "${GREEN}✅${NC} Proxy container is already running"
fi

# Wait for proxy to be ready using centralized health check script
HEALTH_CHECK_SCRIPT="$PROJECT_ROOT/scripts/containers/litellm/check_proxy_health.sh"
if [ -f "$HEALTH_CHECK_SCRIPT" ]; then
    "$HEALTH_CHECK_SCRIPT" --timeout 30 --interval 1 --proxy-host localhost --proxy-port 4000 || {
        echo -e "${RED}❌${NC} Proxy not ready after 30 attempts"
        exit 1
    }
else
    echo -e "${YELLOW}⚠️${NC} Health check script not found at $HEALTH_CHECK_SCRIPT, using fallback check..."
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
            exit 1
        fi
        sleep 1
    done
fi

# Wait for database connection to be established
echo "⏳ Waiting for database connection to be established..."
sleep 5

# Create secrets directory if it doesn't exist
mkdir -p "$SECRETS_DIR"

# Get email from git config
EMAIL=$(git config user.email 2>/dev/null || echo "")
if [ -z "$EMAIL" ]; then
    echo -e "${RED}❌${NC} Error: Could not get email from git config. Run: git config user.email 'your@email.com'"
    exit 1
fi

echo "📧 Using email: $EMAIL"

# Generate API key
MASTER_KEY="sk-1234"
PROXY_HOST="${LITELLM_PROXY_HOST:-localhost}"
PROXY_PORT="${LITELLM_PROXY_PORT:-4000}"

echo "🌐 Calling LiteLLM proxy at http://$PROXY_HOST:$PROXY_PORT/key/generate..."

RESPONSE=$(curl -s -w "\n%{http_code}" \
    "http://$PROXY_HOST:$PROXY_PORT/key/generate" \
    --header "Authorization: Bearer $MASTER_KEY" \
    --header "Content-Type: application/json" \
    --data-raw "{\"models\": [\"lm_studio/qwen3-coder-30b\", \"qwen3-coder-30b\", \"lm_studio/gpt-oss-20b\", \"lm_studio/text-embedding-qwen3-embedding-8b\"], \"metadata\": {\"user\": \"$EMAIL\"}}" \
    2>/dev/null) || {
    echo -e "${RED}❌${NC} Error: Failed to connect to proxy. Is it running?"
    exit 1
}

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
    # Extract API key from response
    if command -v jq >/dev/null 2>&1; then
        KEY=$(echo "$BODY" | jq -r '.key // .api_key // empty' 2>/dev/null)
    else
        KEY=$(echo "$BODY" | grep -o '"key"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4 || \
              echo "$BODY" | grep -o '"api_key"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    fi
    
    if [ -z "$KEY" ]; then
        echo -e "${RED}❌${NC} Error: Could not extract key from response: $BODY"
        exit 1
    fi
    
    # Save API key to file
    echo "$KEY" > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
    
    echo -e "${GREEN}✅${NC} API key generated and saved to $API_KEY_FILE"
    echo "🔐 Key (first 16 chars): $(echo "$KEY" | cut -c1-16)..."
else
    echo -e "${RED}❌${NC} Error: Proxy returned HTTP $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi

