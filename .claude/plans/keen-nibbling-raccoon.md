# Grafana Observability: Loki via Docker Logging Driver + Separate Claude Agent Metrics

## Context

Logs scattered across containers, no centralized search, Claude Agent has no Prometheus metrics. Need lightweight local-dev observability.

**Architecture:** Use the **Loki Docker logging driver** so all containers ship logs directly to Loki — no Alloy/Promtail needed. Just 2 new containers: Grafana + Loki. Claude Agent gets its own `/metrics` endpoint scraped separately by the existing Prometheus.

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ agentic-api │  │ claude-agent  │  │ neo4j, etc   │
│ :8001       │  │ :8004        │  │              │
│ /metrics    │  │ /metrics NEW │  │              │
└──────┬──────┘  └──────┬───────┘  └──────┬───────┘
       │                │                  │
       │     Docker logging driver: loki   │
       └────────────────┼──────────────────┘
                        ▼
              ┌──────────────────┐    ┌──────────────┐
              │  Loki :3100      │    │  Prometheus   │
              │  (log storage)   │    │  :9090        │
              └────────┬─────────┘    └──────┬────────┘
                       │                      │
                       ▼                      ▼
              ┌──────────────────────────────────────┐
              │          Grafana :3000                │
              │  Datasources: Prometheus, Loki       │
              │  Volume: observability_data           │
              └──────────────────────────────────────┘
```

**2 new containers:** Grafana (~80MB RAM), Loki (~100MB RAM)

## Plan

### Step 1: Install Loki Docker logging driver plugin on ALL Docker hosts

One-time setup on each machine running Docker (documented in README + Makefile + OBSERVABILITY.md):

```bash
# Local machine (Docker Desktop for Mac)
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions

# Mac Studio (remote — if running Docker containers there)
ssh mac-studio "docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions"
```

Add a Makefile target that installs on both:
```makefile
observability-install: ## Install Loki Docker logging driver on local + Mac Studio
    docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions 2>/dev/null || echo "Already installed locally"
    ssh mac-studio "docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions" 2>/dev/null || echo "Already installed on Mac Studio (or Docker not running)"
```

Verify with:
```bash
docker plugin ls  # Should show "loki:latest" as enabled
ssh mac-studio "docker plugin ls"
```

### Step 2: Add Prometheus metrics to Claude Agent

**File:** `src/knowledge_agents/claude_agent/server.py`

Add `claude_agent_` namespaced Prometheus metrics:
- `claude_agent_chat_requests_total` (counter, labels: status)
- `claude_agent_chat_duration_seconds` (histogram)
- `claude_agent_tool_calls_total` (counter, labels: tool_name)
- `claude_agent_rate_limit_events_total` (counter, labels: status)
- `claude_agent_cost_usd_total` (counter)

Add `GET /metrics` endpoint returning `generate_latest()`.
Instrument `chat()` and `chat_stream()` handlers.

**File:** `requirements-claude-agent.txt` — add `prometheus_client>=0.20.0`

### Step 3: Switch to JSON structured logging (file handlers)

**File:** `src/knowledge_agents/config/logging_config.py` — add `JsonFormatter`
**File:** `src/knowledge_agents/claude_agent/server.py` — JSON on file handler, plain text on console

### Step 4: Update Prometheus to scrape claude-agent separately

**File:** `config/prometheus.yml`

Add:
```yaml
  - job_name: 'claude-agent'
    static_configs:
      - targets: ['claude-agent:8000']
    scrape_interval: 15s
```

### Step 5: Add Loki + Grafana to docker-compose

**File:** `docker-compose.yml`

```yaml
loki:
  image: grafana/loki:latest
  ports:
    - "3100:3100"
  volumes:
    - observability_data:/loki
    - ./config/loki.yml:/etc/loki/local-config.yaml:ro
  command: -config.file=/etc/loki/local-config.yaml
  healthcheck:
    test: ["CMD-SHELL", "wget -q --tries=1 -O- http://localhost:3100/ready || exit 1"]
    interval: 15s
    timeout: 5s
    retries: 5
    start_period: 30s
  restart: unless-stopped

