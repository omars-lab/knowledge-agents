#!/usr/bin/env bash
# lm_studio_ctl.sh — Control LM Studio locally or remotely via SSH
#
# Usage:
#   ./scripts/lm_studio_ctl.sh status [--remote HOST]
#   ./scripts/lm_studio_ctl.sh load-embeddings [--remote HOST]
#   ./scripts/lm_studio_ctl.sh test-embedding [--remote HOST]
#   ./scripts/lm_studio_ctl.sh ls [--remote HOST]
#   ./scripts/lm_studio_ctl.sh ps [--remote HOST]
#
# If --remote is omitted, runs locally (assumes LM Studio is on this machine).
# If --remote HOST is provided, runs commands via SSH to HOST.

set -euo pipefail

# Defaults
LMS_CLI="/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms"
EMBED_MODEL="Qwen/Qwen3-Embedding-8B-GGUF/Qwen3-Embedding-8B-Q4_K_M.gguf"
EMBED_MODEL_ID="text-embedding-qwen3-embedding-8b"
API_PORT=1234
REMOTE_HOST=""

# Parse args
COMMAND="${1:-help}"
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remote) REMOTE_HOST="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Run a command locally or via SSH
run_cmd() {
    if [ -n "$REMOTE_HOST" ]; then
        ssh -o ConnectTimeout=5 "$REMOTE_HOST" "$@" 2>/dev/null
    else
        eval "$@"
    fi
}

# Get the API host (local=localhost, remote=IP via SSH)
get_api_host() {
    if [ -n "$REMOTE_HOST" ]; then
        run_cmd "ifconfig | grep 'inet 192' | awk '{print \$2}' | head -1"
    else
        echo "localhost"
    fi
}

case "$COMMAND" in
    status)
        echo "🔍 LM Studio Status${REMOTE_HOST:+ (remote: $REMOTE_HOST)}..."
        echo ""
        echo "Server:"
        run_cmd "'$LMS_CLI' status" || echo "  ❌ LM Studio CLI not available"
        echo ""
        echo "Loaded Models:"
        run_cmd "'$LMS_CLI' ps" || echo "  (none)"
        echo ""
        API_HOST=$(get_api_host)
        if [ -n "$API_HOST" ]; then
            echo "Network (${API_HOST}:${API_PORT}):"
            if curl -sf --connect-timeout 3 "http://${API_HOST}:${API_PORT}/v1/models" >/dev/null 2>&1; then
                MODEL_COUNT=$(curl -sf "http://${API_HOST}:${API_PORT}/v1/models" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']))" 2>/dev/null || echo "?")
                echo "  ✅ API reachable — $MODEL_COUNT models available"
            else
                echo "  ❌ API not reachable at http://${API_HOST}:${API_PORT}"
            fi
        fi
        ;;

    load-embeddings)
        echo "🚀 Loading embedding model: $EMBED_MODEL_ID"
        run_cmd "'$LMS_CLI' load --yes '$EMBED_MODEL'" | grep -v '^\[' | tail -5 || echo "❌ Failed"
        echo ""
        echo "📦 Loaded models:"
        run_cmd "'$LMS_CLI' ps"
        ;;

    test-embedding)
        API_HOST=$(get_api_host)
        if [ -z "$API_HOST" ]; then
            echo "❌ Cannot determine API host"
            exit 1
        fi
        echo "🧪 Testing embedding (${API_HOST}:${API_PORT})..."
        RESULT=$(curl -sf --connect-timeout 10 -X POST "http://${API_HOST}:${API_PORT}/v1/embeddings" \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$EMBED_MODEL_ID\", \"input\": \"test embedding\"}" 2>&1)
        if [ -n "$RESULT" ]; then
            echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
dim = len(d['data'][0]['embedding'])
print(f'✅ OK: {dim} dimensions (model: {d.get(\"model\", \"?\")})')
" 2>/dev/null || echo "❌ Unexpected response: ${RESULT:0:200}"
        else
            echo "❌ No response from embedding endpoint"
        fi
        ;;

    ls)
        echo "📦 Downloaded models${REMOTE_HOST:+ on $REMOTE_HOST}:"
        run_cmd "'$LMS_CLI' ls"
        ;;

    ps)
        echo "🔄 Loaded models${REMOTE_HOST:+ on $REMOTE_HOST}:"
        run_cmd "'$LMS_CLI' ps"
        ;;

    help|*)
        echo "Usage: $0 <command> [--remote HOST]"
        echo ""
        echo "Commands:"
        echo "  status           Check LM Studio server, loaded models, and API"
        echo "  load-embeddings  Load the embedding model"
        echo "  test-embedding   Test embedding generation end-to-end"
        echo "  ls               List all downloaded models"
        echo "  ps               List currently loaded models"
        echo ""
        echo "Options:"
        echo "  --remote HOST    Run commands via SSH to HOST (default: local)"
        ;;
esac
