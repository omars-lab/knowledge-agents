# /deploy-llm — Ensure local LLM hardware is running

Verify and start the local LLM infrastructure (LM Studio on Mac Studio) needed for embeddings and local model inference.

## Architecture

```
Mac Studio (remote)           Docker Host (local)
┌───────────────┐             ┌──────────────────┐
│  LM Studio    │◄──HTTP──────│  LiteLLM Proxy   │
│  (port 1234)  │             │  (port 4000)     │
│  - Embeddings │             │  - Routes to     │
│  - Chat       │             │    LM Studio     │
└───────────────┘             └──────────────────┘
```

## Pre-flight Checks

Run these checks in order. Stop at first failure.

### 1. Network Connectivity
```bash
# Check Mac Studio is reachable
ping -c 1 -W 2 <mac-studio-ip>
```

### 2. LM Studio API
```bash
# Check LM Studio is running and responding
curl -sf http://<mac-studio-ip>:1234/v1/models | python3 -m json.tool
```

### 3. Embedding Model Loaded
```bash
# Verify the embedding model is loaded
curl -sf http://<mac-studio-ip>:1234/v1/models | python3 -c "
import sys, json
models = json.load(sys.stdin)['data']
embed_models = [m for m in models if 'embed' in m['id'].lower()]
if embed_models:
    print(f'Embedding models loaded: {[m[\"id\"] for m in embed_models]}')
else:
    print('WARNING: No embedding models loaded')
    sys.exit(1)
"
```

### 4. LiteLLM Proxy
```bash
# Check LiteLLM proxy is running and healthy
curl -sf http://localhost:4000/health/liveliness
```

### 5. End-to-End Embedding Test
```bash
# Test embedding generation through the full chain
curl -s -X POST http://localhost:4000/v1/embeddings \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{"model": "lm_studio/text-embedding-qwen3-embedding-8b", "input": "test"}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'data' in data and len(data['data']) > 0:
    dim = len(data['data'][0]['embedding'])
    print(f'Embedding OK: {dim} dimensions')
else:
    print(f'Embedding FAILED: {data}')
    sys.exit(1)
"
```

## Recovery Actions

### LM Studio Not Running
SSH into the Mac Studio and start LM Studio:
```bash
ssh <mac-studio-user>@<mac-studio-ip> "open -a 'LM Studio'"
```
Wait ~30 seconds for startup, then verify model is loaded.

### Embedding Model Not Loaded
LM Studio GUI must have the model loaded. If SSH access is available:
```bash
# Check available models
ssh <mac-studio-user>@<mac-studio-ip> "ls ~/\".cache/lm-studio/models/\""
```
The model may need to be loaded manually via the LM Studio UI.

### LiteLLM Proxy Not Healthy
```bash
make docker-up  # Starts all services including llm-proxy
# Or specifically:
docker compose restart llm-proxy
```

## Integration with Claude Agent

When the deploy-llm checks pass, you can re-enable `semantic_search` in the Claude agent:
1. Uncomment the embedding client in `tools.py:init_tool_clients()`
2. Add `semantic_search` back to `ALL_TOOLS` and `TOOL_NAMES`
3. Rebuild: `docker compose up -d --build claude-agent`

## Configuration

Key environment variables (in docker-compose.yml):
- `CLAUDE_AGENT_LITELLM_PROXY_HOST`: LiteLLM proxy hostname (default: `llm-proxy`)
- `CLAUDE_AGENT_LITELLM_PROXY_PORT`: LiteLLM proxy port (default: `4000`)
- `CLAUDE_AGENT_LITELLM_PROXY_API_KEY`: LiteLLM virtual key (default: `sk-1234`)
- `CLAUDE_AGENT_LITELLM_PROXY_EMBEDDING_MODEL`: Model name (default: `lm_studio/text-embedding-qwen3-embedding-8b`)