grafana:
  image: grafana/grafana-oss:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=knowledge123
    - GF_AUTH_ANONYMOUS_ENABLED=true
    - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
  volumes:
    - observability_data:/var/lib/grafana
    - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
  depends_on:
    loki:
      condition: service_healthy
    prometheus:
      condition: service_started
  restart: unless-stopped
```

Add Docker logging driver to ALL services via `x-logging` anchor:
```yaml
x-logging: &loki-logging
  logging:
    driver: loki
    options:
      loki-url: "http://localhost:3100/loki/api/v1/push"
      loki-retries: "3"
      loki-batch-size: "100"
      labels: "service"

services:
  claude-agent:
    <<: *loki-logging
    labels:
      service: claude-agent
    ...
```

**Important:** The `loki-url` must use `host.docker.internal` or `localhost` depending on Docker Desktop networking. On Docker Desktop for Mac, containers can reach the host via `host.docker.internal`.

Actually, since Loki runs in the same compose network, services can use `http://loki:3100`. But the Docker logging driver runs at the Docker daemon level, outside the compose network. So `loki-url` must use `http://localhost:3100` (Loki port is mapped to host).

Add `observability_data:` to volumes section.

### Step 6: Create config files

**New file:** `config/loki.yml`
```yaml
auth_enabled: false
server:
  http_listen_port: 3100
common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /loki
schema_config:
  configs:
    - from: "2020-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
storage_config:
  filesystem:
    directory: /loki/chunks
limits_config:
  retention_period: 168h
```

**New file:** `config/grafana/provisioning/datasources/datasources.yml`
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

### Step 7: Create `docs/OBSERVABILITY.md` living doc

Contents:
- Stack overview (Grafana + Loki + Prometheus, Docker logging driver)
- Architecture diagram
- Services table (image, port, purpose, RAM)
- **Claude Agent metrics catalog** — all `claude_agent_*` metrics
- **Agentic API metrics** — reference `src/knowledge_agents/metrics.py`
- Log format (JSON schema)
- Accessing Grafana (localhost:3000, admin/knowledge123)
- How to add new metrics
- Docker logging driver setup (plugin install)
- Volume and retention (7 days logs, 200h metrics)
- Troubleshooting

### Step 8: Update living docs

**File:** `CLAUDE.md` — add to Living Documents:
```
- **`docs/OBSERVABILITY.md`** -- When adding metrics, changing log format, or modifying the observability stack
```

Add observability commands to Key Commands.

### Step 9: Makefile targets

```makefile
observability-up:    ## Start Grafana + Loki (requires: docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions)
observability-down:  ## Stop Grafana + Loki
grafana-open:        ## Open Grafana dashboard
```

## Critical Files

| File | Change |
|------|--------|
| `src/knowledge_agents/claude_agent/server.py` | Add `/metrics`, Prometheus counters |
| `src/knowledge_agents/config/logging_config.py` | Add `JsonFormatter` |
| `requirements-claude-agent.txt` | Add `prometheus_client` |
| `config/prometheus.yml` | Add `claude-agent` scrape job |
| `docker-compose.yml` | Add loki + grafana, `x-logging` anchor, `observability_data` volume |
| `config/loki.yml` | New: Loki config |
| `config/grafana/provisioning/datasources/datasources.yml` | New: auto-provision datasources |
| `docs/OBSERVABILITY.md` | New: living tech design doc |
| `Makefile` | Add observability targets |
| `CLAUDE.md` | Add OBSERVABILITY.md to living docs |
| `README.md` | Add Grafana to tech stack |

## Verification

1. Install plugin: `make observability-install` (installs on local + Mac Studio)
2. Verify: `docker plugin ls` shows `loki:latest` enabled on both hosts
3. `make observability-up` — Grafana + Loki start
3. `make claude-agent-up` — claude-agent starts with loki logging driver
4. `http://localhost:3000` — Grafana loads
5. Explore > Loki > `{service="claude-agent"}` — see claude-agent logs
6. Explore > Prometheus > `claude_agent_chat_requests_total` — see metrics
7. Send a chat request, verify it appears in both Loki and Prometheus
8. `make observability-down` — clean shutdown
