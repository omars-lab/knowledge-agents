# Architecture

> **Living Document** — update when adding/removing containers, changing networks, or modifying routing (Kong, CF Tunnel).

## System Overview

```mermaid
graph TB
    subgraph Internet
        User([User / Browser])
    end

    subgraph "Cloudflare"
        CF_Access[CF Access<br/>LinkedIn SSO]
        CF_Tunnel[CF Tunnel]
    end

    User --> CF_Access --> CF_Tunnel

    subgraph "private-site stack"
        Kong[Kong Gateway<br/>:8000]
        CF_Tunnel --> Kong
    end

    subgraph "knowledge-agents stack"
        subgraph "Chat"
            ChatUI[chat<br/>nginx:alpine :80<br/>Static chat UI]
        end

        subgraph "Agent Layer"
            ClaudeAgent[claude-agent<br/>FastAPI :8000<br/>Multi-turn agent]
            TidyMCP[tidy-mcp<br/>FastAPI :8000<br/>NotePlan MCP tools]
        end

        subgraph "Data Layer"
            Qdrant[qdrant<br/>:6333<br/>Vector search]
            Neo4j[neo4j<br/>:7474/:7687<br/>Knowledge graph]
            Postgres[(postgres<br/>:5432<br/>Metadata + Langfuse)]
        end

        subgraph "LLM Layer"
            LLMProxy[llm-proxy<br/>LiteLLM :4000]
        end

        subgraph "Batch Jobs"
            Seeder[seeder<br/>DB + Qdrant seeding]
            GraphBuilder[neo4j-graph-builder<br/>Knowledge graph builder]
        end

        subgraph "Observability"
            Langfuse[langfuse<br/>:3000<br/>LLM tracing]
            LangfuseWorker[langfuse-worker]
            Clickhouse[langfuse-clickhouse<br/>OLAP]
            Redis[langfuse-redis<br/>Queue/cache]
            Minio[langfuse-minio<br/>Blob store]
            Grafana[grafana<br/>:3000<br/>Dashboards]
            Loki[loki<br/>:3100<br/>Log aggregation]
            Prometheus[prometheus<br/>:9090<br/>Metrics]
        end

        subgraph "Testing"
            AgenticAPI[agentic-api<br/>FastAPI :8000<br/>Legacy API]
            Test[test<br/>Test runner]
        end
    end

    subgraph "External"
        LMStudio[LM Studio<br/>mac-studio.local:1234<br/>Local LLMs]
        NotePlan[(NotePlan<br/>Local filesystem)]
        ClaudeAPI[Claude API<br/>anthropic.com]
    end

    %% Kong routing
    Kong -->|"chat.bytesofpurpose.com /"| ChatUI
    Kong -->|"chat.bytesofpurpose.com /api"| ClaudeAgent
    Kong -->|"langfuse.bytesofpurpose.com"| Langfuse
    Kong -->|"grafana.bytesofpurpose.com"| Grafana

    %% Agent dependencies
    ClaudeAgent --> Qdrant
    ClaudeAgent --> Neo4j
    ClaudeAgent --> TidyMCP
    ClaudeAgent --> Langfuse
    ClaudeAgent -.->|"Anthropic API"| ClaudeAPI
    ClaudeAgent -.->|"NotePlan notes"| NotePlan

    %% LLM routing
    LLMProxy -.-> LMStudio
    AgenticAPI --> LLMProxy
    AgenticAPI --> Postgres
    AgenticAPI --> Qdrant
    AgenticAPI --> TidyMCP

    %% Batch jobs
    Seeder --> Postgres
    Seeder --> Qdrant
    Seeder --> LLMProxy
    GraphBuilder --> LLMProxy

    %% Observability internals
    Langfuse --> Postgres
    Langfuse --> Clickhouse
    Langfuse --> Redis
    Langfuse --> Minio
    LangfuseWorker --> Postgres
    LangfuseWorker --> Clickhouse
    LangfuseWorker --> Redis
    LangfuseWorker --> Minio
    Grafana --> Loki
    Grafana --> Prometheus
    Prometheus --> AgenticAPI
```

## Hostname Routing

All subdomains route through **CF Access (LinkedIn SSO) -> CF Tunnel -> Kong**.

| Hostname | Kong Target | Container | Stack |
|----------|-------------|-----------|-------|
| `chat.bytesofpurpose.com /` | `http://chat:80` | `chat` (nginx) | knowledge-agents |
| `chat.bytesofpurpose.com /api` | `http://claude-agent:8000` | `claude-agent` | knowledge-agents |
| `langfuse.bytesofpurpose.com` | `http://langfuse:3000` | `langfuse` | knowledge-agents |
| `grafana.bytesofpurpose.com` | `http://grafana:3000` | `grafana` | knowledge-agents |
| `site.bytesofpurpose.com` | `http://site:80` | `site` | private-site |
| `plans.bytesofpurpose.com` | `http://plans-server:80` | `plans-server` | private-site |
| `art.bytesofpurpose.com` | `http://art-server:80` | `art-server` | private-site |
| `analytics.bytesofpurpose.com` | `http://umami:3000` | `umami` | private-site |
| `mcp.bytesofpurpose.com` | `http://mcp:8080` | `mcp` | private-site |

## Cross-Stack Networking

Containers in the knowledge-agents stack that need to be reachable from the private-site Kong must be connected to the `private-site_internal` Docker network:

```bash
make cross-network-connect   # Connect all (langfuse, chat, claude-agent)
make cross-network-check     # Verify all reachable from Kong
```

**Connection lost on container recreate.** `make deploy` runs `cross-network-connect` automatically post-deploy. If you recreate individual containers, re-run the connect target for that service.

| Service | Connect Command | Alias on private-site_internal |
|---------|----------------|-------------------------------|
| Langfuse | `make langfuse-connect` | `langfuse` |
| Chat UI | `make chat-connect` | `chat` |
| Claude Agent | `make claude-agent-connect` | `claude-agent` |

## Container Port Map

| Container | Internal Port | Host Port | Purpose |
|-----------|--------------|-----------|---------|
| postgres | 5432 | 5432 | Metadata DB + Langfuse DB |
| qdrant | 6333, 6334 | 6333, 6334 | Vector search (HTTP, gRPC) |
| neo4j | 7474, 7687 | 7474, 7687 | Graph DB (browser, Bolt) |
| llm-proxy | 4000 | 4000 | LiteLLM proxy |
| agentic-api | 8000 | 8001 | Legacy API |
| tidy-mcp | 8000 | 8003 | NotePlan MCP tools |
| claude-agent | 8000 | 8004 | Conversational agent |
| chat | 80 | 8080 | Chat UI (nginx) |
| prometheus | 9090 | 9090 | Metrics |
| grafana | 3000 | 3002 | Dashboards + Logs |
| loki | 3100 | 3100 | Log aggregation |
| langfuse | 3000 | 3210 | LLM tracing |
