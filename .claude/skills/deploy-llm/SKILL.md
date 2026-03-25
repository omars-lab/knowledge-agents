---
name: deploy-llm
description: Verify and start LM Studio on Mac Studio for embeddings and local inference
user_invocable: true
---

# /deploy-llm — Ensure local LLM hardware is running

Verify and start the local LLM infrastructure (LM Studio on Mac Studio) needed for embeddings and local model inference.

## Architecture

```
Mac Studio (192.168.1.131)       Docker Host (local)
┌───────────────────────┐        ┌──────────────────┐
│  LM Studio (port 1234)│◄──HTTP─│  LiteLLM Proxy   │
│  - Qwen3-Embed-8B     │        │  (port 4000)     │
│  - Nomic-Embed-v1.5   │        │  - Routes to     │
│  - Devstral/Ministral │        │    Mac Studio     │
│  lms CLI bundled       │        └──────────────────┘
└───────────────────────┘
```

## Quick Start

```bash
# Check everything
make lm-studio-status

# Load embedding model
make lm-studio-load-embeddings

# Test end-to-end
make lm-studio-test-embedding

# List available models
make lm-studio-ls
```

## Pre-flight Checks (in order)

### 1. SSH Connectivity
```bash
ssh -o ConnectTimeout=5 mac-studio "echo OK"
```

### 2. LM Studio Server Status
```bash
# Uses bundled CLI at /Applications/LM Studio.app/Contents/Resources/app/.webpack/lms
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' status"
```
Expected: `Server: ON (port: 1234)`

### 3. Embedding Model Loaded
```bash
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' ps"
```
Expected: `text-embedding-qwen3-embedding-8b` in IDLE or RUNNING state

### 4. API Accessible from Docker Host
```bash
curl -sf http://192.168.1.131:1234/v1/models | python3 -m json.tool
```

### 5. Embedding Test
```bash
curl -s -X POST http://192.168.1.131:1234/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "text-embedding-qwen3-embedding-8b", "input": "test"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['data'][0]['embedding']), 'dimensions')"
```
Expected: `4096 dimensions`

## Recovery Actions

### LM Studio Not Running
```bash
ssh mac-studio "open -a 'LM Studio'"
# Wait ~15s for startup
```

### No Models Loaded
```bash
make lm-studio-load-embeddings
# Or manually:
ssh mac-studio "'/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms' load --yes 'Qwen/Qwen3-Embedding-8B-GGUF/Qwen3-Embedding-8B-Q4_K_M.gguf'"
```

### API Not Accessible from Network
LM Studio may be binding to localhost only. In the LM Studio GUI:
1. Go to Settings → Server
2. Enable "Serve on local network" / set bind address to `0.0.0.0`
3. Verify with `curl http://192.168.1.131:1234/v1/models`

### IP Address Changed
```bash
ssh mac-studio "ifconfig | grep 'inet 192'"
# Update docker-compose.yml LM_STUDIO_HOST env var
```

## Available Models (as of 2026-03-22)

| Model | Type | Size | Dimensions |
|-------|------|------|------------|
| text-embedding-qwen3-embedding-8b | Embedding | 4.68 GB | 4096 |
| text-embedding-nomic-embed-text-v1.5 | Embedding | 84 MB | 768 |
| mistralai/devstral-small-2-2512 | LLM | 14.12 GB | — |
| mistralai/ministral-3-14b-reasoning | LLM | 9.12 GB | — |
| openai/gpt-oss-20b | LLM | 12.10 GB | — |
| qwen/qwen3-coder-30b | LLM | 17.19 GB | — |

## Key Details

- **SSH host**: `mac-studio` (configured in `~/.ssh/config`)
- **LMS CLI path**: `/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms`
- **API IP**: `192.168.1.131` (may change with DHCP)
- **API port**: `1234`
- **No npm/node on Mac Studio** — use the bundled CLI, not `npx lmstudio install-cli`
- **LM Studio version**: 0.3.39+2
- **Mac Studio**: Apple Silicon (arm64)
