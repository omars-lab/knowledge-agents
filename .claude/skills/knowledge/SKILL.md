---
name: knowledge
description: Query NotePlan notes, build knowledge graphs, and visualize connections via the Claude Agent
user_invocable: true
---

# /knowledge — Query your notes via the Claude Agent

Ask questions about your NotePlan notes, build knowledge graphs, and visualize connections — all from Claude Code.

## How to use

```
/knowledge <your question or command>
```

## Prerequisites

The stack must be running. If not deployed yet, use `/deploy` first. Then ensure the Claude Agent is up:

```bash
make claude-agent-up && make claude-agent-auth-seed
```

## Workflow

### 1. Check the agent is running

Run a health check first:
```bash
curl -sf http://localhost:8004/health
```

If it fails, start the agent:
```bash
make claude-agent-up && make claude-agent-auth-seed
```

### 2. Send the query to the agent

Use the chat API to send the user's question:
```bash
curl -s -m 300 -X POST http://localhost:8004/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "<USER_QUERY>"}'
```

Parse the JSON response:
- `response` — the agent's answer text
- `tools_used` — which tools the agent called
- `metadata.session_id` — for follow-up queries
- `metadata.cost_usd` — API cost
- `metadata.duration_ms` — response time

### 3. Display the result

Show the user:
1. The agent's response text
2. Tools used (as a brief note)
3. Cost and duration
4. If the response references note files, mention the NotePlan links

### 4. Handle follow-up queries

If the user asks follow-up questions in the same conversation, pass the `session_id` from the previous response:
```bash
curl -s -m 300 -X POST http://localhost:8004/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "<FOLLOW_UP>", "session_id": "<SESSION_ID>"}'
```

### 5. Graph visualization (on-demand)

If the user asks to "show a graph", "visualize", or "render" the knowledge graph:

1. First, query the knowledge graph via the agent to get relevant entities
2. Then render an SVG using the graph renderer:
```bash
python scripts/render_graph.py \
  --query "MATCH (n:Entity)-[r]->(m:Entity) RETURN n.name, n.type, type(r), m.name, m.type LIMIT 50" \
  --output build/graphs/knowledge-graph.svg
```
3. Show the user the SVG file path so they can view it
4. Read the SVG file to display it inline if possible

For entity-specific graphs:
```bash
python scripts/render_graph.py \
  --entity "machine learning" \
  --output build/graphs/ml-connections.svg
```

## Examples

**Ask about notes:**
```
/knowledge what notes do I have from December 2025?
```

**Read and summarize:**
```
/knowledge read Calendar/20251218.md and tell me what it contains
```

**Build knowledge graph:**
```
/knowledge read my recent calendar notes and build a knowledge graph from them
```

**Visualize:**
```
/knowledge show me a graph of all entities in the knowledge graph
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Connection refused` on :8004 | `make claude-agent-up` |
| `CLIConnectionError` or 503 | `make claude-agent-auth-seed` (token expired) |
| Empty response | Check `make claude-agent-auth-status` |
| Graph render fails | Ensure `graphviz` is installed: `pip install graphviz` |
