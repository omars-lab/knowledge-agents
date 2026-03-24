# Observability Stack

> **Living Document** — update when adding metrics, changing log format, or modifying the observability stack.

## Stack Overview

| Component | Image | Port | Purpose | RAM |
|-----------|-------|------|---------|-----|
| **Langfuse** | `langfuse/langfuse:3` | 3210 | LLM tracing, evals, prompt management | ~200 MB |
| Langfuse Worker | `langfuse/langfuse-worker:3` | — | Background job processor | ~150 MB |
| ClickHouse | `clickhouse/clickhouse-server:24.3` | — | OLAP storage for traces | ~200 MB |
| Redis | `redis:7-alpine` | — | Queue and cache for Langfuse | ~30 MB |
| MinIO | `minio/minio` | — | S3-compatible blob store | ~50 MB |
| Grafana | `grafana/grafana-oss` | 3001 | Dashboards for infra logs + metrics | ~80 MB |
| Loki | `grafana/loki` | 3100 | Log storage and query engine | ~100 MB |
| Prometheus | `prom/prometheus` | 9090 | Metrics storage (pre-existing) | ~50 MB |

**LLM tracing:** Langfuse captures every agent chat trace with input/output/cost/tools. Traces flow via the Langfuse Python SDK (v4) with graceful degradation.

**Log collection:** Docker Loki logging driver plugin ships container stdout/stderr directly to Loki. No Promtail or Alloy needed.

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ agentic-api │  │ claude-agent  │  │ summarizer   │
│ :8001       │  │ :8004        │  │ (batch)      │
└──────┬──────┘  └──────┬───────┘  └──────┬───────┘
       │                │                  │
       │     Docker logging driver: loki   │
       └────────────────┼──────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
  ┌──────────────┐ ┌─────────┐ ┌──────────────────┐
  │ Loki :3100   │ │Langfuse │ │  Grafana :3001    │
  │ (logs)       │ │ :3210   │ │  (infra dashboards│
  └──────────────┘ │ (traces)│ │   + Loki logs)    │
                   └────┬────┘ └──────────────────┘
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
         ClickHouse   Redis     MinIO
         (OLAP)      (queue)   (blobs)
```

**Two observability paths:**
- **Logs** → Docker logging driver → Loki → Grafana (search, debug)
- **LLM traces** → Langfuse SDK → Langfuse (input/output/cost/tools per call)

## Accessing Grafana

- **URL:** http://localhost:3001
- **Credentials:** admin / knowledge123 (or anonymous access enabled)
- **Datasources:** Prometheus and Loki are auto-provisioned on first start

## Accessing Langfuse (LLM Tracing)

- **URL:** http://localhost:3210
- **Credentials:** admin@localhost.dev / knowledge123
- **API Keys:** `pk-lf-knowledge` (public) / `sk-lf-knowledge` (secret)
- **Project:** Knowledge Agents (auto-created on first start)

### What's traced

| Source | Trace Name | Data Captured |
|--------|-----------|---------------|
| Claude Agent chat | `chat` | Input message, output response, cost, duration, tools used, session ID |
| Summarizer batch | `summarize_batch` | Section count, model, per-section generation spans |
| Tool calls | Tool name (e.g., `mcp__notes__read_note`) | Input parameters |

### Commands

```bash
make langfuse-up     # Start Langfuse + ClickHouse + Redis + MinIO
make langfuse-down   # Stop all Langfuse services
make langfuse-open   # Open Langfuse UI in browser
```

### Integration

Langfuse tracing is integrated via `src/knowledge_agents/utils/langfuse_trace.py`:
- **Graceful degradation** — if Langfuse is down, tracing is silently disabled
- **Config via env vars:** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **SDK:** Langfuse Python v4 (`start_observation()` + `update()` + `end()`)
- **Gotcha:** v4 SDK's `end()` doesn't accept `output` — must call `update(output=...)` first

### Useful queries

**Loki (logs):**
- All claude-agent logs: `{container_name=~".*claude-agent.*"}`
- Errors only: `{container_name=~".*claude-agent.*"} |= "ERROR"`
- By request ID: `{container_name=~".*claude-agent.*"} |= "abc12345"`

**Prometheus (metrics):**
- Chat request rate: `rate(claude_agent_chat_requests_total[5m])`
- p95 latency: `histogram_quantile(0.95, rate(claude_agent_chat_duration_seconds_bucket[5m]))`
- Tool usage: `topk(5, sum by (tool_name)(claude_agent_tool_calls_total))`
- Cost: `claude_agent_cost_usd_total`

## Claude Agent Metrics

All prefixed with `claude_agent_` — scraped by Prometheus as `job="claude-agent"`.

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `claude_agent_chat_requests_total` | Counter | `status` | Chat requests (success/error/transport_error) |
| `claude_agent_chat_duration_seconds` | Histogram | — | Response time (buckets: 1s, 5s, 10s, 30s, 60s, 120s, 300s, 600s) |
| `claude_agent_tool_calls_total` | Counter | `tool_name` | Tool invocations by name |
| `claude_agent_rate_limit_events_total` | Counter | `status` | Rate limit events (allowed/warning/rejected) |
| `claude_agent_cost_usd_total` | Counter | — | Cumulative API cost |
| `claude_agent_stream_requests_total` | Counter | `status` | Streaming chat requests |

## Agentic API Metrics

Pre-existing, 65+ metrics. See `src/knowledge_agents/metrics.py` for the full catalog.
Scraped by Prometheus as `job="agentic-api"`.

Key metrics: `http_requests_total`, `workflow_analysis_duration_seconds`, `guardrails_total`, `openai_cost_total_usd`.

## Log Format

### Console (plain text, for `docker logs`)
```
2026-03-22 18:20:57 [INFO] knowledge_agents.claude_agent.server:200 [d6e3bf04] chat request — session=(new) message='...'
```

### File (JSON, for machine consumption)
```json
{"timestamp": "2026-03-22T18:20:57", "level": "INFO", "logger": "knowledge_agents.claude_agent.server", "message": "chat request — ...", "service": "claude-agent", "request_id": "d6e3bf04", "lineno": 200}
```

## Docker Logging Driver Setup

### Prerequisites

Install the Loki Docker logging driver plugin (one-time per Docker host):

```bash
# Local machine
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions

# Verify
docker plugin ls  # Should show loki:latest enabled
```

### How it works

When configured in docker-compose.yml, the Docker daemon sends container stdout/stderr directly to Loki:

```yaml
logging:
  driver: loki
  options:
    loki-url: "http://localhost:3100/loki/api/v1/push"
```

The `loki-url` uses `localhost:3100` because the Docker logging driver runs at the daemon level (outside the compose network), and Loki's port 3100 is mapped to the host.

## Volumes and Retention

| Volume | Purpose | Retention |
|--------|---------|-----------|
| `observability_data` | Grafana dashboards + Loki log chunks | 7 days (logs), indefinite (dashboards) |
| `prometheus_data` | Prometheus TSDB | 200 hours |

## Adding New Metrics

1. Define the metric in the service's server module using `prometheus_client`:
   ```python
   MY_COUNTER = Counter("claude_agent_my_metric_total", "Description", ["label"])
   ```
2. Instrument the relevant code path: `MY_COUNTER.labels(label="value").inc()`
3. Update this document's metrics table
4. The metric auto-appears in Prometheus (already scraping `/metrics`)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Loki plugin not found | `docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions` |
| Container won't start with loki driver | Check Loki is running: `curl http://localhost:3100/ready` |
| No logs in Grafana | Check Loki datasource config, try `{job="docker"}` |
| Prometheus not scraping claude-agent | Check `config/prometheus.yml` has `claude-agent` job, verify `/metrics` responds |
| Grafana shows "No data" | Ensure datasources are provisioned: check `config/grafana/provisioning/datasources/` |
